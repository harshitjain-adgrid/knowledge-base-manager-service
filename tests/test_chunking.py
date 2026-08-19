"""
Chunker tests.

The invariants that matter for retrieval quality are asserted directly:
nothing is lost, nothing overflows, tables and code survive intact, and every
chunk knows which section it came from.
"""

import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.services.chunking_service import (
    chunk_document,
    chunk_text_document,
    parse_blocks,
)

settings = get_settings()


def bodies(chunks):
    """Chunk text with the breadcrumb prefix removed."""
    out = []
    for c in chunks:
        parts = c.content.split("\n\n", 1)
        out.append(parts[1] if len(parts) == 2 and " > " in parts[0] else c.content)
    return out


def crumb(chunk):
    head = chunk.content.split("\n\n", 1)[0]
    return head if " > " in head else ""


def body_of(chunk):
    return chunk.content.split("\n\n", 1)[-1]


SAMPLE = """# Refund Policy

Refunds are credited to the original payment method.

## Timing

Approved refunds settle within 7 business days.

| Method | Days | Notes |
|---|---|---|
| UPI | 3 | fastest |
| Card | 7 | issuer dependent |

## Escalation

Raise a ticket with the payments team if it is late.

```json
{"ticket": "PAY-123", "priority": "high"}
```
"""


# ── structure ──

def test_headings_start_new_chunks():
    chunks = chunk_text_document(SAMPLE, doc_title="Refunds")
    sections = [c.metadata.get("section") for c in chunks]
    assert "Timing" in sections and "Escalation" in sections
    for c in chunks:
        assert not (
            "settle within 7 business days" in c.content and "Raise a ticket" in c.content
        )


def test_every_chunk_carries_its_breadcrumb():
    chunks = chunk_text_document(SAMPLE, doc_title="Refunds")
    for c in chunks:
        assert crumb(c).startswith("Refunds"), c.content[:80]
        assert c.metadata["heading_path"]


def test_heading_path_nests_correctly():
    md = "# A\n\ntop\n\n## B\n\nmid\n\n### C\n\ndeep\n\n## D\n\nback up\n"
    paths = [c.metadata["heading_path"] for c in chunk_text_document(md, doc_title="T")]
    assert ["A"] in paths
    assert ["A", "B"] in paths
    assert ["A", "B", "C"] in paths
    assert ["A", "D"] in paths  # C is popped when D opens at level 2


def test_deeper_heading_does_not_pop_shallower():
    chunks = chunk_text_document("# A\n\n## B\n\n### C\n\ntext\n", doc_title="T")
    assert chunks[0].metadata["heading_path"] == ["A", "B", "C"]


# ── atomic blocks ──

def test_table_is_never_split_when_it_fits():
    chunks = chunk_text_document(SAMPLE, doc_title="Refunds")
    holder = [c for c in chunks if "| UPI |" in c.content]
    assert len(holder) == 1
    assert "| Card |" in holder[0].content
    assert "| Method | Days | Notes |" in holder[0].content


def test_oversized_table_repeats_its_header():
    rows = "\n".join("| CODE{0} | {0}% | note {0} |".format(i) for i in range(200))
    md = "# Codes\n\n| Code | Value | Notes |\n|---|---|---|\n" + rows + "\n"
    chunks = chunk_text_document(md, doc_title="T")
    assert len(chunks) > 1
    for c in chunks:
        assert "| Code | Value | Notes |" in c.content, "header missing from a piece"


def test_code_block_stays_intact():
    chunks = chunk_text_document(SAMPLE, doc_title="Refunds")
    holder = [c for c in chunks if "ticket" in c.content and "```" in c.content]
    assert len(holder) == 1
    assert holder[0].content.count("```") == 2


def test_markdown_inside_code_is_not_parsed_as_structure():
    md = "# Real\n\n```\n# Not a heading\n| not | a table |\n|---|---|\n```\n\nafter\n"
    chunks = chunk_text_document(md, doc_title="T")
    assert all(c.metadata["heading_path"] == ["Real"] for c in chunks)


def test_unclosed_code_fence_does_not_lose_content():
    md = "# T\n\n```\nnever closed\nstill here\n"
    joined = " ".join(c.content for c in chunk_text_document(md, doc_title="T"))
    assert "never closed" in joined and "still here" in joined


def test_pipe_in_prose_is_not_a_table():
    md = "# T\n\nUse PERCENTAGE | FLAT for the type field.\n"
    chunks = chunk_text_document(md, doc_title="T")
    assert "PERCENTAGE | FLAT" in chunks[0].content


def test_tilde_fence_is_supported():
    md = "# T\n\n~~~\n# not a heading\n~~~\n"
    chunks = chunk_text_document(md, doc_title="T")
    assert all(c.metadata["heading_path"] == ["T"] for c in chunks)


# ── size ──

@pytest.mark.parametrize("size", [200, 600, 1200, 4000])
def test_chunks_respect_max_size(size, monkeypatch):
    monkeypatch.setattr(settings, "chunk_size", size)
    text = "# H\n\n" + "\n\n".join("Paragraph number {0}. ".format(i) * 12 for i in range(40))
    for c in chunk_text_document(text, doc_title="Doc"):
        assert len(body_of(c)) <= size * 1.2, "{0} > {1}".format(len(body_of(c)), size)


def test_single_huge_paragraph_is_split():
    chunks = chunk_text_document("# H\n\n" + ("word " * 4000), doc_title="T")
    assert len(chunks) > 1


def test_long_line_without_spaces_terminates():
    chunks = chunk_text_document("# H\n\n" + ("x" * 10000), doc_title="T")
    assert len(chunks) > 1
    assert sum(c.content.count("x") for c in chunks) >= 10000


def test_oversized_code_block_splits_on_line_boundaries():
    lines = "\n".join('  "field_{0}": "value_{0}",'.format(i) for i in range(300))
    md = "# Payload\n\n```json\n{\n" + lines + "\n}\n```\n"
    chunks = chunk_text_document(md, doc_title="T")
    assert len(chunks) > 1
    for c in chunks:
        for line in body_of(c).split("\n"):
            assert line == "" or line.startswith(("```", "{", "}", '  "')), line[:40]


# ── content preservation ──

def test_no_content_is_lost():
    joined = " ".join(bodies(chunk_text_document(SAMPLE, doc_title="Refunds")))
    for phrase in [
        "original payment method",
        "7 business days",
        "issuer dependent",
        "Raise a ticket",
        "PAY-123",
    ]:
        assert phrase in joined, phrase


def test_chunk_indices_are_contiguous():
    chunks = chunk_text_document(SAMPLE * 3, doc_title="T")
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_is_deterministic():
    a = [c.content for c in chunk_text_document(SAMPLE, doc_title="T")]
    b = [c.content for c in chunk_text_document(SAMPLE, doc_title="T")]
    assert a == b


# ── degenerate input ──

@pytest.mark.parametrize("content", ["", "   ", "\n\n\n", "\t \n "])
def test_empty_input_yields_no_chunks(content):
    assert chunk_text_document(content, doc_title="T") == []


def test_heading_with_no_body_produces_no_empty_chunk():
    chunks = chunk_text_document("# A\n\n## B\n\n## C\n", doc_title="T")
    assert all(body_of(c).strip() for c in chunks)


def test_content_before_any_heading_is_kept():
    md = "Preamble text that matters.\n\n# First\n\nbody\n"
    joined = " ".join(c.content for c in chunk_text_document(md, doc_title="T"))
    assert "Preamble text that matters." in joined


def test_document_without_headings_still_works():
    md = "\n\n".join("Paragraph {0} with some content.".format(i) for i in range(30))
    chunks = chunk_text_document(md, doc_title="Plain Doc")
    assert chunks
    assert all(c.content.startswith("Plain Doc\n\n") for c in chunks)


def test_no_title_means_no_breadcrumb_prefix():
    chunks = chunk_text_document("# A\n\nbody\n")
    assert chunks[0].content.startswith("A\n\n")


def test_windows_line_endings():
    chunks = chunk_text_document("# A\r\n\r\nbody here\r\n", doc_title="T")
    assert "body here" in chunks[0].content
    assert "\r" not in chunks[0].content


def test_unicode_and_emoji_survive():
    md = "# Khata — खाता \U0001f4d2\n\nUdhaar ka hisaab ₹500.\n"
    chunks = chunk_text_document(md, doc_title="Khata")
    assert "खाता" in chunks[0].content
    assert "\U0001f4d2" in chunks[0].content
    assert "₹500" in chunks[0].content


def test_duplicate_heading_names_are_disambiguated_by_path():
    md = "# Deal\n\n## Validity\n\ndeal rules\n\n# Discount\n\n## Validity\n\ndiscount rules\n"
    paths = [c.metadata["heading_path"] for c in chunk_text_document(md, doc_title="T")]
    assert ["Deal", "Validity"] in paths
    assert ["Discount", "Validity"] in paths


def test_setext_style_and_trailing_hashes():
    chunks = chunk_text_document("### Closed heading ###\n\nbody\n", doc_title="T")
    assert chunks[0].metadata["heading_path"] == ["Closed heading"]


# ── the failure this work exists to fix ──

def test_chunks_are_self_contained():
    """Regression guard for orphans like 'same shape as the deal validity above'."""
    md = (
        "# Create Discount\n\n## Validity\n\n"
        "| Field | Required |\n|---|---|\n| endDate | conditional |\n\n"
        "validity object — same shape as the deal validity above\n"
    )
    for c in chunk_text_document(md, doc_title="Deals API"):
        assert c.content.startswith("Deals API > Create Discount")


def test_no_chunk_starts_mid_sentence():
    for c in chunk_text_document(SAMPLE, doc_title="Refunds"):
        body = body_of(c).lstrip()
        assert not re.match(r"^[a-z,.)\]}\"]", body), body[:60]


# ── api definitions ──

def test_parse_blocks_classifies_correctly():
    kinds = [b.kind for b in parse_blocks(SAMPLE)]
    assert "heading" in kinds and "table" in kinds and "code" in kinds and "text" in kinds


# ── front matter promotion ──

def test_frontmatter_dates_are_json_safe():
    """PyYAML turns `last_reviewed: 2026-08-18` into a date, which JSONB cannot store."""
    import datetime
    import json

    from app.services.extraction_service import ExtractedDocument, promote_frontmatter

    e = ExtractedDocument(
        text="x", file_name="f.md", file_size=1, source_format="md",
        metadata={"frontmatter": {
            "title": "T", "type": "Guide",
            "last_reviewed": datetime.date(2026, 8, 18),
            "reviewed_at": datetime.datetime(2026, 8, 18, 10, 30),
            "at": datetime.time(9, 0),
            "tags": ["a", "b"],
            "nested": {"d": datetime.date(2020, 1, 1)},
            "unique": {"x"},
        }},
    )
    r = promote_frontmatter(e)
    assert r["title"] == "T"
    assert r["doc_type"] == "guide"                    # normalised
    assert r["metadata"]["last_reviewed"] == "2026-08-18"
    assert r["metadata"]["nested"]["d"] == "2020-01-01"
    json.dumps(r["metadata"])                          # must not raise


def test_frontmatter_absent_is_harmless():
    from app.services.extraction_service import ExtractedDocument, promote_frontmatter

    e = ExtractedDocument(text="x", file_name="f.pdf", file_size=1,
                          source_format="pdf", metadata={"page_count": 3})
    assert promote_frontmatter(e) == {"title": None, "doc_type": None, "metadata": {}}


@pytest.mark.parametrize("bad_type", ["Not A Type!", "", 42, None, "x" * 100])
def test_unusable_frontmatter_type_is_ignored(bad_type):
    from app.services.extraction_service import ExtractedDocument, promote_frontmatter

    e = ExtractedDocument(text="x", file_name="f.md", file_size=1, source_format="md",
                          metadata={"frontmatter": {"title": "T", "type": bad_type}})
    assert promote_frontmatter(e)["doc_type"] is None


def test_frontmatter_keys_are_case_insensitive():
    from app.services.extraction_service import ExtractedDocument, promote_frontmatter

    e = ExtractedDocument(text="x", file_name="f.md", file_size=1, source_format="md",
                          metadata={"frontmatter": {"Title": "T", "Type": "guide"}})
    r = promote_frontmatter(e)
    assert r["title"] == "T" and r["doc_type"] == "guide"


def test_breadcrumb_does_not_repeat_the_title():
    """The recommended style makes H1 equal the title; it must not appear twice."""
    md = "# Creating an Offer\n\n## When to use\n\nUse it for automatic discounts.\n"
    chunks = chunk_text_document(md, doc_title="Creating an Offer")
    for c in chunks:
        assert not c.content.startswith("Creating an Offer > Creating an Offer")
    deep = [c for c in chunks if c.metadata.get("section") == "When to use"]
    assert deep and deep[0].content.startswith("Creating an Offer > When to use")


def test_breadcrumb_keeps_a_heading_that_differs_from_the_title():
    chunks = chunk_text_document("# Overview\n\nbody\n", doc_title="Offers Guide")
    assert chunks[0].content.startswith("Offers Guide > Overview")


def test_breadcrumb_title_match_ignores_punctuation_and_case():
    chunks = chunk_text_document("# What is Khata?\n\nbody\n", doc_title="What is Khata")
    assert chunks[0].content.startswith("What is Khata\n\n")
