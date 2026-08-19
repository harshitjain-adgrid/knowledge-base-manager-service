import asyncio
import logging
import re
import time
from dataclasses import dataclass

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Retry configuration
MAX_RETRIES = 5
RETRY_BASE_DELAY = 1.0  # seconds

# Provider endpoints
FAL_EMBEDDINGS_URL = "https://fal.run/openrouter/router/openai/v1/embeddings"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Roles a piece of text can play in retrieval. Each model expresses these
# differently — see MODEL_SPECS below.
ROLE_DOCUMENT = "document"
ROLE_QUERY = "query"

# ── Embedding model catalogue ───────────────────────────────────────────────
# `task_style` is the important field:
#
#   "task_type"     — gemini-embedding-001 takes a `taskType` request field.
#   "prompt_prefix" — gemini-embedding-2 does NOT support `taskType`. It
#                     accepts the field and returns 200, but silently ignores
#                     it; the task must be expressed as a text prefix instead.
#                     Verified against the live API.
#
# `auto_normalize` records whether the model normalises truncated (<3072)
# outputs itself. gemini-embedding-001 does not — measured norm 0.593 at 768
# dims — so we always normalise locally, which is a no-op for already-unit
# vectors and therefore safe for every model here.
MODEL_SPECS: dict[str, dict] = {
    "gemini-embedding-001": {
        "provider": "gemini",
        "task_style": "task_type",
        "max_dimensions": 3072,
        "allowed_dimensions": [768, 1536, 3072],
        "input_token_limit": 2048,
        "auto_normalize": False,
        "multimodal": False,
    },
    "gemini-embedding-2": {
        "provider": "gemini",
        "task_style": "prompt_prefix",
        "max_dimensions": 3072,
        "allowed_dimensions": [768, 1536, 3072],
        "input_token_limit": 8192,
        "auto_normalize": True,
        "multimodal": True,
    },
    "openai/text-embedding-3-large": {
        "provider": "fal",
        "task_style": "none",
        "max_dimensions": 3072,
        "allowed_dimensions": [256, 1024, 1536, 3072],
        "input_token_limit": 8191,
        "auto_normalize": True,
        "multimodal": False,
    },
    "openai/text-embedding-3-small": {
        "provider": "fal",
        "task_style": "none",
        "max_dimensions": 1536,
        "allowed_dimensions": [512, 1536],
        "input_token_limit": 8191,
        "auto_normalize": True,
        "multimodal": False,
    },
}

# Prefixes for models that carry the task in the prompt (gemini-embedding-2).
# Retrieval is an *asymmetric* task: queries and documents are shaped
# differently. Both sides must stay consistent or similarity scores degrade.
_QUERY_PREFIX = "task: search result | query: "


def get_model_spec(model: str) -> dict:
    """Return the catalogue entry for a model, or a permissive default."""
    spec = MODEL_SPECS.get(model)
    if spec is None:
        logger.warning(
            f"Embedding model '{model}' is not in MODEL_SPECS. "
            f"Falling back to a no-task-type profile."
        )
        return {
            "provider": settings.embedding_provider,
            "task_style": "none",
            # Permissive on purpose: an unknown model is one we have no facts
            # about, so guessing a tight limit would reject valid setups.
            "max_dimensions": 4096,
            "allowed_dimensions": [],
            "input_token_limit": 2048,
            "auto_normalize": False,
            "multimodal": False,
        }
    return spec


def format_for_embedding(
    text: str, role: str, model: str, title: str | None = None
) -> str:
    """
    Shape a piece of text for the given model and retrieval role.

    For `prompt_prefix` models the task instruction lives in the text itself.
    For every other model the text passes through untouched.
    """
    if get_model_spec(model)["task_style"] != "prompt_prefix":
        return text

    if role == ROLE_QUERY:
        return f"{_QUERY_PREFIX}{text}"
    return f"title: {title or 'none'} | text: {text}"


def model_uses_title(model: str) -> bool:
    """
    Whether the document title becomes part of the embedded text for this model.

    When it does, renaming a document invalidates its stored vectors and the
    document has to be re-embedded. When it does not, a rename is free.
    """
    return get_model_spec(model)["task_style"] == "prompt_prefix"


# ────────────────────────────────────────────────────────────────────────────
# Per-knowledge-base embedding configuration
# ────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EmbeddingConfig:
    """
    How one knowledge base embeds its content.

    Every knowledge base picks its own model when it is created, so the model
    can no longer be read from global settings at the point of use — it has to
    travel with the request. The API *key* is deliberately not part of this: keys
    stay in the environment, one per provider, and are never written to the
    registry.
    """

    provider: str
    model: str
    dimensions: int
    batch_size: int = 20
    requests_per_minute: int = 90

    @property
    def normalised_provider(self) -> str:
        return self.provider.lower()


def default_config() -> EmbeddingConfig:
    """The configuration from the environment — the default knowledge base's."""
    return EmbeddingConfig(
        provider=settings.embedding_provider,
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        batch_size=settings.max_embedding_batch_size,
        requests_per_minute=settings.embedding_requests_per_minute,
    )


# Lazily initialised HTTP clients, keyed by provider
_clients: dict[str, httpx.AsyncClient] = {}


# ────────────────────────────────────────────────────────────────────────────
# Rate limiting
# ────────────────────────────────────────────────────────────────────────────

class _RollingRateLimiter:
    """
    Simple rolling-window limiter.

    Gemini's free tier counts *each text* in a batchEmbedContents call against
    the per-minute request quota, so a 100-chunk PDF burns 100 requests. This
    paces calls so we degrade into waiting rather than into 429s.
    """

    def __init__(self, max_per_minute: int):
        self.max_per_minute = max_per_minute
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self, count: int) -> None:
        if self.max_per_minute <= 0:
            return

        async with self._lock:
            while True:
                now = time.monotonic()
                self._timestamps = [t for t in self._timestamps if now - t < 60.0]

                if len(self._timestamps) + count <= self.max_per_minute:
                    self._timestamps.extend([now] * count)
                    return

                # Wait until the oldest timestamp falls out of the window.
                oldest = self._timestamps[0]
                wait = max(0.1, 60.0 - (now - oldest))
                logger.info(
                    f"Embedding rate limit reached "
                    f"({len(self._timestamps)}/{self.max_per_minute} per min). "
                    f"Waiting {wait:.1f}s..."
                )
                await asyncio.sleep(wait)


# One limiter per provider, not per knowledge base: the quota belongs to the
# API key, and every knowledge base on a provider shares that key. When two
# knowledge bases disagree about the rate, the lower one wins — going over is a
# 429 for everybody, going under only costs a little time.
_rate_limiters: dict[str, _RollingRateLimiter] = {}


def _limiter_for(provider: str, requests_per_minute: int) -> _RollingRateLimiter:
    limiter = _rate_limiters.get(provider)
    if limiter is None:
        limiter = _RollingRateLimiter(requests_per_minute)
        _rate_limiters[provider] = limiter
    elif requests_per_minute > 0 and (
        limiter.max_per_minute <= 0 or requests_per_minute < limiter.max_per_minute
    ):
        limiter.max_per_minute = requests_per_minute
    return limiter


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """Extract the server-suggested retry delay from a 429 response."""
    header = response.headers.get("retry-after")
    if header:
        try:
            return float(header)
        except ValueError:
            pass

    try:
        error = response.json().get("error", {})
    except Exception:
        return None

    for detail in error.get("details", []) or []:
        delay = detail.get("retryDelay")
        if isinstance(delay, str) and delay.endswith("s"):
            try:
                return float(delay[:-1])
            except ValueError:
                pass

    match = re.search(r"retry in ([\d.]+)s", error.get("message", ""))
    if match:
        return float(match.group(1))

    return None


# ────────────────────────────────────────────────────────────────────────────
# HTTP clients
# ────────────────────────────────────────────────────────────────────────────

def _get_client(provider: str) -> httpx.AsyncClient:
    """Return the HTTP client for a provider, creating it on first use."""
    if provider not in _clients:
        if provider == "gemini":
            if not settings.gemini_api_key:
                raise RuntimeError(
                    "GEMINI_API_KEY is not set. "
                    "Please set it in your .env file or environment variables."
                )
            _clients[provider] = httpx.AsyncClient(
                base_url=GEMINI_BASE_URL,
                headers={
                    "x-goog-api-key": settings.gemini_api_key,
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )
        elif provider == "fal":
            if not settings.fal_key:
                raise RuntimeError(
                    "FAL_KEY is not set. "
                    "Please set it in your .env file or environment variables."
                )
            _clients[provider] = httpx.AsyncClient(
                headers={
                    "Authorization": f"Key {settings.fal_key}",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )
        else:
            raise RuntimeError(
                f"Unknown EMBEDDING_PROVIDER '{provider}'. Use 'gemini' or 'fal'."
            )

    return _clients[provider]


def validate_embedding_config(config: EmbeddingConfig | None = None) -> None:
    """
    Fail fast on a model/dimension/provider mismatch.

    Called at startup for the environment's configuration, and again whenever a
    knowledge base is created, so a bad combination surfaces immediately rather
    than as a confusing pgvector insert error partway through a large upload.
    """
    config = config or default_config()
    model = config.model
    provider = config.normalised_provider
    spec = get_model_spec(model)
    dims = config.dimensions

    if spec["provider"] != provider and model in MODEL_SPECS:
        raise RuntimeError(
            f"Model '{model}' belongs to provider "
            f"'{spec['provider']}', not '{provider}'."
        )

    if dims > spec["max_dimensions"]:
        raise RuntimeError(
            f"{dims} dimensions exceeds the maximum "
            f"{spec['max_dimensions']} supported by '{model}'."
        )

    if model in MODEL_SPECS and dims not in spec["allowed_dimensions"]:
        logger.warning(
            f"{dims} is not a recommended dimension count for "
            f"'{model}'. Recommended: {spec['allowed_dimensions']}."
        )


def mask_api_key(key: str | None) -> str | None:
    """
    Render a key as a recognisable-but-useless preview, e.g. 'AQ.Ab…9BI-ALw'.

    Enough for an admin to tell which key is loaded; never enough to use.
    The full key is never returned to a client.
    """
    if not key:
        return None
    if len(key) <= 12:
        return "…" * 3
    return f"{key[:5]}…{key[-7:]}"


async def verify_api_key(
    provider: str, api_key: str, model: str | None = None
) -> tuple[bool, str]:
    """
    Check a key against the provider before accepting it.

    Uses a throwaway client so a bad key can never replace a working one, and
    so the live client is untouched if verification fails.
    Returns (ok, message).
    """
    provider = provider.lower()
    if provider != "gemini":
        return False, f"Key verification is only implemented for 'gemini', not '{provider}'."

    model = model or settings.embedding_model
    async with httpx.AsyncClient(base_url=GEMINI_BASE_URL, timeout=30.0) as client:
        try:
            response = await client.post(
                f"/models/{model}:embedContent",
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json={"model": f"models/{model}",
                      "content": {"parts": [{"text": "connectivity check"}]}},
            )
        except httpx.HTTPError as e:
            return False, f"Could not reach the Gemini API: {e}"

    if response.status_code == 200:
        dims = len(response.json()["embedding"]["values"])
        return True, f"Key accepted — {model} responded with {dims} dimensions."

    try:
        detail = response.json()["error"]["message"]
    except Exception:
        detail = response.text[:200]
    if response.status_code in (400, 401, 403):
        return False, f"Key rejected by Gemini: {detail}"
    if response.status_code == 429:
        # The key is valid; it is the quota that is exhausted. Refusing here
        # would block swapping in a key precisely when it is needed.
        return False, f"Quota exceeded for this key: {detail}"
    return False, f"Unexpected response {response.status_code}: {detail}"


async def set_api_key(provider: str, api_key: str) -> None:
    """
    Swap the in-memory key and drop the cached client so the next request
    rebuilds it with the new credentials.
    """
    provider = provider.lower()
    if provider == "gemini":
        settings.gemini_api_key = api_key
    elif provider == "fal":
        settings.fal_key = api_key
    else:
        raise ValueError(f"Unknown provider '{provider}'.")

    client = _clients.pop(provider, None)
    if client is not None:
        await client.aclose()
    logger.info(f"Embedding API key for '{provider}' was replaced at runtime.")


async def close_clients() -> None:
    """Close all open HTTP clients (call on application shutdown)."""
    for client in _clients.values():
        await client.aclose()
    _clients.clear()


# ────────────────────────────────────────────────────────────────────────────
# Gemini provider
# ────────────────────────────────────────────────────────────────────────────

def _normalize(vector: list[float]) -> list[float]:
    """
    L2-normalise a vector.

    gemini-embedding-001 returns unit-length vectors at its native 3072 dims,
    but truncated outputs (768 / 1536) are NOT normalised. Cosine distance in
    pgvector is fine either way, but normalising keeps inner-product and
    cosine consistent and makes stored vectors comparable across dimensions.
    """
    magnitude = sum(v * v for v in vector) ** 0.5
    if magnitude == 0:
        return vector
    return [v / magnitude for v in vector]


async def _gemini_embed(
    texts: list[str], role: str, config: EmbeddingConfig
) -> list[list[float]]:
    """
    Embed a batch of texts via Gemini's batchEmbedContents endpoint.

    Each text is wrapped in its OWN request object. This matters: Gemini
    aggregates multiple *parts* within a single content into one embedding,
    but returns one embedding per *request*. Verified — a 3-request batch
    returns 3 vectors, while a 3-part single content returns 1.
    """
    client = _get_client("gemini")
    model = config.model
    spec = get_model_spec(model)
    url = f"/models/{model}:batchEmbedContents"

    request = {
        "model": f"models/{model}",
        "outputDimensionality": config.dimensions,
    }
    if spec["task_style"] == "task_type":
        request["taskType"] = (
            "RETRIEVAL_QUERY" if role == ROLE_QUERY else "RETRIEVAL_DOCUMENT"
        )

    request_body = {
        "requests": [
            {**request, "content": {"parts": [{"text": text}]}} for text in texts
        ]
    }

    for attempt in range(1, MAX_RETRIES + 1):
        # Gemini counts each text as one request against the per-minute quota.
        await _limiter_for("gemini", config.requests_per_minute).acquire(len(texts))

        try:
            response = await client.post(url, json=request_body)

            if response.status_code == 429 and attempt < MAX_RETRIES:
                delay = _retry_after_seconds(response) or (
                    RETRY_BASE_DELAY * (2 ** attempt)
                )
                logger.warning(
                    f"Gemini rate limited (429). Retrying in {delay:.1f}s "
                    f"(attempt {attempt}/{MAX_RETRIES})..."
                )
                await asyncio.sleep(delay + 1.0)
                continue

            response.raise_for_status()
            embeddings = [item["values"] for item in response.json()["embeddings"]]

            if len(embeddings) != len(texts):
                raise RuntimeError(
                    f"Gemini returned {len(embeddings)} embeddings "
                    f"for {len(texts)} inputs."
                )

            for embedding in embeddings:
                if len(embedding) != config.dimensions:
                    raise RuntimeError(
                        f"Gemini returned a {len(embedding)}-dim vector but this "
                        f"knowledge base stores {config.dimensions}. "
                        f"The pgvector column would reject it."
                    )

            return [_normalize(e) for e in embeddings]

        except Exception as e:
            if attempt == MAX_RETRIES:
                logger.error(
                    f"Gemini embedding API failed after {MAX_RETRIES} attempts: {e}"
                )
                raise

            delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(
                f"Gemini embedding attempt {attempt}/{MAX_RETRIES} failed: {e}. "
                f"Retrying in {delay}s..."
            )
            await asyncio.sleep(delay)

    raise RuntimeError("Embedding generation failed unexpectedly.")


# ────────────────────────────────────────────────────────────────────────────
# fal.ai provider (OpenAI-compatible)
# ────────────────────────────────────────────────────────────────────────────

async def _fal_embed(
    texts: list[str], role: str, config: EmbeddingConfig
) -> list[list[float]]:
    """
    Embed a batch of texts via fal.ai's OpenRouter-proxied OpenAI endpoint.

    fal.ai uses `Authorization: Key <fal_key>` (not Bearer), and the request
    format follows the OpenAI embeddings API spec. `role` is unused — OpenAI
    embeddings have no task-type concept.
    """
    client = _get_client("fal")

    payload = {
        "model": config.model,
        "input": texts,
        "dimensions": config.dimensions,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        await _limiter_for("fal", config.requests_per_minute).acquire(1)

        try:
            response = await client.post(FAL_EMBEDDINGS_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in data["data"]]
        except Exception as e:
            if attempt == MAX_RETRIES:
                logger.error(
                    f"fal.ai embedding API failed after {MAX_RETRIES} attempts: {e}"
                )
                raise

            delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(
                f"fal.ai embedding attempt {attempt}/{MAX_RETRIES} failed: {e}. "
                f"Retrying in {delay}s..."
            )
            await asyncio.sleep(delay)

    raise RuntimeError("Embedding generation failed unexpectedly.")


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────

_PROVIDERS = {
    "gemini": _gemini_embed,
    "fal": _fal_embed,
}


async def _embed(
    texts: list[str], role: str, config: EmbeddingConfig
) -> list[list[float]]:
    provider = config.normalised_provider
    handler = _PROVIDERS.get(provider)
    if handler is None:
        raise RuntimeError(
            f"Unknown embedding provider '{provider}'. "
            f"Supported: {', '.join(_PROVIDERS)}."
        )
    return await handler(texts, role, config)


async def generate_embedding(
    text: str, config: EmbeddingConfig | None = None
) -> list[float]:
    """
    Generate a vector embedding for a single search query.

    `config` says which knowledge base is being searched; without one the
    environment's configuration is used. Returns a list of floats with length =
    config.dimensions.
    """
    config = config or default_config()
    formatted = format_for_embedding(text, ROLE_QUERY, config.model)
    results = await _embed([formatted], ROLE_QUERY, config)
    return results[0]


async def generate_embeddings(
    texts: list[str],
    title: str | None = None,
    config: EmbeddingConfig | None = None,
) -> list[list[float]]:
    """
    Generate vector embeddings for a batch of document chunks.

    `title` is the parent document's title. Models that carry the retrieval
    task in the prompt (gemini-embedding-2) embed it as
    `title: {title} | text: {chunk}`; other models ignore it.

    Automatically splits large batches into smaller requests to stay within
    API limits (max_embedding_batch_size from settings).

    Returns a list of embedding vectors, one per input text.
    """
    if not texts:
        return []

    config = config or default_config()
    model = config.model
    formatted = [
        format_for_embedding(t, ROLE_DOCUMENT, model, title) for t in texts
    ]

    batch_size = config.batch_size
    total_batches = (len(formatted) + batch_size - 1) // batch_size
    all_embeddings: list[list[float]] = []

    for i in range(0, len(formatted), batch_size):
        batch = formatted[i : i + batch_size]
        logger.info(
            f"Generating embeddings via {config.provider} "
            f"({model}) — batch {i // batch_size + 1}"
            f"/{total_batches} ({len(batch)} texts)..."
        )
        all_embeddings.extend(await _embed(batch, ROLE_DOCUMENT, config))

    return all_embeddings
