import logging
import uuid
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncEngine,
    AsyncSession,
)

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# The control-plane engine: admin users, sessions, and the knowledge-base
# registry. It is also the default knowledge base's storage, so a single-KB
# deployment only ever uses this one.
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# Read-only variant. A normal session costs three round trips — BEGIN, the
# query, then COMMIT — because SQLAlchemy opens a transaction even for a plain
# SELECT. Over an SSH tunnel at ~220ms per round trip that is 660ms of latency
# to answer a GET. AUTOCOMMIT drops it to one. The pool is shared, so this is
# not a second set of connections.
readonly_engine = engine.execution_options(isolation_level="AUTOCOMMIT")

ReadOnlySessionLocal = async_sessionmaker(
    bind=readonly_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields a transactional session, for writes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_readonly_db() -> AsyncSession:
    """
    Session for endpoints that only read.

    No transaction is opened and nothing is committed, so a read costs a single
    round trip. Using this for a write would leave each statement
    self-committing, so writes must keep using get_db().
    """
    async with ReadOnlySessionLocal() as session:
        yield session


# ────────────────────────────────────────────────────────────────────────────
# Per-knowledge-base engines
# ────────────────────────────────────────────────────────────────────────────
#
# Each registered knowledge base may live on a different Postgres host, so each
# needs its own connection pool. Pools are built on first use and cached, keyed
# by the knowledge base id together with its DSN — pairing the two means that
# editing a connection string retires the old pool instead of silently reusing
# a connection to the previous host.
#
# A knowledge base pointing at DATABASE_URL shares the control-plane pool
# rather than opening a second set of connections to the same database.

_kb_engines: dict[uuid.UUID, tuple[str, AsyncEngine]] = {}


def split_schema(dsn: str) -> tuple[str, str | None]:
    """
    Pull an optional `?schema=` off a connection string.

    Postgres users often cannot create databases — the usual grant is CREATE on
    one schema. Naming a schema lets a knowledge base live beside others on the
    same database without a DBA in the loop, and without any of them being able
    to see each other's tables.

    The name is put on the connection's search_path rather than into every
    query, so the models and SQL stay unqualified and identical everywhere.
    """
    parts = urlsplit(dsn)
    if not parts.query:
        return dsn, None

    params = parse_qsl(parts.query, keep_blank_values=False)
    schema = None
    remaining = []
    for key, value in params:
        if key == "schema":
            schema = value or None
        else:
            remaining.append((key, value))

    if schema is None:
        return dsn, None
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(remaining), "")
    ), schema


async def get_kb_engine(kb_id: uuid.UUID, dsn: str) -> AsyncEngine:
    """Return the engine for a knowledge base, creating its pool on first use."""
    if dsn == settings.database_url:
        return engine

    cached = _kb_engines.get(kb_id)
    if cached is not None:
        cached_dsn, cached_engine = cached
        if cached_dsn == dsn:
            return cached_engine
        # The DSN changed under us; the old pool points at the wrong database.
        await cached_engine.dispose()
        logger.info(f"Connection string changed for knowledge base {kb_id}; rebuilding its pool.")

    # Smaller than the control pool on purpose: there can be many of these, and
    # a knowledge base nobody is looking at should not hold ten connections
    # open on someone else's database.
    url, schema = split_schema(dsn)
    new_engine = create_async_engine(
        url,
        echo=False,
        pool_size=3,
        max_overflow=5,
        pool_pre_ping=True,  # remote hosts and tunnels drop idle connections
        connect_args=(
            # public comes second so the pgvector type resolves, while every
            # table this service creates still lands in the named schema.
            {"server_settings": {"search_path": f"{schema}, public"}}
            if schema
            else {}
        ),
    )
    _kb_engines[kb_id] = (dsn, new_engine)
    return new_engine


def kb_sessionmaker(kb_engine: AsyncEngine) -> async_sessionmaker:
    """Transactional session factory for a knowledge base, for writes."""
    return async_sessionmaker(
        bind=kb_engine, class_=AsyncSession, expire_on_commit=False
    )


def kb_readonly_sessionmaker(kb_engine: AsyncEngine) -> async_sessionmaker:
    """
    Read-only session factory — AUTOCOMMIT, so a SELECT costs one round trip
    instead of BEGIN/SELECT/COMMIT. Writes must not use this.
    """
    return async_sessionmaker(
        bind=kb_engine.execution_options(isolation_level="AUTOCOMMIT"),
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def dispose_kb_engine(kb_id: uuid.UUID) -> None:
    """Close a knowledge base's pool — called when it is deleted or edited."""
    entry = _kb_engines.pop(kb_id, None)
    if entry is not None:
        await entry[1].dispose()


async def dispose_all_engines() -> None:
    """Close every pool. Called on shutdown."""
    for _, kb_engine in _kb_engines.values():
        await kb_engine.dispose()
    _kb_engines.clear()
    await engine.dispose()
