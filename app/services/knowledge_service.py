import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, delete, or_, text
from sqlalchemy.orm import noload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.chunking_service import chunk_document
from app.services.embedding_service import generate_embeddings, model_uses_title
from app.services.kb_types import KbProfile, default_profile

settings = get_settings()

logger = logging.getLogger(__name__)


async def add_document(
    db: AsyncSession,
    title: str,
    content: str,
    doc_type: str,
    metadata: dict | None = None,
    file_name: str | None = None,
    file_size: int | None = None,
    folder_path: str = "/",
    source_format: str = "manual",
    profile: KbProfile | None = None,
) -> tuple:
    """
    Add a new document to the knowledge base.

    Flow: save document → chunk it → embed chunks → store chunks with embeddings.

    `profile` says which knowledge base is being written to — its chunk sizes
    and its embedding model. Omitting it uses the environment's settings, which
    is the default knowledge base's configuration.

    Returns (document, chunk_count) to avoid stale relationship issues.
    """
    profile = profile or default_profile()
    KnowledgeDocument, KnowledgeChunk = profile.tables

    # 1. Create the document record
    document = KnowledgeDocument(
        title=title,
        content=content,
        doc_type=doc_type,
        metadata_=metadata or {},
        file_name=file_name,
        file_size=file_size,
        folder_path=normalize_folder_path(folder_path),
        source_format=source_format,
    )
    db.add(document)
    await db.flush()  # Get the generated ID without committing

    # 2. Chunk the document
    chunks = chunk_document(
        content, doc_type, metadata, doc_title=title,
        max_size=profile.chunk_size, overlap=profile.chunk_overlap,
    )

    if not chunks:
        # Storing this would create a document nothing can ever retrieve, with
        # no error at the point the admin created it. Refuse instead.
        raise ValueError(
            f"'{title}' produced no chunks, so nothing about it would be "
            f"retrievable. The content is empty or contains no extractable text."
        )

    # 3. Generate embeddings for all chunks in batch
    chunk_texts = [c.content for c in chunks]
    embeddings = await generate_embeddings(
        chunk_texts, title=document.title, config=profile.embedding
    )

    # 4. Create chunk records with embeddings
    for chunk, embedding in zip(chunks, embeddings):
        db_chunk = KnowledgeChunk(
            document_id=document.id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            embedding=embedding,
            metadata_=chunk.metadata,
        )
        db.add(db_chunk)

    chunk_count = len(chunks)
    logger.info(
        f"Added document '{title}' (id={document.id}) with {chunk_count} chunks."
    )
    return document, chunk_count


async def update_document(
    db: AsyncSession,
    document_id: uuid.UUID,
    title: str | None = None,
    content: str | None = None,
    doc_type: str | None = None,
    metadata: dict | None = None,
    folder_path: str | None = None,
    profile: KbProfile | None = None,
) -> tuple:
    """
    Update an existing document. If content or doc_type changes,
    re-chunk and re-embed everything.

    Returns (document, chunk_count) to avoid stale relationship issues.
    """
    profile = profile or default_profile()
    KnowledgeDocument, KnowledgeChunk = profile.tables

    # Fetch existing document
    document = await db.get(KnowledgeDocument, document_id)
    if not document:
        raise ValueError(f"Document with id {document_id} not found.")

    content_changed = False

    if title is not None and title != document.title:
        document.title = title
        # Some models (gemini-embedding-2 among them) fold the document title
        # into the embedded text, so a title change makes their vectors stale.
        # For models that do not, a rename is free.
        if model_uses_title(profile.model):
            content_changed = True
    if content is not None and content != document.content:
        document.content = content
        content_changed = True
    if doc_type is not None and doc_type != document.doc_type:
        document.doc_type = doc_type
        content_changed = True
    if metadata is not None:
        # Merged, not replaced — replace/append/upload all merge, and a PUT that
        # silently dropped every key it did not mention lost data quietly.
        document.metadata_ = {**(document.metadata_ or {}), **metadata}
    if folder_path is not None:
        document.folder_path = normalize_folder_path(folder_path)

    document.updated_at = datetime.now(timezone.utc)

    # If content or type changed, re-chunk and re-embed
    if content_changed:
        # Delete old chunks
        await db.execute(
            delete(KnowledgeChunk).where(
                KnowledgeChunk.document_id == document_id
            )
        )

        # Re-chunk
        effective_content = content if content is not None else document.content
        effective_type = doc_type if doc_type is not None else document.doc_type
        effective_meta = document.metadata_
        chunks = chunk_document(
            effective_content, effective_type, effective_meta,
            doc_title=document.title,
            max_size=profile.chunk_size, overlap=profile.chunk_overlap,
        )

        # Re-embed
        chunk_texts = [c.content for c in chunks]
        embeddings = await generate_embeddings(
            chunk_texts, title=document.title, config=profile.embedding
        )

        # Create new chunks
        for chunk, embedding in zip(chunks, embeddings):
            db_chunk = KnowledgeChunk(
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                embedding=embedding,
                metadata_=chunk.metadata,
            )
            db.add(db_chunk)

        chunk_count = len(chunks)
        logger.info(
            f"Updated document '{document.title}' (id={document_id}) — "
            f"re-chunked into {chunk_count} chunks."
        )
    else:
        # Count existing chunks
        count_result = await db.execute(
            select(func.count(KnowledgeChunk.id)).where(
                KnowledgeChunk.document_id == document_id
            )
        )
        chunk_count = count_result.scalar() or 0

        logger.info(
            f"Updated document '{document.title}' (id={document_id}) — "
            f"metadata only, no re-chunking needed."
        )

    return document, chunk_count


async def delete_document(
    db: AsyncSession, document_id: uuid.UUID, profile: KbProfile | None = None
) -> bool:
    """
    Delete a document and all its chunks (cascaded via FK).
    Returns True if document existed and was deleted.
    """
    profile = profile or default_profile()
    KnowledgeDocument, KnowledgeChunk = profile.tables

    document = await db.get(KnowledgeDocument, document_id)
    if not document:
        return False

    await db.delete(document)
    logger.info(f"Deleted document (id={document_id}) and all its chunks.")
    return True


async def get_document(
    db: AsyncSession, document_id: uuid.UUID, profile: KbProfile | None = None
):
    """Fetch a single document with its chunks."""
    profile = profile or default_profile()
    KnowledgeDocument, KnowledgeChunk = profile.tables

    return await db.get(KnowledgeDocument, document_id)


async def list_documents(
    db: AsyncSession,
    profile: KbProfile | None = None,
    doc_type: str | None = None,
    search: str | None = None,
    folder: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list, int]:
    """
    List documents with optional filtering, keyword search, and pagination.
    Returns (documents, total_count).
    """
    profile = profile or default_profile()
    KnowledgeDocument, KnowledgeChunk = profile.tables

    # Base query. noload() on chunks is essential: the relationship is
    # lazy="selectin", so without it every listed document would pull in all of
    # its chunks and their embeddings — megabytes of vectors to render a table.
    query = (
        select(KnowledgeDocument)
        .options(noload(KnowledgeDocument.chunks))
        .order_by(KnowledgeDocument.created_at.desc())
    )
    count_query = select(func.count(KnowledgeDocument.id))

    # Apply type filter
    if doc_type:
        query = query.where(KnowledgeDocument.doc_type == doc_type)
        count_query = count_query.where(KnowledgeDocument.doc_type == doc_type)

    # Apply folder filter
    if folder:
        # Match exact folder path, normalised so '/HR' and '/HR/' agree
        folder = normalize_folder_path(folder)
        query = query.where(KnowledgeDocument.folder_path == folder)
        count_query = count_query.where(KnowledgeDocument.folder_path == folder)

    # Apply keyword search (case-insensitive on title and content)
    if search:
        search_filter = or_(
            KnowledgeDocument.title.ilike(f"%{search}%"),
            KnowledgeDocument.content.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Get total count
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    documents = list(result.scalars().all())

    return documents, total


async def chunk_counts_for(
    db: AsyncSession, document_ids: list[uuid.UUID], profile: KbProfile | None = None
) -> dict[uuid.UUID, int]:
    """
    Count chunks per document in one aggregate query.

    Used instead of len(document.chunks) so listing documents never loads
    embeddings.
    """
    profile = profile or default_profile()
    KnowledgeDocument, KnowledgeChunk = profile.tables

    if not document_ids:
        return {}

    result = await db.execute(
        select(KnowledgeChunk.document_id, func.count(KnowledgeChunk.id))
        .where(KnowledgeChunk.document_id.in_(document_ids))
        .group_by(KnowledgeChunk.document_id)
    )
    counts = {row[0]: row[1] for row in result.all()}
    return {doc_id: counts.get(doc_id, 0) for doc_id in document_ids}


async def search_similar(
    db: AsyncSession,
    query_embedding: list[float],
    profile: KbProfile | None = None,
    top_k: int = 5,
    doc_type: str | None = None,
    folder: str | None = None,
) -> list[dict]:
    """
    Perform a vector similarity search against stored chunks.

    Returns the top_k most similar chunks with their similarity scores
    and parent document info.
    """
    profile = profile or default_profile()
    KnowledgeDocument, KnowledgeChunk = profile.tables

    # Build the similarity search query using pgvector's cosine distance
    query = (
        select(
            KnowledgeChunk,
            KnowledgeDocument.title.label("doc_title"),
            KnowledgeDocument.doc_type.label("doc_type"),
            KnowledgeDocument.folder_path.label("folder_path"),
            (1 - KnowledgeChunk.embedding.cosine_distance(query_embedding)).label(
                "similarity"
            ),
        )
        .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .order_by(KnowledgeChunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )

    if doc_type:
        query = query.where(KnowledgeDocument.doc_type == doc_type)

    if folder:
        query = query.where(
            KnowledgeDocument.folder_path == normalize_folder_path(folder)
        )

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "chunk_id": str(row.KnowledgeChunk.id),
            "document_id": str(row.KnowledgeChunk.document_id),
            "document_title": row.doc_title,
            "doc_type": row.doc_type,
            "folder_path": row.folder_path,
            "chunk_index": row.KnowledgeChunk.chunk_index,
            "content": row.KnowledgeChunk.content,
            "similarity": round(float(row.similarity), 4),
            "metadata": row.KnowledgeChunk.metadata_,
        }
        for row in rows
    ]


async def get_stats(db: AsyncSession, profile: KbProfile | None = None) -> dict:
    """
    Knowledge base statistics for the dashboard.

    Deliberately one round trip. The service usually talks to Postgres over an
    SSH tunnel where a single round trip costs ~700ms, so seven sequential
    queries made the dashboard take five seconds. The work itself is trivial —
    it was latency, not cost.

    Includes both the configured embedding dimensions and the dimensions
    actually stored, because those two silently drifting apart is the failure
    that destroys retrieval without any error surfacing.
    """
    profile = profile or default_profile()
    KnowledgeDocument, KnowledgeChunk = profile.tables

    # Table names are interpolated rather than bound, because a parameter
    # cannot stand in for an identifier. The prefix is regex-validated when it
    # is stored and again when the models are built, and is unique-constrained
    # in the registry — it never carries anything a user typed freely.
    documents, chunks = f"{profile.table_prefix}_documents", f"{profile.table_prefix}_chunks"

    result = (
        await db.execute(
            text(
                """
                WITH doc_totals AS (
                    SELECT count(*) AS total FROM {documents}
                ),
                chunk_totals AS (
                    SELECT count(*) AS total,
                           count(*) FILTER (WHERE embedding IS NULL) AS missing,
                           min(vector_dims(embedding)) FILTER (WHERE embedding IS NOT NULL)
                               AS stored_dims
                    FROM {chunks}
                ),
                by_type AS (
                    SELECT coalesce(jsonb_object_agg(doc_type, n), '{}'::jsonb) AS j
                    FROM (SELECT doc_type, count(*) AS n
                          FROM {documents} GROUP BY doc_type) t
                ),
                by_format AS (
                    SELECT coalesce(jsonb_object_agg(source_format, n), '{}'::jsonb) AS j
                    FROM (SELECT source_format, count(*) AS n
                          FROM {documents} GROUP BY source_format) t
                ),
                by_folder AS (
                    SELECT coalesce(jsonb_object_agg(folder_path, n), '{}'::jsonb) AS j
                    FROM (SELECT folder_path, count(*) AS n
                          FROM {documents} GROUP BY folder_path) t
                ),
                recent AS (
                    SELECT coalesce(jsonb_agg(r ORDER BY r.created_at DESC), '[]'::jsonb) AS j
                    FROM (
                        SELECT id, title, doc_type, source_format, folder_path, created_at
                        FROM {documents}
                        ORDER BY created_at DESC
                        LIMIT 5
                    ) r
                )
                SELECT doc_totals.total          AS total_documents,
                       chunk_totals.total        AS total_chunks,
                       chunk_totals.missing      AS chunks_missing_embedding,
                       chunk_totals.stored_dims  AS stored_dimensions,
                       by_type.j                 AS documents_by_type,
                       by_format.j               AS documents_by_format,
                       by_folder.j               AS documents_by_folder,
                       recent.j                  AS recent_documents,
                       pg_total_relation_size('{chunks}') AS chunk_storage_bytes
                FROM doc_totals, chunk_totals, by_type, by_format, by_folder, recent
                """.replace("{documents}", documents).replace("{chunks}", chunks)
            )
        )
    ).one()

    stored_dimensions = result.stored_dimensions

    return {
        "total_documents": result.total_documents or 0,
        "total_chunks": result.total_chunks or 0,
        "chunks_missing_embedding": result.chunks_missing_embedding or 0,
        "documents_by_type": result.documents_by_type or {},
        "documents_by_format": result.documents_by_format or {},
        "documents_by_folder": result.documents_by_folder or {},
        "recent_documents": result.recent_documents or [],
        "embedding_provider": profile.embedding.provider,
        "embedding_model": profile.model,
        "configured_dimensions": profile.dimensions,
        "stored_dimensions": stored_dimensions,
        "dimensions_match": (
            stored_dimensions is None or stored_dimensions == profile.dimensions
        ),
        "chunk_storage_bytes": result.chunk_storage_bytes or 0,
    }


async def replace_document_content(
    db: AsyncSession,
    document_id: uuid.UUID,
    new_content: str,
    new_doc_type: str | None = None,
    file_name: str | None = None,
    file_size: int | None = None,
    source_format: str | None = None,
    metadata: dict | None = None,
    profile: KbProfile | None = None,
) -> tuple:
    """
    Replace a document's content entirely (e.g., uploading a new PDF over an old one).

    Deletes all old chunks/embeddings and creates new ones from the new content.

    Returns (document, chunk_count).
    """
    profile = profile or default_profile()
    KnowledgeDocument, KnowledgeChunk = profile.tables

    document = await db.get(KnowledgeDocument, document_id)
    if not document:
        raise ValueError(f"Document with id {document_id} not found.")

    # Update document fields
    document.content = new_content
    if new_doc_type:
        document.doc_type = new_doc_type
    if file_name is not None:
        document.file_name = file_name
    if file_size is not None:
        document.file_size = file_size
    if source_format is not None:
        document.source_format = source_format
    if metadata is not None:
        document.metadata_ = {**(document.metadata_ or {}), **metadata}
    document.updated_at = datetime.now(timezone.utc)

    # Delete old chunks
    await db.execute(
        delete(KnowledgeChunk).where(
            KnowledgeChunk.document_id == document_id
        )
    )

    # Re-chunk and re-embed
    chunks = chunk_document(
        new_content, document.doc_type, document.metadata_,
        doc_title=document.title,
        max_size=profile.chunk_size, overlap=profile.chunk_overlap,
    )
    if not chunks:
        raise ValueError(
            f"The new content for '{document.title}' produced no chunks. "
            f"The document was not changed."
        )

    chunk_texts = [c.content for c in chunks]
    embeddings = await generate_embeddings(
        chunk_texts, title=document.title, config=profile.embedding
    )

    for chunk, embedding in zip(chunks, embeddings):
        db_chunk = KnowledgeChunk(
            document_id=document.id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            embedding=embedding,
            metadata_=chunk.metadata,
        )
        db.add(db_chunk)

    chunk_count = len(chunks)
    logger.info(
        f"Replaced content of document '{document.title}' (id={document_id}) — "
        f"{chunk_count} new chunks."
    )
    return document, chunk_count


async def append_document_content(
    db: AsyncSession,
    document_id: uuid.UUID,
    additional_content: str,
    metadata: dict | None = None,
    profile: KbProfile | None = None,
) -> tuple:
    """
    Append content to an existing document.

    The new content is concatenated to the existing content, then the entire
    document is re-chunked and re-embedded (because chunk boundaries shift).

    Returns (document, chunk_count).
    """
    profile = profile or default_profile()
    KnowledgeDocument, KnowledgeChunk = profile.tables

    document = await db.get(KnowledgeDocument, document_id)
    if not document:
        raise ValueError(f"Document with id {document_id} not found.")

    # Concatenate content
    document.content = document.content + "\n\n" + additional_content
    if metadata is not None:
        document.metadata_ = {**(document.metadata_ or {}), **metadata}
    document.updated_at = datetime.now(timezone.utc)

    # Delete old chunks — full re-chunk needed because boundaries shift
    await db.execute(
        delete(KnowledgeChunk).where(
            KnowledgeChunk.document_id == document_id
        )
    )

    # Re-chunk and re-embed the combined content
    chunks = chunk_document(
        document.content, document.doc_type, document.metadata_,
        doc_title=document.title,
        max_size=profile.chunk_size, overlap=profile.chunk_overlap,
    )
    if not chunks:
        raise ValueError(
            f"The combined content for '{document.title}' produced no chunks."
        )

    chunk_texts = [c.content for c in chunks]
    embeddings = await generate_embeddings(
        chunk_texts, title=document.title, config=profile.embedding
    )

    for chunk, embedding in zip(chunks, embeddings):
        db_chunk = KnowledgeChunk(
            document_id=document.id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            embedding=embedding,
            metadata_=chunk.metadata,
        )
        db.add(db_chunk)

    chunk_count = len(chunks)
    logger.info(
        f"Appended to document '{document.title}' (id={document_id}) — "
        f"now {len(document.content)} chars, {chunk_count} chunks."
    )
    return document, chunk_count


# ────────────────────────────────────────────────────────────────────────────
# Folder tree
# ────────────────────────────────────────────────────────────────────────────

def normalize_folder_path(path: str | None) -> str:
    """
    Canonicalise a folder path so the tree never splits into near-duplicates.

    '', 'HR', '/HR', '/HR/', '//HR//Policies' all collapse to a single form:
    a leading slash, a trailing slash, and no empty segments. Without this,
    '/HR' and '/HR/' would render as two different folders.
    """
    if not path:
        return "/"
    segments = [segment.strip() for segment in path.split("/")]
    # Drop empties and relative segments. These are not filesystem paths — they
    # never touch disk — but '..' would otherwise render as a literal folder.
    segments = [s for s in segments if s and s not in (".", "..")]
    if not segments:
        return "/"
    return "/" + "/".join(segments) + "/"


def ancestors_of(path: str) -> list[str]:
    """
    Every folder between the root and `path`, root first, `path` last.

    '/a/b/' -> ['/', '/a/', '/a/b/']. The tree needs these so an intermediate
    folder still renders when no document sits directly inside it.
    """
    normalized = normalize_folder_path(path)
    if normalized == "/":
        return ["/"]

    result = ["/"]
    current = ""
    for segment in normalized.strip("/").split("/"):
        current = f"{current}/{segment}"
        result.append(current + "/")
    return result


async def get_tree(db: AsyncSession, profile: KbProfile | None = None) -> dict:
    """
    Everything the directory tree needs, in two queries.

    Returns a flat list of documents plus the full set of folder paths with
    their direct counts. The nesting is assembled by the client, which keeps
    expand/collapse and filtering instant without another round trip.

    Only scalar columns are selected — never the ORM entity — so chunk
    embeddings are never loaded.
    """
    profile = profile or default_profile()
    KnowledgeDocument, KnowledgeChunk = profile.tables

    rows = (
        await db.execute(
            select(
                KnowledgeDocument.id,
                KnowledgeDocument.title,
                KnowledgeDocument.folder_path,
                KnowledgeDocument.doc_type,
                KnowledgeDocument.source_format,
                KnowledgeDocument.file_name,
                KnowledgeDocument.file_size,
                KnowledgeDocument.created_at,
                KnowledgeDocument.updated_at,
                func.count(KnowledgeChunk.id).label("chunk_count"),
                func.count(KnowledgeChunk.embedding).label("embedded_chunk_count"),
            )
            .outerjoin(
                KnowledgeChunk, KnowledgeChunk.document_id == KnowledgeDocument.id
            )
            .group_by(KnowledgeDocument.id)
            .order_by(KnowledgeDocument.folder_path, KnowledgeDocument.title)
        )
    ).all()

    documents = [
        {
            "id": str(row.id),
            "title": row.title,
            "folder_path": normalize_folder_path(row.folder_path),
            "doc_type": row.doc_type,
            "source_format": row.source_format,
            "file_name": row.file_name,
            "file_size": row.file_size,
            "chunk_count": row.chunk_count,
            "embedded_chunk_count": row.embedded_chunk_count,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]

    # Expand every stored path into its ancestors so intermediate folders exist
    # as tree nodes even when nothing is filed directly in them.
    folder_paths: set[str] = {"/"}
    for document in documents:
        folder_paths.update(ancestors_of(document["folder_path"]))

    direct_counts: dict[str, int] = {}
    for document in documents:
        path = document["folder_path"]
        direct_counts[path] = direct_counts.get(path, 0) + 1

    folders = [
        {"path": path, "document_count": direct_counts.get(path, 0)}
        for path in sorted(folder_paths)
    ]

    return {
        "folders": folders,
        "documents": documents,
        "total_documents": len(documents),
        "total_chunks": sum(d["chunk_count"] for d in documents),
    }
