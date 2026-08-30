"""
Tests for validate_text_document — the authoring contract, as code.

The contract was written down before it was enforced, and for a while it was
enforced only by whoever remembered to run a script. It is now checked at the
upload endpoint, which makes it load-bearing: a false positive blocks an author
from publishing, and a false negative lets through the exact defect the rule
exists to catch. Both directions are tested here.

Every rule is checked twice — once on a document that breaks it, once on a
document that satisfies it — because a validator that rejects everything passes
the first kind of test and is useless.
"""
import pathlib
import re

import pytest
import yaml

from app.services.chunking_service import (
    MIN_ANSWERS,
    MIN_DEVANAGARI_PHRASINGS,
    MIN_PHRASINGS,
    MIN_STEPS,
    TEXT_DOC_TYPES,
    validate_text_document,
)

CONTENT = pathlib.Path(__file__).resolve().parents[1] / "content" / "product-knowledge-v2"

GOOD_META = {
    "title": "A Conforming Document",
    "type": "guide",
    "status": "published",
    "audience": "merchant",
    "owner": "product-team",
    "review_by": "2099-01-01",
    "answers": ["how to do the thing", "what the thing costs", "why the thing failed"],
}

GOOD_BODY = """# A Conforming Document

An opening paragraph with enough substance in it that the section is not a
fragment when it is retrieved on its own, away from everything around it.

## The steps to do the thing

1. Open the app and find the thing.
2. Choose the option you want for it.
3. Confirm with your MPIN.

## What if it does not work

Check the obvious causes first, in order. Most failures here are a missing
field rather than anything wrong with the account itself, and the app says
which one it is when you try to save.

## Hinglish mein

Yeh kaam karne ke liye app kholein, apna option chunein aur MPIN daal kar
confirm karein. Agar save nahi ho raha to koi field khali reh gaya hoga, app
aapko bata dega ki kaunsa hai.

## Frequently asked as

- "how do I do the thing"
- "thing kaise karein"
- "चीज़ कैसे करें"
- "the thing is not saving"
- "thing save nahi ho raha"
- "चीज़ सेव नहीं हो रही"
"""


def problems_for(meta_changes=None, body=None, drop=()):
    meta = {**GOOD_META, **(meta_changes or {})}
    for k in drop:
        meta.pop(k, None)
    return validate_text_document(meta, GOOD_BODY if body is None else body)


# ── the baseline must pass, or every test below is meaningless ───────────

def test_a_conforming_document_has_no_problems():
    assert problems_for() == []


# ── front matter ─────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "field", ["title", "type", "status", "audience", "owner", "review_by"])
def test_each_required_field_is_required(field):
    found = problems_for(drop=(field,))
    assert any(f"'{field}'" in p for p in found), found


def test_an_unknown_type_is_rejected():
    found = problems_for({"type": "capability"})
    assert any("capability" in p for p in found), found


@pytest.mark.parametrize("doc_type", sorted(TEXT_DOC_TYPES))
def test_every_declared_type_is_accepted(doc_type):
    # Only guides carry the numbered-steps rule, and only guides and
    # troubleshooting need a failure section; the shared body satisfies both.
    assert problems_for({"type": doc_type}) == []


def test_too_few_answers_is_rejected():
    found = problems_for({"answers": ["only one"] * (MIN_ANSWERS - 1)})
    assert any("answers" in p for p in found), found


def test_answers_must_be_a_list_not_a_string():
    found = problems_for({"answers": "how to do the thing"})
    assert any("answers" in p for p in found), found


def test_a_review_date_in_the_past_is_rejected():
    found = problems_for({"review_by": "2020-01-01"})
    assert any("review_by" in p for p in found), found


def test_a_malformed_review_date_is_rejected():
    found = problems_for({"review_by": "next spring"})
    assert any("review_by" in p for p in found), found


# ── body shape ───────────────────────────────────────────────────────────

def test_a_guide_without_numbered_steps_is_rejected():
    body = GOOD_BODY.replace("1. Open the app and find the thing.\n", "") \
                    .replace("2. Choose the option you want for it.\n", "") \
                    .replace("3. Confirm with your MPIN.\n",
                             "Open the app, choose your option, confirm.\n")
    found = problems_for(body=body)
    assert any("numbered procedure" in p for p in found), found


def test_a_concept_without_numbered_steps_is_fine():
    # The rule exists so a procedural question has something to land on. A
    # concept document describes; it is not a procedure, and requiring steps of
    # it is what put a numbered list into a payments explainer and made it win
    # 'how do I create an offer step by step'.
    body = GOOD_BODY.replace("## The steps to do the thing", "## How the thing works")
    body = re.sub(r"^\d\. ", "", body, flags=re.M)
    assert problems_for({"type": "concept"}, body=body) == []


def test_a_missing_hinglish_section_is_rejected():
    body = GOOD_BODY.replace("## Hinglish mein", "## In Hindi")
    found = problems_for(body=body)
    assert any("Hinglish mein" in p for p in found), found


def test_a_token_hinglish_section_is_rejected():
    body = re.sub(r"## Hinglish mein\n\n.*?\n\n## Frequently",
                  "## Hinglish mein\n\nHaan ji.\n\n## Frequently",
                  GOOD_BODY, flags=re.S)
    found = problems_for(body=body)
    assert any("Hinglish mein" in p for p in found), found


def test_too_few_phrasings_is_rejected():
    lines = [l for l in GOOD_BODY.splitlines() if l.startswith('- "')]
    body = GOOD_BODY
    for line in lines[MIN_PHRASINGS - 1:]:
        body = body.replace(line + "\n", "")
    found = problems_for(body=body)
    assert any("phrasings" in p for p in found), found


def test_phrasings_without_devanagari_are_rejected():
    # Typed input arrives in Roman, speech-to-text arrives in Devanagari, and
    # both are live traffic. A document indexed only against one is invisible
    # to the other.
    body = GOOD_BODY.replace('- "चीज़ कैसे करें"\n', '- "thing kaise kare"\n') \
                    .replace('- "चीज़ सेव नहीं हो रही"\n', '- "thing save nahi hua"\n')
    found = problems_for(body=body)
    assert any("Devanagari" in p for p in found), found
    assert MIN_DEVANAGARI_PHRASINGS == 2


def test_a_guide_without_a_failure_section_is_rejected():
    body = GOOD_BODY.replace("## What if it does not work", "## More about the thing")
    found = problems_for(body=body)
    assert any("goes wrong" in p or "complaint" in p for p in found), found


@pytest.mark.parametrize("phrase", [
    "as mentioned above", "see below", "the table above", "as described below",
])
def test_positional_references_are_rejected(phrase):
    body = GOOD_BODY.replace("Check the obvious causes first, in order.",
                             f"Check the causes, {phrase}.")
    found = problems_for(body=body)
    assert any("Positional reference" in p for p in found), found


def test_a_fragment_section_is_rejected():
    body = GOOD_BODY + "\n## A stub\n\nToo short.\n"
    found = problems_for(body=body)
    assert any("retrieves as a fragment" in p for p in found), found


def test_a_section_larger_than_the_chunk_size_is_rejected():
    body = GOOD_BODY + "\n## An enormous section\n\n" + ("filler words " * 400)
    found = problems_for(body=body)
    assert any("over the" in p and "chunk size" in p for p in found), found


def test_all_problems_are_reported_at_once():
    # Same contract as validate_tool_card: an author fixing a document wants
    # every problem in one pass, not one per upload attempt.
    found = validate_text_document({"title": "Bare"}, "# Bare\n\nNothing here.\n")
    assert len(found) > 3, found


# ── the shipped corpus must satisfy its own contract ─────────────────────

@pytest.mark.parametrize(
    "path", sorted(CONTENT.rglob("*.md")), ids=lambda p: p.name)
def test_every_shipped_document_conforms(path):
    if path.name.lower() == "readme.md":
        pytest.skip("housekeeping, not content")
    raw = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
    assert match, f"{path.name} has no front matter"
    meta = yaml.safe_load(match.group(1)) or {}
    assert validate_text_document(meta, match.group(2)) == []
