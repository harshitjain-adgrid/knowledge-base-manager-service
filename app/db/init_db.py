import logging
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.database import engine
from app.db.models import TABLE_PREFIX_RE, ControlBase

logger = logging.getLogger(__name__)


class SchemaMismatch(RuntimeError):
    """
    The target tables already store vectors of a different width.

    Not something to repair automatically: the existing vectors were produced by
    a different model and are not comparable with new ones, so the only correct
    answers are "point at empty tables" or "re-ingest", and a human picks which.
    """


# ── Knowledge base tables ───────────────────────────────────────────────────
#
# One pair per knowledge base, in whatever schema the connection lands in, named
# after its registry prefix. Written as explicit DDL rather than create_all
# because the embedding column's width depends on the model that knowledge base
# was created with, and the ORM class carries no fixed size — this is the only
# place the dimension is stated.

_KB_TABLES = """
CREATE TABLE IF NOT EXISTS {prefix}_documents (
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

CREATE TABLE IF NOT EXISTS {prefix}_chunks (
    id          UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES {prefix}_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content     TEXT NOT NULL,
    embedding   VECTOR({dimensions}),
    metadata    JSONB,
    created_at  TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_{prefix}_documents_folder_path
    ON {prefix}_documents (folder_path);

CREATE INDEX IF NOT EXISTS ix_{prefix}_chunks_document_id
    ON {prefix}_chunks (document_id);
"""


def _check_prefix(table_prefix: str) -> str:
    if not TABLE_PREFIX_RE.match(table_prefix):
        raise ValueError(f"'{table_prefix}' is not a usable table prefix.")
    return table_prefix


async def _declared_vector_dimensions(conn, table: str) -> int | None:
    """
    The declared width of a chunks table's embedding column, or None if the
    table does not exist yet.

    format_type renders the type as written, e.g. 'vector(3072)'. Reading
    atttypmod directly would depend on how pgvector chooses to encode it.
    """
    declared = (
        await conn.execute(
            text(
                """
                SELECT format_type(a.atttypid, a.atttypmod)
                FROM pg_attribute a
                WHERE a.attrelid = to_regclass(:table)
                  AND a.attname = 'embedding'
                  AND a.attnum > 0
                  AND NOT a.attisdropped
                """
            ),
            {"table": table},
        )
    ).scalar()

    if declared and "(" in declared:
        try:
            return int(declared.split("(")[1].rstrip(")"))
        except ValueError:
            return None
    return None


async def init_control_db() -> None:
    """Admin users, sessions, and the registry of knowledge bases."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(ControlBase.metadata.create_all)
    logger.info("Control-plane tables created / verified.")


async def init_kb_schema(
    kb_engine: AsyncEngine, table_prefix: str, dimensions: int
) -> None:
    """
    Prepare one knowledge base's tables at the right vector width.

    Safe to call on every startup and whenever a knowledge base is added. Raises
    SchemaMismatch when the tables already hold vectors this knowledge base's
    model cannot read. Empty tables are adapted in place instead — there is
    nothing to invalidate, so changing the model there is free.
    """
    _check_prefix(table_prefix)
    chunks = f"{table_prefix}_chunks"

    async with kb_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        existing = await _declared_vector_dimensions(conn, chunks)
        stored = 0
        if existing is not None:
            stored = (
                await conn.execute(text(f"SELECT count(*) FROM {chunks}"))
            ).scalar() or 0

        if existing is not None and existing != dimensions:
            if stored:
                raise SchemaMismatch(
                    f"{chunks} already holds {stored} {existing}-dimension "
                    f"vectors, but this knowledge base is configured for "
                    f"{dimensions}. Vectors from two different models are not "
                    f"comparable, so mixing them would break retrieval without "
                    f"any error appearing. Point this knowledge base at empty "
                    f"tables, or re-ingest its content."
                )
            await conn.execute(
                text(f"ALTER TABLE {chunks} ALTER COLUMN embedding TYPE vector({dimensions})")
            )
            logger.info(
                f"{chunks} was empty: embedding column changed from {existing} "
                f"to {dimensions} dimensions."
            )

        for statement in _KB_TABLES.format(
            prefix=table_prefix, dimensions=dimensions
        ).split(";"):
            if statement.strip():
                await conn.execute(text(statement))


# ── One-time migration ──────────────────────────────────────────────────────
#
# The service used to give each knowledge base its own schema, with both using
# the same table names. It now uses one schema and a table prefix per knowledge
# base. This moves an existing installation across without touching a single
# row: RENAME and SET SCHEMA are catalogue updates, so no vector is rewritten
# and nothing needs re-embedding.
#
# Idempotent, like every other migration here — it checks what exists before
# acting, so a second startup does nothing.


async def migrate_to_prefixed_tables() -> None:
    """Move pre-prefix installations onto per-knowledge-base table names."""
    async with engine.begin() as conn:
        registry = await conn.execute(
            text("SELECT to_regclass('public.knowledge_bases')")
        )
        if registry.scalar() is None:
            return  # fresh install, nothing to move

        await conn.execute(
            text(
                "ALTER TABLE public.knowledge_bases "
                "ADD COLUMN IF NOT EXISTS table_prefix VARCHAR(64)"
            )
        )

        rows = (
            await conn.execute(
                text("SELECT slug, table_prefix FROM public.knowledge_bases")
            )
        ).all()

        for slug, existing_prefix in rows:
            prefix = existing_prefix or "kb_" + re.sub(r"[^a-z0-9]+", "_", slug.lower()).strip("_")
            _check_prefix(prefix)

            # Where this knowledge base's tables live today: its own schema when
            # one was carved out for it, otherwise public.
            source_schema = "public" if slug == "default" else re.sub(
                r"[^a-z0-9_]+", "_", slug.lower()
            )

            for kind in ("documents", "chunks"):
                target = f"{prefix}_{kind}"
                if (await conn.execute(
                    text("SELECT to_regclass(:t)"), {"t": f"public.{target}"}
                )).scalar() is not None:
                    continue  # already moved

                source = f"{source_schema}.knowledge_{kind}"
                if (await conn.execute(
                    text("SELECT to_regclass(:t)"), {"t": source}
                )).scalar() is None:
                    continue  # nothing there to move

                # Rename inside the source schema first, then move. The other
                # order collides: every knowledge base's tables are called
                # knowledge_documents today, so moving one into public before
                # the one already there has been renamed hits a duplicate.
                await conn.execute(text(f"ALTER TABLE {source} RENAME TO {target}"))

                # Renaming a table leaves its indexes alone, and an index is a
                # relation in the schema namespace just like a table is — so
                # two knowledge_documents_pkey would collide on the move just
                # as the tables would. Renamed by the same substitution, which
                # also lands them on the names init_kb_schema expects, so no
                # duplicate index is created afterwards.
                indexes = (
                    await conn.execute(
                        text(
                            "SELECT indexname FROM pg_indexes "
                            "WHERE schemaname = :s AND tablename = :t"
                        ),
                        {"s": source_schema, "t": target},
                    )
                ).scalars().all()

                for index in indexes:
                    renamed = index.replace(f"knowledge_{kind}", f"{prefix}_{kind}")
                    if renamed != index:
                        await conn.execute(
                            text(f'ALTER INDEX "{source_schema}"."{index}" '
                                 f'RENAME TO "{renamed}"')
                        )

                if source_schema != "public":
                    await conn.execute(
                        text(f'ALTER TABLE "{source_schema}".{target} SET SCHEMA public')
                    )
                logger.info(
                    f"Migrated {source} -> public.{target} "
                    f"({len(indexes)} index(es) renamed with it)"
                )

            await conn.execute(
                text("UPDATE public.knowledge_bases SET table_prefix = :p WHERE slug = :s"),
                {"p": prefix, "s": slug},
            )

        # The ownership marker existed to catch two knowledge bases pointing at
        # one database when their connection strings were spelled differently.
        # A unique table prefix says the same thing more simply.
        for schema, _ in [(r[0], None) for r in (await conn.execute(text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT IN ('pg_catalog','information_schema','pg_toast')"
        ))).all()]:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{schema}".knowledge_base_meta'))

        await conn.execute(
            text(
                "ALTER TABLE public.knowledge_bases "
                "ALTER COLUMN table_prefix SET NOT NULL"
            )
        )
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_knowledge_bases_table_prefix "
                "ON public.knowledge_bases (table_prefix)"
            )
        )

        # Any schema that was created purely to hold one knowledge base is now
        # empty. Dropped without CASCADE on purpose — if anything unexpected is
        # still in there, the drop fails and leaves it alone.
        for slug, _ in rows:
            if slug == "default":
                continue
            schema = re.sub(r"[^a-z0-9_]+", "_", slug.lower())
            try:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" RESTRICT'))
                logger.info(f"Dropped now-empty schema '{schema}'.")
            except Exception as e:
                logger.warning(f"Left schema '{schema}' in place: {e}")


__all__ = [
    "ControlBase",
    "SchemaMismatch",
    "init_control_db",
    "init_kb_schema",
    "migrate_to_prefixed_tables",
]
