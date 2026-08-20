"""
Tests for the product-knowledge documents in content/product-knowledge/.

Whether the right document actually comes back for a real question cannot be
asserted here — that depends on an embedding model and a populated knowledge
base, and is measured instead against a labelled set by seeds/eval/run_eval.py.
What is tested here is everything that has to hold regardless of what the model
returns: that a document is shaped so retrieval has something to work with.

Each rule comes from docs/CONTENT_GUIDE.md. These run over every file, so a
document added later is held to the same standard as the ones written first.
"""

import pathlib
import re

import pytest
import yaml

from app.services.chunking_service import chunk_document
from app.services.extraction_service import extract, promote_frontmatter

CONTENT = pathlib.Path(__file__).parent.parent / "content" / "product-knowledge"

REQUIRED_KEYS = {"title", "type", "tags", "audience", "status", "owner", "last_reviewed"}
DOC_TYPES = {"guide", "concept", "policy", "capability", "troubleshooting"}

# A section that refers to another one by position stops standing alone, and a
# chunk retrieved on its own then points at something the reader cannot see.
POSITIONAL = re.compile(
    r"\b(as (mentioned|described|shown) (above|below)"
    r"|see (above|below)"
    r"|the (section|table|list) (above|below))\b",
    re.I,
)

# Enough Hinglish to tell that a document was written for the people who ask in
# it, rather than translated as an afterthought.
HINGLISH = re.compile(
    r"\b(kya|kaise|kahan|nahi|kab|kitna|kitni|kitne|mera|meri|hai|hota|karein"
    r"|dikhao|dikh|bhool|wapas|badle|milega|milti|karta|chalaye|dhoond\w*"
    r"|dikhta|aaya|aata|aayega|hisaab|kamaya|kharcha|paisa|dukaan|grahak"
    r"|utha|nikalein|lagta|faayda|jodne|farak|maangta|pahunchega|chadh"
    r"|hatana|chalu|rakam|jama|khatam|sakta|sakte|sakti|lag)\b"
)

# A heading naming the case where things go wrong. Half of what merchants ask
# arrives as a complaint, so a document without one answers only half its job.
TROUBLE = re.compile(
    r"^## .*(what if|not showing|not work|goes wrong|wrong|fail|missing"
    r"|expire|cannot|has not|no longer|problem)",
    re.I | re.M,
)


def documents() -> list[pathlib.Path]:
    """Every content file. A README explains the folder and is not content."""
    return sorted(p for p in CONTENT.rglob("*.md") if p.name.lower() != "readme.md")


def parsed(path: pathlib.Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name} has no front matter"
    _, front, body = text.split("---\n", 2)
    return yaml.safe_load(front), body


def sections(body: str) -> list[tuple[str, str]]:
    """Every `##` section as (heading, whole section including the heading)."""
    return [("## " + part.split("\n", 1)[0].strip(), "## " + part.rstrip())
            for part in re.split(r"^## ", body, flags=re.M)[1:]]


ALL = documents()
IDS = [p.relative_to(CONTENT).as_posix() for p in ALL]


def test_there_is_content_to_check():
    assert ALL, f"no documents found under {CONTENT}"


# ── Front matter ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", ALL, ids=IDS)
def test_front_matter_carries_every_required_key(path):
    front, _ = parsed(path)
    assert REQUIRED_KEYS <= set(front), f"missing {sorted(REQUIRED_KEYS - set(front))}"


@pytest.mark.parametrize("path", ALL, ids=IDS)
def test_type_is_one_the_service_understands(path):
    front, _ = parsed(path)
    assert front["type"] in DOC_TYPES


@pytest.mark.parametrize("path", ALL, ids=IDS)
def test_tags_are_a_non_empty_list(path):
    front, _ = parsed(path)
    assert isinstance(front["tags"], list) and front["tags"]


@pytest.mark.parametrize("path", ALL, ids=IDS)
def test_the_heading_and_the_title_agree(path):
    """The title is what the evaluation set names, and what search returns."""
    front, body = parsed(path)
    headings = re.findall(r"^# (.+)$", body, re.M)
    assert len(headings) == 1, f"expected one H1, found {len(headings)}"
    assert headings[0].strip() == str(front["title"]).strip()


# ── Shape ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", ALL, ids=IDS)
def test_every_section_is_worth_retrieving_and_small_enough_to_use(path):
    _, body = parsed(path)
    found = sections(body)
    assert found, "no sections"
    for heading, text in found:
        assert 100 <= len(text) <= 1200, f"{heading} is {len(text)} chars"


@pytest.mark.parametrize("path", ALL, ids=IDS)
def test_no_section_points_at_another_by_position(path):
    _, body = parsed(path)
    hit = POSITIONAL.search(body)
    assert hit is None, f"positional reference {hit.group(0)!r}" if hit else ""


@pytest.mark.parametrize("path", ALL, ids=IDS)
def test_the_case_where_it_goes_wrong_is_covered(path):
    _, body = parsed(path)
    assert TROUBLE.search(body), "no section covering what happens when it fails"


# ── How it is asked ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", ALL, ids=IDS)
def test_there_is_a_list_of_how_it_gets_asked(path):
    _, body = parsed(path)
    assert "## Frequently asked as" in body


@pytest.mark.parametrize("path", ALL, ids=IDS)
def test_enough_phrasings_to_match_more_than_one_wording(path):
    _, body = parsed(path)
    block = body.split("## Frequently asked as", 1)[1]
    lines = [line for line in block.splitlines() if line.startswith("- ")]
    assert len(lines) >= 5, f"only {len(lines)} phrasings"


@pytest.mark.parametrize("path", ALL, ids=IDS)
def test_at_least_one_phrasing_is_how_a_merchant_would_actually_say_it(path):
    _, body = parsed(path)
    block = body.split("## Frequently asked as", 1)[1]
    lines = [line for line in block.splitlines() if line.startswith("- ")]
    assert any(HINGLISH.search(line) for line in lines), "no Hinglish phrasing"


# ── What must not be in here ─────────────────────────────────────────────────

@pytest.mark.parametrize("path", ALL, ids=IDS)
def test_no_api_surface_leaked_into_the_product_knowledge_base(path):
    """
    Endpoints belong to the API catalogue. Mixing them in makes conversational
    retrieval worse, because a question about money then competes with a card
    about a payments endpoint.
    """
    _, body = parsed(path)
    for pattern in (r"\b(GET|POST|PUT|PATCH|DELETE)\s+/",
                    r"https?://[^\s)]+/v\d",
                    r"\b\d{3}\s+(Bad Request|Unauthorized|Not Found)\b"):
        hit = re.search(pattern, body)
        assert hit is None, f"looks like an API detail: {hit.group(0)!r}" if hit else ""


# ── Chunking ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", ALL, ids=IDS)
def test_it_chunks_into_passages_that_can_answer_on_their_own(path):
    extraction = extract(path.read_bytes(), path.name)
    front = promote_frontmatter(extraction)
    chunks = chunk_document(extraction.text, front["doc_type"] or "text",
                            front["metadata"], front["title"])

    assert chunks, "produced no chunks"
    for chunk in chunks:
        # A chunk shorter than this is a fragment. Retrieved on its own it gives
        # the assistant a heading and half a thought, which reads back as a
        # confident non-answer. The opening paragraph is the usual offender,
        # because it is chunked apart from every section under it.
        assert len(chunk.content) >= 120, (
            f"chunk {chunk.chunk_index} is {len(chunk.content)} chars: "
            f"{chunk.content[:60]!r}"
        )


@pytest.mark.parametrize("path", ALL, ids=IDS)
def test_every_chunk_keeps_the_metadata_it_can_be_filtered_on(path):
    extraction = extract(path.read_bytes(), path.name)
    front = promote_frontmatter(extraction)
    chunks = chunk_document(extraction.text, front["doc_type"] or "text",
                            front["metadata"], front["title"])

    for chunk in chunks:
        assert "tags" in chunk.metadata
        assert "status" in chunk.metadata
        assert chunk.metadata.get("heading_path"), "chunk lost its breadcrumb"


# ── The evaluation set ───────────────────────────────────────────────────────

EVAL = pathlib.Path(__file__).parent.parent / "seeds" / "eval" / "product_queries.yaml"


def eval_cases() -> list[dict]:
    return yaml.safe_load(EVAL.read_text(encoding="utf-8"))["queries"]


def titles() -> set[str]:
    return {parsed(p)[0]["title"] for p in ALL}


def test_every_document_the_evaluation_names_actually_exists():
    """A renamed document silently turns its queries into permanent failures."""
    known = titles()
    named = {c["expect"] for c in eval_cases() if c.get("expect")}
    named |= {c["not_expect"] for c in eval_cases() if c.get("not_expect")}
    assert named <= known, f"evaluation names documents that are gone: {sorted(named - known)}"


def test_every_document_is_measured_by_at_least_one_query():
    expected = {c["expect"] for c in eval_cases() if c.get("expect")}
    assert titles() <= expected, f"never retrieved for: {sorted(titles() - expected)}"


def test_no_query_is_lifted_out_of_the_document_it_targets():
    """
    A query copied from a "Frequently asked as" list measures string overlap,
    not retrieval — it would pass however badly the document was written.
    """
    phrasings = set()
    for path in ALL:
        block = parsed(path)[1].split("## Frequently asked as", 1)[-1]
        phrasings |= {line.strip(' -"') for line in block.splitlines()
                      if line.startswith("- ")}

    copied = [c["q"] for c in eval_cases() if c["q"] in phrasings]
    assert not copied, f"copied straight out of the content: {copied}"


def test_a_confusable_case_names_the_neighbour_it_is_confused_with():
    for case in eval_cases():
        if case["tier"] == "confusable":
            assert case.get("not_expect"), f"{case['q']!r} names no neighbour"
            assert case["not_expect"] != case.get("expect")


def test_there_are_questions_nothing_answers():
    """
    Without them the evaluation only ever rewards answering, and a knowledge
    base that answers everything confidently is the failure mode that matters.
    """
    assert sum(1 for c in eval_cases() if c["tier"] == "negative") >= 5
