"""
Turning chunk hits into a decision about which API was asked for.

This lives in the evaluation tooling, not in the service. The knowledge base
stores and retrieves; deciding what to do with a retrieval — and calling
anything — belongs to the orchestrator, which is a separate system.

What it is for here is measurement: given a labelled set of merchant messages,
does the catalogue retrieve the right API? That question is an internal-team
question, and answering it needs the same collapsing and ranking the
orchestrator will do, so the logic sits beside the evaluation that uses it.

It is also the clearest available description of the shape, for whoever builds
the orchestrator. Everything below is deterministic — the only model call is the
one `/search` already made to embed the query.
"""

from dataclasses import dataclass, field

CONFIDENCE_HIGH = "high"
CONFIDENCE_AMBIGUOUS = "ambiguous"
CONFIDENCE_LOW = "low"

# Calibrated against the seed catalogue; see BASELINE.md for the sweep.
DEFAULT_MIN_SCORE = 0.65
DEFAULT_DECISION_MARGIN = 0.02
DEFAULT_DOMAIN_MARGIN = 0.05
DEFAULT_MAX_DOMAINS = 3
DEFAULT_POOL_SIZE = 60


@dataclass
class Candidate:
    api_id: str
    domain: str
    method: str
    path: str
    title: str
    score: float
    # "utterance" when the best evidence was an example phrase someone wrote,
    # "card" when it was the description.
    matched_kind: str
    matched_text: str
    mpin_required: bool = False
    required_fields: list = field(default_factory=list)
    contract: dict = field(default_factory=dict)


@dataclass
class Decision:
    candidates: list
    confidence: str
    reason: str
    domains_ranked: list
    domains_kept: list
    fallback_used: bool
    top_score: float | None
    margin: float | None


def aggregate_by_api(rows: list) -> list:
    """
    Collapse chunk hits into one entry per API, keeping its best evidence.

    An API is several chunks — one card and one per example utterance — so a
    good match returns the same API three or four times. Ranking chunks would
    let one verbose API fill every slot with itself; ranking APIs by their single
    best chunk is both fairer and closer to the question being asked.
    """
    best = {}

    for row in rows:
        meta = row.get("metadata") or {}
        api_id = str(meta.get("api_id") or "").strip()
        if not api_id:
            # A chunk with no api_id cannot be acted on. Skipped rather than
            # given an invented identity — this is how a stray prose document in
            # the catalogue is ignored instead of offered as something to call.
            continue

        score = float(row["similarity"])
        current = best.get(api_id)
        if current is not None and current.score >= score:
            continue

        fields = meta.get("fields")
        required = [
            str(f.get("name"))
            for f in (fields if isinstance(fields, list) else [])
            if isinstance(f, dict) and f.get("required") and f.get("name")
        ]

        best[api_id] = Candidate(
            api_id=api_id,
            domain=str(meta.get("domain") or "").strip() or "unknown",
            method=str(meta.get("method") or "").strip().upper(),
            path=str(meta.get("path") or "").strip(),
            title=row.get("document_title") or api_id,
            score=round(score, 4),
            matched_kind=str(meta.get("chunk_kind") or "card"),
            matched_text=row.get("content") or "",
            mpin_required=bool(meta.get("mpin_required")),
            required_fields=required,
            contract=meta,
        )

    return sorted(best.values(), key=lambda c: c.score, reverse=True)


def rank_domains(candidates: list) -> list:
    """
    Score each domain by its strongest API, with the hit count as a tiebreak.

    Best-of rather than mean-of, deliberately. A domain holding thirty APIs of
    which one matches perfectly should not be punished for the other
    twenty-nine, and averaging does exactly that — the more complete a domain is,
    the worse its mean looks.
    """
    domains = {}
    for candidate in candidates:
        entry = domains.setdefault(
            candidate.domain, {"domain": candidate.domain, "score": 0.0, "hits": 0}
        )
        entry["score"] = max(entry["score"], candidate.score)
        entry["hits"] += 1

    return sorted(domains.values(), key=lambda d: (d["score"], d["hits"]), reverse=True)


def decide(
    rows: list,
    *,
    top_k: int = 5,
    min_score: float = DEFAULT_MIN_SCORE,
    decision_margin: float = DEFAULT_DECISION_MARGIN,
    domain_margin: float = DEFAULT_DOMAIN_MARGIN,
    max_domains: int = DEFAULT_MAX_DOMAINS,
) -> Decision:
    """
    Search everything, then narrow. Not the other way round.

    Narrowing first — picking a domain and searching only inside it — is the
    obvious design and it has a fatal property: when the domain is wrong, the
    right API becomes unreachable, and a ranking error turns into a confident
    wrong action. Searching everything first costs microseconds at this size and
    leaves the unfiltered ranking in hand as a free fallback. The domain filter
    then does what it is good at: removing near-duplicates from unrelated areas
    so the gap between first and second place means something.

    No keywords, no trigger lists, no hand-maintained mapping. Domains are
    inferred from where the evidence lands.
    """
    unfiltered = aggregate_by_api(rows)

    if not unfiltered:
        return Decision([], CONFIDENCE_LOW, "Nothing in the catalogue matched at all.",
                        [], [], False, None, None)

    domains_ranked = rank_domains(unfiltered)
    best_domain = domains_ranked[0]["score"]
    kept = [
        d["domain"] for d in domains_ranked
        if d["score"] >= best_domain - domain_margin
    ][:max_domains]

    filtered = [c for c in unfiltered if c.domain in kept]

    # The filter is a precision aid, never a gate. Narrowing to fewer candidates
    # than top_k is it succeeding, not failing — a domain with three APIs should
    # return three. What matters is whether anything survived to choose between,
    # and whether the survivors are any good.
    filtered_best = filtered[0].score if filtered else 0.0
    fallback_used = len(filtered) < 2 or filtered_best < min_score
    candidates = (unfiltered if fallback_used else filtered)[:top_k]

    top_score = candidates[0].score
    margin = round(top_score - candidates[1].score, 4) if len(candidates) > 1 else None

    if top_score < min_score:
        confidence = CONFIDENCE_LOW
        reason = (f"The closest API scored {top_score:.2f}, below the "
                  f"{min_score:.2f} needed to act.")
    elif margin is not None and margin < decision_margin:
        confidence = CONFIDENCE_AMBIGUOUS
        reason = (f"'{candidates[0].api_id}' and '{candidates[1].api_id}' are only "
                  f"{margin:.3f} apart. Ask which one before doing anything.")
    else:
        confidence = CONFIDENCE_HIGH
        reason = (f"'{candidates[0].api_id}' matched at {top_score:.2f}"
                  + (f", clear of the next by {margin:.3f}." if margin is not None
                     else ", and nothing else came close."))

    return Decision(candidates, confidence, reason, domains_ranked, kept,
                    fallback_used, top_score, margin)
