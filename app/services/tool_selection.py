"""
Turning a merchant's message into the API it asked for.

The problem this solves is not "find relevant text". It is "identify one action
out of hundreds, or admit that you cannot" — a classification problem wearing
retrieval's clothes. That difference drives every decision below.

The shape is: search everything, then narrow. Not the other way round.

Narrowing first — deciding a domain and searching only inside it — is the
obvious design and it has a fatal property: when the router is wrong, the right
answer becomes unreachable, and a ranking error turns into a confident wrong
action. Searching everything first costs microseconds at this size, and it means
the unfiltered ranking is always in hand as the fallback. The domain filter then
does what it is actually good at: removing near-duplicates from unrelated areas
so the margin between first and second place means something.

Nothing here uses keywords, lists of trigger words, or any hand-maintained
mapping. The only inputs are the query vector and the vectors of what authors
wrote. Domains are inferred from where the evidence lands.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import knowledge_service
from app.services.embedding_service import generate_embedding
from app.services.kb_types import KbProfile

logger = logging.getLogger(__name__)


# ── Confidence ───────────────────────────────────────────────────────────────

CONFIDENCE_HIGH = "high"
CONFIDENCE_AMBIGUOUS = "ambiguous"
CONFIDENCE_LOW = "low"


@dataclass
class Candidate:
    """One API that might be what the merchant asked for."""

    api_id: str
    domain: str
    method: str
    path: str
    title: str
    document_id: str
    score: float
    # "utterance" when the best evidence was an example phrase someone wrote,
    # "card" when it was the description. Worth surfacing: an utterance match is
    # a merchant saying almost exactly what another merchant would say.
    matched_kind: str
    matched_text: str
    mpin_required: bool = False
    required_fields: list[str] = field(default_factory=list)
    contract: dict = field(default_factory=dict)


@dataclass
class Resolution:
    """What the pipeline concluded, and enough of why to debug it."""

    query: str
    knowledge_base: str
    candidates: list[Candidate]
    confidence: str
    reason: str
    domains_ranked: list[dict]
    domains_kept: list[str]
    domain_filter_applied: bool
    fallback_used: bool
    top_score: float | None
    margin: float | None
    embed_ms: float
    search_ms: float


# ── Aggregation ──────────────────────────────────────────────────────────────

def _aggregate_by_api(rows: list[dict]) -> list[Candidate]:
    """
    Collapse chunk hits into one entry per API, keeping its best evidence.

    An API is represented by several chunks — one card and one per example
    utterance — so a good match usually returns the same API three or four
    times. Ranking chunks would let a single verbose API crowd out every rival;
    ranking APIs by their single best chunk is both fairer and closer to the
    question being asked.
    """
    best: dict[str, Candidate] = {}

    for row in rows:
        meta = row.get("metadata") or {}
        api_id = str(meta.get("api_id") or "").strip()
        if not api_id:
            # A chunk with no api_id cannot be acted on. Skip it rather than
            # inventing an identity — this is how stray documents in the
            # catalogue knowledge base are ignored instead of being offered.
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
            document_id=row["document_id"],
            score=round(score, 4),
            matched_kind=str(meta.get("chunk_kind") or "card"),
            matched_text=row.get("content") or "",
            mpin_required=bool(meta.get("mpin_required")),
            required_fields=required,
            contract=meta,
        )

    return sorted(best.values(), key=lambda c: c.score, reverse=True)


def _rank_domains(candidates: list[Candidate]) -> list[dict]:
    """
    Score each domain by its strongest API, with the count as a tiebreak.

    Best-of rather than mean-of, deliberately. A domain holding thirty APIs of
    which one is a perfect match should not be punished for the other
    twenty-nine, and averaging does exactly that — the more complete a domain
    is, the worse its mean looks.
    """
    domains: dict[str, dict] = {}
    for candidate in candidates:
        entry = domains.setdefault(
            candidate.domain, {"domain": candidate.domain, "score": 0.0, "hits": 0}
        )
        entry["score"] = max(entry["score"], candidate.score)
        entry["hits"] += 1

    return sorted(
        domains.values(), key=lambda d: (d["score"], d["hits"]), reverse=True
    )


# ── The pipeline ─────────────────────────────────────────────────────────────

async def resolve_action(
    db: AsyncSession,
    profile: KbProfile,
    message: str,
    *,
    top_k: int = 5,
    pool_size: int = 60,
    min_score: float = 0.60,
    decision_margin: float = 0.04,
    domain_margin: float = 0.05,
    max_domains: int = 3,
) -> Resolution:
    """
    Resolve a merchant message to the API it is asking for.

    Deterministic throughout — the only model call is embedding the message.
    Given the same message and the same catalogue this returns the same answer,
    which is what makes it testable and what makes a regression visible.

    Every threshold is a parameter rather than a constant, because the right
    values depend on the catalogue and have to be measured against it.
    """
    import time

    embed_start = time.perf_counter()
    query_vector = await generate_embedding(message, config=profile.embedding)
    embed_ms = (time.perf_counter() - embed_start) * 1000

    # Search the whole catalogue. The pool is deliberately much larger than
    # top_k: it has to be deep enough that the right API is still present after
    # collapsing several chunks per API, and deep enough for the domain ranking
    # to see more than one area.
    search_start = time.perf_counter()
    rows = await knowledge_service.search_similar(
        db=db, query_embedding=query_vector, top_k=pool_size
    )
    search_ms = (time.perf_counter() - search_start) * 1000

    unfiltered = _aggregate_by_api(rows)

    if not unfiltered:
        return Resolution(
            query=message, knowledge_base=profile.slug, candidates=[],
            confidence=CONFIDENCE_LOW,
            reason="Nothing in this catalogue matched at all.",
            domains_ranked=[], domains_kept=[], domain_filter_applied=False,
            fallback_used=False, top_score=None, margin=None,
            embed_ms=round(embed_ms, 1), search_ms=round(search_ms, 1),
        )

    domains_ranked = _rank_domains(unfiltered)

    # Keep every domain whose best API is close to the best overall. One clear
    # winner keeps one domain; a genuinely ambiguous message keeps two or three
    # and lets the ranking below decide between them.
    best_domain_score = domains_ranked[0]["score"]
    kept = [
        d["domain"] for d in domains_ranked
        if d["score"] >= best_domain_score - domain_margin
    ][:max_domains]

    filtered = [c for c in unfiltered if c.domain in kept]

    # The filter is a precision aid, never a gate. Two things make it give way,
    # and both use the unfiltered ranking already computed above — no second
    # query, so the fallback is free.
    #
    # Narrowing to fewer candidates than top_k is the filter succeeding, not
    # failing: a domain with three APIs should return three. What matters is
    # whether anything survived to choose between, and whether the survivors are
    # any good — a filtered set whose best is weak means the domain ranking sent
    # us somewhere wrong, and the wider ranking deserves a look.
    filtered_best = filtered[0].score if filtered else 0.0
    fallback_used = len(filtered) < 2 or filtered_best < min_score
    candidates = (unfiltered if fallback_used else filtered)[:top_k]

    top_score = candidates[0].score
    margin = (
        round(top_score - candidates[1].score, 4) if len(candidates) > 1 else None
    )

    if top_score < min_score:
        confidence = CONFIDENCE_LOW
        reason = (
            f"The closest API scored {top_score:.2f}, below the {min_score:.2f} "
            f"needed to act. Treat this as a question rather than an instruction, "
            f"or ask the merchant what they meant."
        )
    elif margin is not None and margin < decision_margin:
        confidence = CONFIDENCE_AMBIGUOUS
        reason = (
            f"'{candidates[0].api_id}' and '{candidates[1].api_id}' are only "
            f"{margin:.3f} apart. Ask which one before doing anything."
        )
    else:
        confidence = CONFIDENCE_HIGH
        reason = (
            f"'{candidates[0].api_id}' matched at {top_score:.2f}"
            + (f", clear of the next by {margin:.3f}." if margin is not None
               else ", and nothing else came close.")
        )

    logger.info(
        f"resolve '{message[:48]}' -> {candidates[0].api_id} "
        f"({top_score:.3f}, {confidence}, domains={kept}"
        + (", fallback" if fallback_used else "") + ")"
    )

    return Resolution(
        query=message,
        knowledge_base=profile.slug,
        candidates=candidates,
        confidence=confidence,
        reason=reason,
        domains_ranked=domains_ranked,
        domains_kept=kept,
        domain_filter_applied=not fallback_used and len(kept) < len(domains_ranked),
        fallback_used=fallback_used,
        top_score=top_score,
        margin=margin,
        embed_ms=round(embed_ms, 1),
        search_ms=round(search_ms, 1),
    )
