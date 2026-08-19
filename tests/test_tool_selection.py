"""
Tests for API cards and the action-selection pipeline's pure logic.

The retrieval half — whether the right API actually comes back for a real
message — cannot be asserted here, because it depends on an embedding model and
a populated catalogue. That is measured instead, against a labelled set, by
seeds/eval/run_eval.py. What is tested here is everything that has to hold
regardless of what the model returns.
"""

import pytest

from app.services.chunking_service import (
    MIN_UTTERANCES,
    _describe_fields,
    chunk_document,
    chunk_tool_card,
    validate_tool_card,
)
from app.services.tool_selection import _aggregate_by_api, _rank_domains


def card(**overrides) -> dict:
    meta = {
        "api_id": "offers.create",
        "domain": "offers",
        "method": "POST",
        "path": "/v1/merchant/offers",
        "utterances": ["start a sale", "give 20% off", "create an offer"],
        "fields": [
            {"name": "offer_name", "required": True, "prompt": "What is it called?"}
        ],
    }
    meta.update(overrides)
    return meta


# ── Front matter validation ──────────────────────────────────────────────────

def test_a_complete_card_has_nothing_wrong_with_it():
    assert validate_tool_card(card()) == []


@pytest.mark.parametrize("missing", ["api_id", "domain", "method", "path"])
def test_every_required_field_is_reported_when_absent(missing):
    meta = card()
    del meta[missing]
    assert any(missing in problem for problem in validate_tool_card(meta))


def test_all_problems_are_reported_at_once():
    # An author fixing a card should see everything wrong with it in one pass,
    # not discover the next problem after fixing the first.
    problems = validate_tool_card({})
    assert len(problems) >= 5


@pytest.mark.parametrize(
    "api_id", ["Offers.Create", "offers create", "offers", "OFFERS.CREATE", "offers."]
)
def test_an_api_id_that_does_not_name_area_and_action_is_refused(api_id):
    assert any("api_id" in p for p in validate_tool_card(card(api_id=api_id)))


def test_a_dotted_lowercase_api_id_is_accepted():
    assert validate_tool_card(card(api_id="catalog.product.create")) == []


def test_an_unknown_http_method_is_refused():
    assert any("method" in p for p in validate_tool_card(card(method="FETCH")))


def test_a_path_without_a_leading_slash_is_refused():
    assert any("path" in p for p in validate_tool_card(card(path="v1/offers")))


def test_too_few_utterances_is_refused():
    meta = card(utterances=["only one"])
    assert any("utterances" in p for p in validate_tool_card(meta))


def test_the_minimum_number_of_utterances_is_accepted():
    meta = card(utterances=[f"phrase {i}" for i in range(MIN_UTTERANCES)])
    assert validate_tool_card(meta) == []


def test_a_required_field_without_a_prompt_is_refused():
    # There would be nothing to say to the merchant when it is missing.
    meta = card(fields=[{"name": "amount", "required": True}])
    assert any("prompt" in p for p in validate_tool_card(meta))


def test_an_optional_field_needs_no_prompt():
    meta = card(fields=[{"name": "note", "required": False}])
    assert validate_tool_card(meta) == []


# ── Chunking ─────────────────────────────────────────────────────────────────

def test_a_card_becomes_one_card_chunk_plus_one_per_utterance():
    chunks = chunk_tool_card("Creates an offer.", card(), "Create an offer", 4000)

    assert len(chunks) == 4
    assert chunks[0].metadata["chunk_kind"] == "card"
    assert [c.metadata["chunk_kind"] for c in chunks[1:]] == ["utterance"] * 3


def test_every_chunk_carries_the_api_id_and_domain():
    # A chunk that cannot say which API it belongs to is unusable downstream —
    # aggregation drops it, so a card missing this would silently never be
    # selectable.
    for chunk in chunk_tool_card("Body.", card(), "T", 4000):
        assert chunk.metadata["api_id"] == "offers.create"
        assert chunk.metadata["domain"] == "offers"


def test_the_card_chunk_names_the_call_it_describes():
    chunks = chunk_tool_card("Creates an offer.", card(), "Create an offer", 4000)
    assert "POST /v1/merchant/offers" in chunks[0].content
    assert "Creates an offer." in chunks[0].content


def test_an_utterance_chunk_holds_only_the_phrase():
    # It is embedded to be matched against a merchant's own words. Padding it
    # with description would make it match like the card instead.
    chunks = chunk_tool_card("Body.", card(), "T", 4000)
    assert chunks[1].content == "start a sale"


def test_repeated_utterances_are_indexed_once():
    meta = card(utterances=["start a sale", "START A SALE", "  start a sale  ", "other one", "third"])
    chunks = chunk_tool_card("Body.", meta, "T", 4000)
    utterances = [c.content for c in chunks if c.metadata["chunk_kind"] == "utterance"]
    assert utterances == ["start a sale", "other one", "third"]


def test_a_card_too_long_to_keep_whole_is_refused():
    # Splitting would return half a tool: a description with no api_id, or an
    # api_id with no description.
    with pytest.raises(ValueError) as error:
        chunk_tool_card("x" * 500, card(), "Title", 200)
    assert "single chunk" in str(error.value)


def test_a_card_with_no_description_is_refused():
    with pytest.raises(ValueError) as error:
        chunk_tool_card("   \n  ", card(), "Title", 4000)
    assert "no description" in str(error.value)


def test_invalid_front_matter_raises_rather_than_storing_a_broken_card():
    with pytest.raises(ValueError) as error:
        chunk_tool_card("Body.", {"api_id": "offers.create"}, "Title", 4000)
    assert "cannot be stored" in str(error.value)


def test_the_method_is_normalised_to_upper_case():
    chunks = chunk_tool_card("Body.", card(method="post"), "T", 4000)
    assert chunks[0].metadata["method"] == "POST"


@pytest.mark.parametrize("doc_type", ["api", "tool_card"])
def test_both_spellings_of_the_doc_type_reach_the_card_chunker(doc_type):
    chunks = chunk_document("Body.", doc_type, card(), "T", 4000)
    assert chunks[0].metadata["chunk_kind"] == "card"


def test_prose_is_still_chunked_as_prose():
    chunks = chunk_document("# H\n\nSome prose.", "text", None, "T", 4000)
    assert chunks[0].metadata["chunk_type"] == "text"


# ── Aggregation ──────────────────────────────────────────────────────────────

def hit(api_id, similarity, kind="card", domain="offers", content="x"):
    return {
        "chunk_id": f"c-{api_id}-{similarity}",
        "document_id": f"d-{api_id}",
        "document_title": api_id,
        "doc_type": "api",
        "folder_path": f"/{domain}/",
        "chunk_index": 0,
        "content": content,
        "similarity": similarity,
        "metadata": {"api_id": api_id, "domain": domain, "chunk_kind": kind,
                     "method": "POST", "path": "/x"},
    }


def test_several_chunks_of_one_api_collapse_to_a_single_candidate():
    # Otherwise one verbose API would fill every candidate slot with itself.
    candidates = _aggregate_by_api([
        hit("offers.create", 0.81),
        hit("offers.create", 0.88, kind="utterance"),
        hit("offers.create", 0.75, kind="utterance"),
    ])
    assert len(candidates) == 1
    assert candidates[0].score == 0.88
    assert candidates[0].matched_kind == "utterance"


def test_candidates_come_back_strongest_first():
    candidates = _aggregate_by_api([
        hit("a.one", 0.60), hit("b.two", 0.90), hit("c.three", 0.75),
    ])
    assert [c.api_id for c in candidates] == ["b.two", "c.three", "a.one"]


def test_a_chunk_with_no_api_id_is_ignored():
    # A stray prose document in the catalogue knowledge base must never be
    # offered as something to execute.
    stray = hit("x.y", 0.99)
    stray["metadata"] = {"domain": "offers"}
    candidates = _aggregate_by_api([stray, hit("offers.create", 0.70)])
    assert [c.api_id for c in candidates] == ["offers.create"]


def test_required_field_names_are_lifted_out_of_the_contract():
    row = hit("offers.create", 0.9)
    row["metadata"]["fields"] = [
        {"name": "offer_name", "required": True},
        {"name": "note", "required": False},
        {"name": "discount", "required": True},
    ]
    assert _aggregate_by_api([row])[0].required_fields == ["offer_name", "discount"]


def test_the_whole_contract_travels_with_the_candidate():
    # So the caller can start filling the form without a second request.
    row = hit("offers.create", 0.9)
    row["metadata"]["mpin_required"] = True
    candidate = _aggregate_by_api([row])[0]
    assert candidate.mpin_required is True
    assert candidate.contract["path"] == "/x"


# ── Domain ranking ───────────────────────────────────────────────────────────

def test_a_domain_is_scored_by_its_best_api_not_its_average():
    # Averaging punishes a complete domain for the APIs that did not match,
    # so the more thoroughly a domain is documented the worse it would rank.
    candidates = _aggregate_by_api([
        hit("offers.create", 0.90, domain="offers"),
        hit("offers.list", 0.20, domain="offers"),
        hit("offers.update", 0.20, domain="offers"),
        hit("khata.balance.get", 0.55, domain="khata"),
    ])
    ranked = _rank_domains(candidates)
    assert ranked[0]["domain"] == "offers"
    assert ranked[0]["score"] == 0.90


def test_hit_count_breaks_a_tie_between_domains():
    candidates = _aggregate_by_api([
        hit("offers.create", 0.80, domain="offers"),
        hit("offers.list", 0.70, domain="offers"),
        hit("khata.balance.get", 0.80, domain="khata"),
    ])
    assert _rank_domains(candidates)[0]["domain"] == "offers"


def test_every_domain_present_is_ranked():
    candidates = _aggregate_by_api([
        hit("a.one", 0.9, domain="offers"),
        hit("b.two", 0.8, domain="khata"),
        hit("c.three", 0.7, domain="orders"),
    ])
    assert {d["domain"] for d in _rank_domains(candidates)} == {"offers", "khata", "orders"}


# ── The needs line ───────────────────────────────────────────────────────────

FIELDS = [
    {"name": "offer_name", "required": True, "prompt": "?"},
    {"name": "discount_type", "required": True, "prompt": "?",
     "values": ["percentage", "flat"]},
    {"name": "valid_until", "required": False},
    {"name": "min_order_value", "required": False},
]


def test_required_fields_are_described_in_words():
    # Underscores are what stop a field name matching anything a merchant types.
    assert _describe_fields(FIELDS, required=True) == (
        "offer name, discount type (percentage or flat)"
    )


def test_optional_fields_are_described_separately():
    assert _describe_fields(FIELDS, required=False) == "valid until, min order value"


def test_enum_values_are_spelled_out():
    # "flat 100 off" should be able to match; "discount_type" never could.
    assert "(percentage or flat)" in _describe_fields(FIELDS, required=True)


def test_describing_nothing_gives_an_empty_string():
    assert _describe_fields(None, required=True) == ""
    assert _describe_fields([], required=True) == ""
    assert _describe_fields([{"required": True}], required=True) == ""


def test_the_card_chunk_says_what_it_needs():
    chunks = chunk_tool_card("Creates an offer.", card(fields=FIELDS), "Create an offer", 4000)
    content = chunks[0].content
    assert "Needs: offer name, discount type (percentage or flat)." in content
    assert "Optionally: valid until, min order value." in content


def test_a_card_with_no_fields_gets_no_needs_line():
    chunks = chunk_tool_card("Body.", card(fields=[]), "T", 4000)
    assert "Needs:" not in chunks[0].content


def test_utterance_chunks_are_left_alone():
    # Only the card chunk describes fields. An utterance is a merchant phrase and
    # padding it would make it match like a description instead.
    chunks = chunk_tool_card("Body.", card(fields=FIELDS), "T", 4000)
    assert all("Needs:" not in c.content for c in chunks[1:])
