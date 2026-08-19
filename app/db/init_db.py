import logging
import re
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.database import engine
from app.db.models import Base, ControlBase

logger = logging.getLogger(__name__)

_SAFE_SCHEMA_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


# Idempotent schema migrations for the *knowledge base* tables, applied in order
# every time a knowledge base is opened.
#
# There is no Alembic in this project yet, and `create_all` only ever creates
# missing tables — it will not alter one that already exists. These statements
# close that gap. Every one of them must be safe to run against a database that
# has already had it applied.
_MIGRATIONS: list[tuple[str, str]] = [
    (
        "add knowledge_documents.source_format",
        """
        ALTER TABLE knowledge_documents
        ADD COLUMN IF NOT EXISTS source_format VARCHAR(32) NOT NULL DEFAULT 'manual'
        """,
    ),
    (
        "convert doc_type from enum to varchar",
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'knowledge_documents'
                  AND column_name = 'doc_type'
                  AND data_type = 'USER-DEFINED'
            ) THEN
                ALTER TABLE knowledge_documents
                ALTER COLUMN doc_type TYPE VARCHAR(64) USING doc_type::text;
                DROP TYPE IF EXISTS doc_type_enum;
            END IF;
        END $$
        """,
    ),
    (
        "split legacy doc_type='pdf' into doc_type='text' + source_format='pdf'",
        """
        UPDATE knowledge_documents
        SET doc_type = 'text', source_format = 'pdf'
        WHERE doc_type = 'pdf'
        """,
    ),
    (
        "index knowledge_documents.folder_path",
        """
        CREATE INDEX IF NOT EXISTS ix_knowledge_documents_folder_path
        ON knowledge_documents (folder_path)
        """,
    ),
    (
        "index knowledge_chunks.document_id",
        """
        CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_document_id
        ON knowledge_chunks (document_id)
        """,
    ),
]


# The knowledge-base tables are created with explicit DDL rather than
# create_all, because the embedding column's width depends on the model that
# knowledge base was created with. The ORM class carries no fixed size, so this
# is the only place the dimension is stated.
_KB_TABLES = """
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id            UUID PRIMARY KEY,
    title         VARCHAR(512) NOT NULL,
    content       TEXT NOT NULL,
    doc_type      VARCHAR(64) NOT NULL,
    source_format VARCHAR(32) NOT NULL DEFAULT 'manual',
    metadata      JSONB,
    file_name     VARCHAR(512),
    file_size     INTEGER,
    folder_path   VARCHAR(1024) NOT NULL DEFAULT '/',
    created_at    TIMESTAMPTZ NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id          UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content     TEXT NOT NULL,
    embedding   VECTOR({dimensions}),
    metadata    JSONB,
    created_at  TIMESTAMPTZ NOT NULL
);

-- Which knowledge base owns this database, and which embedding space its
-- vectors live in. One row, enforced by the CHECK.
--
-- This is the only reliable way to catch two knowledge bases pointing at the
-- same database: comparing connection strings does not, because
-- localhost:5434 and 127.0.0.1:5434 are the same server spelled two ways. It
-- also catches the mismatch a column width cannot — two models that both
-- produce 3072 dimensions still produce incomparable vectors.
CREATE TABLE IF NOT EXISTS knowledge_base_meta (
    id                   INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    kb_id                UUID NOT NULL,
    kb_slug              VARCHAR(64) NOT NULL,
    embedding_provider   VARCHAR(32) NOT NULL,
    embedding_model      VARCHAR(64) NOT NULL,
    embedding_dimensions INTEGER NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


class SchemaMismatch(RuntimeError):
    """
    The target database already stores vectors of a different width.

    Not something to repair automatically: the existing vectors were produced by
    a different model and are not comparable with new ones, so the only correct
    answers are "point at an empty database" or "re-ingest", and a human picks
    which.
    """


async def init_control_db() -> None:
    """
    Prepare the control-plane database: admin users, sessions, and the registry
    of knowledge bases.
    """
    async with engine.begin() as conn:
        await conn.run_sync(ControlBase.metadata.create_all)
    logger.info("Control-plane tables created / verified.")


async def _ensure_search_path_schema(conn) -> None:
    """
    Create the schema this connection points at, if it names one.

    The name comes from our own validated `?schema=` parameter, never from the
    server, so it cannot carry anything that needs escaping — but it is quoted
    anyway, because DDL built from a string should not depend on that being true.
    """
    search_path = (await conn.execute(text("SHOW search_path"))).scalar() or ""
    first = search_path.split(",")[0].strip().strip('"')

    if not first or first in ("public", "$user"):
        return
    if not _SAFE_SCHEMA_RE.match(first):
        logger.warning(f"Refusing to create schema from search_path {first!r}.")
        return

    await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{first}"'))


async def _declared_vector_dimensions(conn) -> int | None:
    """
    The width of knowledge_chunks.embedding as the database declares it.

    format_type renders the type as written, e.g. 'vector(3072)'. Reading
    atttypmod directly would depend on how pgvector chooses to encode it.
    Returns None when the table or column does not exist yet.
    """
    # Qualified with current_schema() on purpose. The search_path also carries
    # public, so that the pgvector type resolves — which means an unqualified
    # lookup would find public's table and report its width for a knowledge base
    # that has no table of its own yet.
    declared = (
        await conn.execute(
            text(
                """
                SELECT format_type(a.atttypid, a.atttypmod)
                FROM pg_attribute a
                WHERE a.attrelid = to_regclass(
                        quote_ident(current_schema()) || '.knowledge_chunks'
                      )
                  AND a.attname = 'embedding'
                  AND a.attnum > 0
                  AND NOT a.attisdropped
                """
            )
        )
    ).scalar()

    if declared and "(" in declared:
        try:
            return int(declared.split("(")[1].rstrip(")"))
        except ValueError:
            return None
    return None


async def init_kb_schema(
    kb_engine: AsyncEngine,
    dimensions: int,
    *,
    kb_id: uuid.UUID | None = None,
    kb_slug: str = "default",
    provider: str = "",
    model: str = "",
    known_kb_ids: set[uuid.UUID] | None = None,
) -> None:
    """
    Prepare one knowledge base's storage: the pgvector extension, the document
    and chunk tables at the right vector width, the idempotent migrations, and
    the marker row that records which knowledge base owns this database.

    Safe to call on every startup and every time a knowledge base is added.

    Raises SchemaMismatch when the database already belongs to a different
    knowledge base, or already holds vectors this knowledge base's model cannot
    read. An empty database is adapted in place instead — there is nothing to
    invalidate, so changing the model there is free.
    """
    async with kb_engine.begin() as conn:
        # When the connection was pointed at a schema, create it before anything
        # else — every CREATE TABLE below lands there by way of the search_path,
        # and none of them can run until it exists.
        await _ensure_search_path_schema(conn)

        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        existing_dimensions = await _declared_vector_dimensions(conn)
        chunk_count = 0
        if existing_dimensions is not None:
            chunk_count = (
                await conn.execute(text("SELECT count(*) FROM knowledge_chunks"))
            ).scalar() or 0

        if existing_dimensions is not None and existing_dimensions != dimensions:
            if chunk_count:
                raise SchemaMismatch(
                    f"This database already stores {chunk_count} "
                    f"{existing_dimensions}-dimension vectors, but this knowledge "
                    f"base is configured for {dimensions}. Vectors from two "
                    f"different models are not comparable, so mixing them would "
                    f"break retrieval without any error appearing. Point this "
                    f"knowledge base at an empty database, or re-ingest its "
                    f"content."
                )
            # Nothing stored, so nothing to invalidate — widen it in place rather
            # than making someone drop the tables by hand.
            await conn.execute(
                text(f"ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector({dimensions})")
            )
            logger.info(
                f"Empty knowledge base: embedding column changed from "
                f"{existing_dimensions} to {dimensions} dimensions."
            )

        for statement in _KB_TABLES.format(dimensions=dimensions).split(";"):
            if statement.strip():
                await conn.execute(text(statement))

        await _stamp_owner(
            conn,
            kb_id=kb_id,
            kb_slug=kb_slug,
            provider=provider,
            model=model,
            dimensions=dimensions,
            chunk_count=chunk_count,
            known_kb_ids=known_kb_ids,
        )

        for description, statement in _MIGRATIONS:
            try:
                result = await conn.execute(text(statement))
                rowcount = result.rowcount if result.returns_rows is False else -1
                if rowcount > 0:
                    logger.info(f"Migration applied — {description} ({rowcount} rows).")
            except Exception as e:
                # A failing migration must not be swallowed: the schema is now in
                # an unknown state and every later query is suspect.
                logger.error(f"Migration FAILED — {description}: {e}")
                raise


async def _stamp_owner(
    conn,
    *,
    kb_id,
    kb_slug: str,
    provider: str,
    model: str,
    dimensions: int,
    chunk_count: int,
    known_kb_ids: set[uuid.UUID] | None = None,
) -> None:
    """
    Claim this database for one knowledge base, or verify an existing claim.

    Called with kb_id=None by code paths that have no registry row to hand; those
    skip the ownership check rather than writing a claim they cannot honour.

    `known_kb_ids` is every knowledge base the registry currently knows about.
    A claim by an id that is not among them belongs to a knowledge base that has
    since been unregistered, so it is adopted rather than treated as a conflict —
    otherwise removing one by mistake would lock its database out for good.
    """
    if kb_id is None:
        return

    owner = (
        await conn.execute(
            text(
                """
                SELECT kb_id, kb_slug, embedding_model, embedding_dimensions
                FROM knowledge_base_meta WHERE id = 1
                """
            )
        )
    ).first()

    if owner is None:
        await conn.execute(
            text(
                """
                INSERT INTO knowledge_base_meta
                    (id, kb_id, kb_slug, embedding_provider, embedding_model,
                     embedding_dimensions)
                VALUES (1, :kb_id, :slug, :provider, :model, :dimensions)
                """
            ),
            {
                "kb_id": kb_id,
                "slug": kb_slug,
                "provider": provider,
                "model": model,
                "dimensions": dimensions,
            },
        )
        return

    if owner.kb_id != kb_id and known_kb_ids is not None and owner.kb_id not in known_kb_ids:
        logger.info(
            f"Adopting a database last claimed by '{owner.kb_slug}', which is no "
            f"longer registered."
        )
    elif owner.kb_id != kb_id:
        raise SchemaMismatch(
            f"This database is already in use by the knowledge base "
            f"'{owner.kb_slug}'. Two knowledge bases cannot share one, because "
            f"they would share its documents — every upload to either would "
            f"appear in both. Point this one at a different database."
        )

    adopting = owner.kb_id != kb_id
    if model and owner.embedding_model != model and not adopting:
        if chunk_count:
            raise SchemaMismatch(
                f"This database holds {chunk_count} vectors produced by "
                f"'{owner.embedding_model}', but the knowledge base is now "
                f"configured for '{model}'. The two models describe different "
                f"spaces, so searching would return near-random results rather "
                f"than failing. Re-ingest the content, or change the model back."
            )
        # Empty, so the recorded model was never used for anything.
        logger.info(
            f"Empty knowledge base: recorded model changed from "
            f"'{owner.embedding_model}' to '{model}'."
        )

    await conn.execute(
        text(
            """
            UPDATE knowledge_base_meta
            SET kb_slug = :slug,
                embedding_provider = :provider,
                embedding_model = :model,
                embedding_dimensions = :dimensions,
                updated_at = now()
            WHERE id = 1
            """
        ),
        {
            "slug": kb_slug,
            "provider": provider,
            "model": model,
            "dimensions": dimensions,
        },
    )

async def release_kb_claim(kb_engine: AsyncEngine) -> None:
    """
    Drop the ownership marker so this database can be registered again.

    Only the marker: documents and vectors are left exactly as they are. Called
    when a knowledge base is unregistered, because otherwise re-adding the same
    database — after a mistaken removal, say — would be refused forever.
    """
    async with kb_engine.begin() as conn:
        await conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF to_regclass(quote_ident(current_schema()) ||
                                   '.knowledge_base_meta') IS NOT NULL THEN
                        DELETE FROM knowledge_base_meta WHERE id = 1;
                    END IF;
                END $$
                """
            )
        )

async def init_db() -> None:
    """
    Backwards-compatible entry point: prepare the control plane and the default
    knowledge base's tables in the database named by DATABASE_URL.
    """
    from app.config import get_settings

    settings = get_settings()
    await init_control_db()
    await init_kb_schema(engine, settings.embedding_dimensions)
    logger.info("Database initialised.")


# Kept so `Base` stays importable from here, as it was before the control plane
# and knowledge-base metadata were split apart.
__all__ = [
    "Base",
    "ControlBase",
    "init_db",
    "init_control_db",
    "init_kb_schema",
    "release_kb_claim",
    "SchemaMismatch",
]
