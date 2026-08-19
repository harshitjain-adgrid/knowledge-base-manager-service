"""
The registry of knowledge bases.

One knowledge base is a Postgres database with pgvector, plus the embedding
model its vectors were produced with. The two travel together because they have
to: vectors written by one model are meaningless to another, so "which database"
and "which model" is a single decision, made once, when the knowledge base is
created.

The default knowledge base is special in exactly one way — its connection string
and model come from the environment rather than from a row, so DATABASE_URL is
never copied into a table. Everything else about it works like any other.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy import text as sql_text

from app.config import get_settings
from app.db.database import get_kb_engine, split_schema
from app.db.init_db import SchemaMismatch, init_kb_schema, release_kb_claim
from app.db.models import KnowledgeBase
from app.services import crypto_service
from app.services.embedding_service import (
    MODEL_SPECS,
    EmbeddingConfig,
    validate_embedding_config,
)
from app.services.kb_types import KbProfile

logger = logging.getLogger(__name__)
settings = get_settings()

DEFAULT_SLUG = "default"

# Drivers we can actually speak. asyncpg is the only async Postgres driver in
# the dependency set, so anything else would fail later with a confusing import
# error instead of here with a clear one.
_ASYNC_DRIVER = "postgresql+asyncpg"
_ACCEPTED_SCHEMES = {"postgres", "postgresql", "postgresql+asyncpg"}

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$")
# Schema names go into DDL, so they are constrained to something that can never
# need quoting or escaping.
SCHEMA_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


class KbError(ValueError):
    """A problem with a knowledge base's definition, safe to show to an admin."""


# ────────────────────────────────────────────────────────────────────────────
# Connection strings
# ────────────────────────────────────────────────────────────────────────────

def normalise_dsn(raw: str) -> str:
    """
    Accept the connection string an admin is likely to paste and return the one
    SQLAlchemy needs.

    `postgresql://…`, `postgres://…` and `postgresql+asyncpg://…` all mean the
    same host; only the last one works with an async engine, so the first two are
    upgraded rather than rejected.
    """
    raw = (raw or "").strip()
    if not raw:
        raise KbError("A connection string is required.")

    parts = urlsplit(raw)
    if parts.scheme not in _ACCEPTED_SCHEMES:
        raise KbError(
            f"'{parts.scheme or raw[:20]}' is not a Postgres connection string. "
            f"It should look like "
            f"postgresql://user:password@host:5432/database"
        )
    if not parts.hostname:
        raise KbError("The connection string has no host.")
    if not parts.path.strip("/"):
        raise KbError("The connection string has no database name.")

    # `?schema=name` is ours, not libpq's. It exists because a Postgres user is
    # far more likely to hold CREATE on one schema than CREATEDB on the server,
    # and needing a DBA to add a knowledge base would defeat the point of a form.
    query = parse_qsl(parts.query, keep_blank_values=False)
    for key, value in query:
        if key == "schema" and not SCHEMA_RE.match(value):
            raise KbError(
                f"'{value}' is not a valid schema name. Use lowercase letters, "
                f"numbers and underscores, starting with a letter."
            )

    return urlunsplit((_ASYNC_DRIVER, parts.netloc, parts.path, urlencode(query), ""))


def dsn_preview(dsn: str) -> str:
    """
    'user@host:5432/database' — everything except the password.

    This is what the UI shows, so an admin can tell two knowledge bases apart
    without the credentials ever leaving the server.
    """
    url, schema = split_schema(dsn)
    parts = urlsplit(url)
    user = f"{parts.username}@" if parts.username else ""
    port = f":{parts.port}" if parts.port else ""
    suffix = f" (schema {schema})" if schema else ""
    return f"{user}{parts.hostname or '?'}{port}{parts.path}{suffix}"


def resolve_dsn(kb: KnowledgeBase) -> str:
    """
    The connection string for a knowledge base.

    NULL means the default one, which is read from the environment every time
    rather than stored — so rotating the database password is an .env edit and a
    restart, not a database migration.
    """
    if kb.dsn_encrypted is None:
        return settings.database_url
    return crypto_service.decrypt(kb.dsn_encrypted)


async def test_connection(dsn: str) -> tuple[bool, str]:
    """
    Open a throwaway connection and report what happened, in words an admin can
    act on.

    Deliberately not reusing a pooled engine: this runs before a knowledge base
    exists, and a failed attempt should leave nothing behind.
    """
    url, schema = split_schema(dsn)
    probe: AsyncEngine | None = None
    try:
        probe = create_async_engine(
            url,
            pool_pre_ping=True,
            pool_size=1,
            max_overflow=0,
            connect_args=(
                {"server_settings": {"search_path": f"{schema}, public"}}
                if schema
                else {}
            ),
        )
        async with probe.connect() as conn:
            version = (await conn.execute(sql_text("SELECT version()"))).scalar()
            has_vector = (
                await conn.execute(
                    sql_text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
                )
            ).scalar()
            installed = (
                await conn.execute(
                    sql_text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
                )
            ).scalar()

        server = (version or "PostgreSQL").split(" on ")[0]
        where = f" (schema {schema})" if schema else ""
        if installed:
            return True, f"Connected — {server}, pgvector {installed} installed.{where}"
        if has_vector:
            return True, (
                f"Connected — {server}. pgvector is available and will be "
                f"enabled.{where}"
            )
        return False, (
            f"Connected to {server}, but the pgvector extension is not available "
            f"on this server. Install it before using this database as a "
            f"knowledge base."
        )
    except Exception as e:
        return False, _connection_error_message(e)
    finally:
        if probe is not None:
            await probe.dispose()


def _connection_error_message(error: Exception) -> str:
    """Turn a driver exception into something an admin can act on."""
    detail = str(error).strip() or error.__class__.__name__
    lowered = detail.lower()

    if "password authentication failed" in lowered or "role" in lowered and "does not exist" in lowered:
        return f"Rejected by the server: {detail}"
    if "does not exist" in lowered and "database" in lowered:
        return f"That database does not exist on the server: {detail}"
    if "timeout" in lowered or "timed out" in lowered:
        return (
            f"Timed out reaching the host. If it is only reachable through an "
            f"SSH tunnel, the tunnel has to be running on this machine and the "
            f"connection string should point at the local end of it. ({detail})"
        )
    if "connection refused" in lowered or "connect call failed" in lowered:
        return (
            f"Nothing is listening there. Check the host and port, and that "
            f"Postgres accepts connections from this machine. ({detail})"
        )
    return detail


# ────────────────────────────────────────────────────────────────────────────
# Profiles and engines
# ────────────────────────────────────────────────────────────────────────────

def profile_for(kb: KnowledgeBase) -> KbProfile:
    """The chunking and embedding settings that belong to this knowledge base."""
    return KbProfile(
        id=kb.id,
        slug=kb.slug,
        name=kb.name,
        embedding=EmbeddingConfig(
            provider=kb.embedding_provider,
            model=kb.embedding_model,
            dimensions=kb.embedding_dimensions,
            batch_size=settings.max_embedding_batch_size,
            requests_per_minute=settings.embedding_requests_per_minute,
        ),
        chunk_size=kb.chunk_size,
        chunk_overlap=kb.chunk_overlap,
    )


async def engine_for(kb: KnowledgeBase) -> AsyncEngine:
    """The connection pool for a knowledge base, created on first use."""
    return await get_kb_engine(kb.id, resolve_dsn(kb))


# ────────────────────────────────────────────────────────────────────────────
# Registry reads
# ────────────────────────────────────────────────────────────────────────────

async def list_kbs(db: AsyncSession) -> list[KnowledgeBase]:
    result = await db.execute(
        select(KnowledgeBase).order_by(
            KnowledgeBase.is_default.desc(), KnowledgeBase.name
        )
    )
    return list(result.scalars().all())


async def get_by_slug(db: AsyncSession, slug: str) -> KnowledgeBase | None:
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.slug == slug))
    return result.scalar_one_or_none()


async def get_default(db: AsyncSession) -> KnowledgeBase | None:
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.is_default.is_(True))
    )
    return result.scalars().first()


# ────────────────────────────────────────────────────────────────────────────
# Registry writes
# ────────────────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return slug[:64].strip("-") or "kb"


def validate_model_choice(provider: str, model: str, dimensions: int) -> None:
    """
    Refuse a combination that cannot work, before anything is written.

    The check is the same one the service runs against its own environment at
    startup — a knowledge base created through the UI gets no weaker guarantees
    than one configured by hand.
    """
    spec = MODEL_SPECS.get(model)
    if spec is None:
        raise KbError(
            f"'{model}' is not a known embedding model. Choose one of: "
            f"{', '.join(sorted(MODEL_SPECS))}."
        )
    if spec["provider"] != provider.lower():
        raise KbError(
            f"'{model}' is a {spec['provider']} model, but the provider given "
            f"was '{provider}'."
        )
    if spec["allowed_dimensions"] and dimensions not in spec["allowed_dimensions"]:
        raise KbError(
            f"{dimensions} dimensions is not supported by '{model}'. "
            f"Supported: {', '.join(str(d) for d in spec['allowed_dimensions'])}."
        )

    key = settings.gemini_api_key if spec["provider"] == "gemini" else settings.fal_key
    if not key:
        env_name = "GEMINI_API_KEY" if spec["provider"] == "gemini" else "FAL_KEY"
        raise KbError(
            f"'{model}' needs a {spec['provider']} API key, and {env_name} is not "
            f"set on this server. API keys are read from the environment, not "
            f"stored per knowledge base."
        )

    validate_embedding_config(
        EmbeddingConfig(provider=provider, model=model, dimensions=dimensions)
    )


async def create_kb(
    db: AsyncSession,
    *,
    name: str,
    dsn: str,
    embedding_provider: str,
    embedding_model: str,
    embedding_dimensions: int,
    slug: str | None = None,
    description: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> KnowledgeBase:
    """
    Register a knowledge base and prepare its schema.

    The order matters: validate, then connect, then create the tables, and only
    then write the row. A knowledge base that appears in the list is one that has
    been proven to work — an admin should never have to wonder whether a row in
    the registry is real.
    """
    name = (name or "").strip()
    if not name:
        raise KbError("A name is required.")

    validate_model_choice(embedding_provider, embedding_model, embedding_dimensions)

    slug = (slug or slugify(name)).strip().lower()
    if not SLUG_RE.match(slug):
        raise KbError(
            "The identifier must be lowercase letters, numbers and hyphens, "
            "starting and ending with a letter or number."
        )
    if await get_by_slug(db, slug) is not None:
        raise KbError(f"A knowledge base with the identifier '{slug}' already exists.")

    normalised = normalise_dsn(dsn)

    if normalised == settings.database_url:
        raise KbError(
            "That is this service's own database, which is already the default "
            "knowledge base. Point this one at a different database."
        )

    # Two knowledge bases sharing a database would share its tables, and every
    # document would appear in both. Compared after decryption because the
    # stored form is ciphertext and no two encryptions of the same string match.
    registered = await list_kbs(db)
    known_ids = {existing.id for existing in registered}
    for existing in registered:
        try:
            if resolve_dsn(existing) == normalised:
                raise KbError(
                    f"'{existing.name}' already uses that database. Two knowledge "
                    f"bases cannot share one, because they would share its "
                    f"documents."
                )
        except crypto_service.SecretsUnavailable:
            # Cannot read that one's DSN to compare. Not a reason to block this
            # create; the unreadable one is already broken and says so elsewhere.
            continue

    if not crypto_service.is_available():
        raise KbError(
            "SECRET_KEY is not set on the server, so a connection string cannot "
            "be stored safely. Add one to .env and restart:\n"
            '    python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )

    ok, message = await test_connection(normalised)
    if not ok:
        raise KbError(message)

    kb = KnowledgeBase(
        slug=slug,
        name=name,
        description=(description or "").strip() or None,
        dsn_encrypted=crypto_service.encrypt(normalised),
        dsn_preview=dsn_preview(normalised),
        embedding_provider=embedding_provider.lower(),
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
        chunk_size=chunk_size or settings.chunk_size,
        chunk_overlap=chunk_overlap if chunk_overlap is not None else settings.chunk_overlap,
        is_default=False,
        is_active=True,
        last_checked_at=datetime.now(timezone.utc),
    )
    db.add(kb)
    await db.flush()

    # Create the tables at the right vector width before the row is committed,
    # so a schema clash fails the whole request rather than leaving a registered
    # knowledge base that cannot store anything.
    kb_engine = await get_kb_engine(kb.id, normalised)
    try:
        await init_kb_schema(
            kb_engine,
            embedding_dimensions,
            kb_id=kb.id,
            kb_slug=slug,
            provider=embedding_provider.lower(),
            model=embedding_model,
            known_kb_ids=known_ids,
        )
    except SchemaMismatch as e:
        raise KbError(str(e))

    logger.info(
        f"Registered knowledge base '{slug}' ({embedding_model}, "
        f"{embedding_dimensions} dims) at {kb.dsn_preview}."
    )
    return kb


async def update_kb(
    db: AsyncSession,
    kb: KnowledgeBase,
    *,
    name: str | None = None,
    description: str | None = None,
    is_active: bool | None = None,
    make_default: bool = False,
    dsn: str | None = None,
) -> KnowledgeBase:
    """
    Edit the things that are safe to edit.

    Provider, model and dimensions are not among them. Changing any of those
    would leave the stored vectors describing one embedding space and new ones
    describing another, with no error anywhere — retrieval would just quietly get
    worse. That is a re-ingest, not a form field.
    """
    if name is not None:
        name = name.strip()
        if not name:
            raise KbError("A name is required.")
        kb.name = name
    if description is not None:
        kb.description = description.strip() or None
    if is_active is not None:
        if kb.is_default and not is_active:
            raise KbError("The default knowledge base cannot be deactivated.")
        kb.is_active = is_active

    if dsn is not None:
        if kb.is_default:
            raise KbError(
                "The default knowledge base's connection string comes from "
                "DATABASE_URL in the server's environment, so it is changed "
                "there rather than here."
            )
        if not crypto_service.is_available():
            raise KbError("SECRET_KEY is not set, so a connection string cannot be stored.")
        normalised = normalise_dsn(dsn)
        ok, message = await test_connection(normalised)
        if not ok:
            raise KbError(message)
        kb.dsn_encrypted = crypto_service.encrypt(normalised)
        kb.dsn_preview = dsn_preview(normalised)
        kb.last_error = None
        kb.last_checked_at = datetime.now(timezone.utc)

        kb_engine = await get_kb_engine(kb.id, normalised)
        try:
            await init_kb_schema(
                kb_engine,
                kb.embedding_dimensions,
                kb_id=kb.id,
                kb_slug=kb.slug,
                provider=kb.embedding_provider,
                model=kb.embedding_model,
            )
        except SchemaMismatch as e:
            raise KbError(str(e))

    if make_default:
        if not kb.is_active:
            raise KbError("An inactive knowledge base cannot be made the default.")
        for other in await list_kbs(db):
            other.is_default = other.id == kb.id
        kb.is_default = True

    kb.updated_at = datetime.now(timezone.utc)
    return kb


async def delete_kb(db: AsyncSession, kb: KnowledgeBase) -> None:
    """
    Remove a knowledge base from the registry.

    Its documents and vectors are left exactly where they are. Dropping tables on
    someone else's database because a row was deleted here would be far too much
    to do on a DELETE — unregistering is reversible, and deleting data is not.
    """
    if kb.is_default:
        raise KbError(
            "The default knowledge base cannot be removed. Make another one the "
            "default first."
        )

    # Hand the database back before forgetting how to reach it, so registering
    # it again later is possible. Best effort: an unreachable host is not a
    # reason to refuse to unregister, and the stale claim is adopted on the way
    # back in anyway.
    try:
        await release_kb_claim(await engine_for(kb))
    except Exception as e:
        logger.warning(
            f"Could not release the ownership marker for '{kb.slug}': {e}. "
            f"Re-registering that database will adopt the stale claim."
        )

    await db.delete(kb)
    logger.info(
        f"Unregistered knowledge base '{kb.slug}'. Its data at {kb.dsn_preview} "
        f"was left untouched."
    )


# ────────────────────────────────────────────────────────────────────────────
# Bootstrap
# ────────────────────────────────────────────────────────────────────────────

async def ensure_default_kb(db: AsyncSession) -> KnowledgeBase:
    """
    Make sure the knowledge base this service started with is in the registry.

    Its model and dimensions are refreshed from the environment on every start,
    because that is where they have always been configured and changing .env
    should keep working exactly as it did. Additional knowledge bases are the
    other way round — the registry is authoritative for those.
    """
    kb = await get_default(db)
    if kb is None:
        kb = await get_by_slug(db, DEFAULT_SLUG)

    if kb is None:
        kb = KnowledgeBase(
            slug=DEFAULT_SLUG,
            name="Primary knowledge base",
            description="The knowledge base configured in the server's environment.",
            dsn_encrypted=None,  # read from DATABASE_URL, never stored
            dsn_preview=dsn_preview(settings.database_url),
            embedding_provider=settings.embedding_provider.lower(),
            embedding_model=settings.embedding_model,
            embedding_dimensions=settings.embedding_dimensions,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            is_default=True,
            is_active=True,
        )
        db.add(kb)
        await db.flush()
        logger.info("Registered the environment's knowledge base as the default.")
        return kb

    # Keep the row in step with the environment it mirrors.
    kb.dsn_encrypted = None
    kb.dsn_preview = dsn_preview(settings.database_url)
    kb.embedding_provider = settings.embedding_provider.lower()
    kb.embedding_model = settings.embedding_model
    kb.embedding_dimensions = settings.embedding_dimensions
    kb.chunk_size = settings.chunk_size
    kb.chunk_overlap = settings.chunk_overlap
    kb.is_default = True
    kb.is_active = True
    return kb


async def recheck(db: AsyncSession, kb: KnowledgeBase) -> tuple[bool, str]:
    """
    Reach a registered knowledge base again and record the result.

    Without this, a knowledge base marked unreachable at startup stays marked
    that way until the next restart, even once the host is back — a stale
    warning that an admin has no way to clear.
    """
    try:
        dsn = resolve_dsn(kb)
    except crypto_service.SecretsUnavailable as e:
        kb.last_error = str(e)[:1000]
        kb.last_checked_at = datetime.now(timezone.utc)
        return False, str(e)

    ok, message = await test_connection(dsn)
    kb.last_error = None if ok else message[:1000]
    kb.last_checked_at = datetime.now(timezone.utc)
    return ok, message


def available_models() -> list[dict]:
    """The embedding models the create form can offer, with their constraints."""
    return [
        {
            "model": model,
            "provider": spec["provider"],
            "allowed_dimensions": spec["allowed_dimensions"] or [spec["max_dimensions"]],
            "default_dimensions": spec["max_dimensions"],
            "input_token_limit": spec["input_token_limit"],
            "multimodal": spec["multimodal"],
            "key_configured": bool(
                settings.gemini_api_key
                if spec["provider"] == "gemini"
                else settings.fal_key
            ),
        }
        for model, spec in sorted(MODEL_SPECS.items())
    ]
