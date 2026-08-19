import time
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.api.deps import KbContext, kb_db, kb_readonly_db, resolve_kb
from app.api.schemas import (
    DocumentCreate,
    DocumentUpdate,
    DocumentResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    ChunkResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    MessageResponse,
    ErrorResponse,
    StatsResponse,
    TreeResponse,
    SupportedFormatsResponse,
    KNOWN_DOC_TYPES,
    EmbeddingSettingsResponse,
    ApiKeyUpdate,
    ApiKeyUpdateResponse,
)
from app.services import knowledge_service
from app.services.embedding_service import (
    MODEL_SPECS,
    generate_embedding,
    mask_api_key,
    set_api_key,
    verify_api_key,
)
from app.services.env_service import update_env_var
from app.services.extraction_service import (
    SUPPORTED_EXTENSIONS,
    TABULAR_FORMATS,
    extract,
    suggested_doc_type,
)

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/v1", tags=["Knowledge Base"])


def _build_document_response(
    document, chunk_count: int | None = None
) -> DocumentResponse:
    """
    Build a consistent DocumentResponse from an ORM object.

    chunk_count should always be supplied. The fallback reads
    document.chunks, which triggers a selectin load of every chunk and its
    embedding — fine for a single document, ruinous inside a list.
    """
    return DocumentResponse(
        id=document.id,
        title=document.title,
        content=document.content,
        doc_type=document.doc_type,
        source_format=document.source_format,
        metadata=document.metadata_,
        chunk_count=chunk_count if chunk_count is not None else len(document.chunks),
        file_name=document.file_name,
        file_size=document.file_size,
        folder_path=document.folder_path,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=201,
    summary="Add a new document",
    description="Upload a new document (text or API definition) to the knowledge base. "
    "The document will be automatically chunked and embedded.",
    responses={500: {"model": ErrorResponse}},
)
async def create_document(
    payload: DocumentCreate,
    request: Request,
    context: KbContext = Depends(resolve_kb),
    db: AsyncSession = Depends(kb_db),
):
    try:
        document, chunk_count = await knowledge_service.add_document(
            db=db,
            title=payload.title,
            content=payload.content,
            doc_type=payload.doc_type,
            metadata=payload.metadata,
            folder_path=payload.folder_path,
            profile=context.profile,
        )
        return _build_document_response(document, chunk_count)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        request_id = getattr(request.state, "request_id", None)
        logger.error(f"[{request_id}] Failed to create document: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create document. Please check the logs. "
                   f"Request ID: {request_id}",
        )


@router.get(
    "/documents",
    response_model=DocumentListResponse,
    summary="List all documents",
    description="List all documents in the knowledge base with optional filtering and pagination.",
)
async def list_documents(
    doc_type: str | None = Query(None, description="Filter by document type"),
    search: str | None = Query(None, description="Keyword search on title and content"),
    folder: str | None = Query(None, description="Filter by folder path"),
    skip: int = Query(0, ge=0, description="Number of documents to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max documents to return"),
    context: KbContext = Depends(resolve_kb),
    db: AsyncSession = Depends(kb_readonly_db),
):
    documents, total = await knowledge_service.list_documents(
        db=db, profile=context.profile, doc_type=doc_type, search=search,
        folder=folder, skip=skip, limit=limit,
    )
    counts = await knowledge_service.chunk_counts_for(
        db, [d.id for d in documents], context.profile
    )
    return DocumentListResponse(
        documents=[
            _build_document_response(doc, counts.get(doc.id, 0)) for doc in documents
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Get a document",
    description="Retrieve a specific document with all its chunks.",
    responses={404: {"model": ErrorResponse}},
)
async def get_document(
    document_id: uuid.UUID,
    context: KbContext = Depends(resolve_kb),
    db: AsyncSession = Depends(kb_readonly_db),
):
    document = await knowledge_service.get_document(db, document_id, context.profile)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    return DocumentDetailResponse(
        id=document.id,
        title=document.title,
        content=document.content,
        doc_type=document.doc_type,
        source_format=document.source_format,
        metadata=document.metadata_,
        chunk_count=len(document.chunks),
        embedded_chunk_count=sum(
            1 for chunk in document.chunks if chunk.embedding is not None
        ),
        file_name=document.file_name,
        file_size=document.file_size,
        folder_path=document.folder_path,
        created_at=document.created_at,
        updated_at=document.updated_at,
        chunks=[
            ChunkResponse(
                id=chunk.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                metadata=chunk.metadata_,
                created_at=chunk.created_at,
            )
            for chunk in sorted(document.chunks, key=lambda c: c.chunk_index)
        ],
    )


@router.put(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    summary="Update a document",
    description="Update an existing document. If content or doc_type changes, "
    "the document is re-chunked and re-embedded automatically.",
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def update_document(
    document_id: uuid.UUID,
    payload: DocumentUpdate,
    request: Request,
    context: KbContext = Depends(resolve_kb),
    db: AsyncSession = Depends(kb_db),
):
    try:
        document, chunk_count = await knowledge_service.update_document(
            db=db,
            document_id=document_id,
            title=payload.title,
            content=payload.content,
            doc_type=payload.doc_type,
            metadata=payload.metadata,
            folder_path=payload.folder_path,
            profile=context.profile,
        )
        return _build_document_response(document, chunk_count)
    except ValueError as e:
        status = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=status, detail=str(e))
    except Exception as e:
        request_id = getattr(request.state, "request_id", None)
        logger.error(f"[{request_id}] Failed to update document: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update document. Please check the logs. "
                   f"Request ID: {request_id}",
        )


@router.delete(
    "/documents/{document_id}",
    response_model=MessageResponse,
    summary="Delete a document",
    description="Delete a document and all its chunks from the knowledge base.",
    responses={404: {"model": ErrorResponse}},
)
async def delete_document(
    document_id: uuid.UUID,
    context: KbContext = Depends(resolve_kb),
    db: AsyncSession = Depends(kb_db),
):
    deleted = await knowledge_service.delete_document(db, document_id, context.profile)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")

    return MessageResponse(
        message="Document deleted successfully.",
        detail=f"Document {document_id} and all its chunks have been removed.",
    )


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Search the knowledge base",
    description="Perform a similarity search against the knowledge base. "
    "Returns the most relevant chunks ranked by cosine similarity.",
    responses={500: {"model": ErrorResponse}},
)
async def search_knowledge_base(
    payload: SearchRequest,
    request: Request,
    context: KbContext = Depends(resolve_kb),
    db: AsyncSession = Depends(kb_readonly_db),
):
    try:
        # Timed separately: embedding latency is an API round trip, search
        # latency is the database. They scale for completely different reasons,
        # and only the second one tells you when an index is needed.
        embed_start = time.perf_counter()
        # Embedded with this knowledge base's model. Using any other one would
        # project the query into a different space from the stored vectors, and
        # the scores would be noise rather than an error.
        query_embedding = await generate_embedding(
            payload.query, config=context.profile.embedding
        )
        embed_ms = (time.perf_counter() - embed_start) * 1000

        search_start = time.perf_counter()
        results = await knowledge_service.search_similar(
            db=db,
            query_embedding=query_embedding,
            profile=context.profile,
            top_k=payload.top_k,
            doc_type=payload.doc_type,
            folder=payload.folder,
        )
        search_ms = (time.perf_counter() - search_start) * 1000

        return SearchResponse(
            query=payload.query,
            results=[SearchResultItem(**r) for r in results],
            total_results=len(results),
            knowledge_base=context.slug,
            embedding_model=context.profile.model,
            embed_ms=round(embed_ms, 1),
            search_ms=round(search_ms, 1),
        )
    except Exception as e:
        request_id = getattr(request.state, "request_id", None)
        logger.error(f"[{request_id}] Search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Search failed. Please check the logs. "
                   f"Request ID: {request_id}",
        )


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Knowledge base statistics",
    description="Get statistics about the knowledge base — "
    "total documents, total chunks, and breakdown by type.",
)
async def get_stats(
    context: KbContext = Depends(resolve_kb),
    db: AsyncSession = Depends(kb_readonly_db),
):
    stats = await knowledge_service.get_stats(db, context.profile)
    return StatsResponse(knowledge_base=context.slug, **stats)


@router.put(
    "/documents/{document_id}/replace",
    response_model=DocumentResponse,
    summary="Replace document content",
    description="Replace a document's content entirely (e.g., upload a new PDF to replace the old one). "
    "All old chunks and embeddings are deleted, and new ones are created from the new content.",
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def replace_document_content(
    document_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(None, description="New PDF file (optional if providing text)"),
    content: str | None = Form(None, description="New text content (optional if providing file)"),
    metadata: str | None = Form(None, description="Optional JSON metadata"),
    context: KbContext = Depends(resolve_kb),
    db: AsyncSession = Depends(kb_db),
):
    """Replace a document's content with new text or a new PDF."""
    try:
        new_content = None
        file_name = None
        file_size = None
        new_doc_type = None

        source_format = None

        if file and file.filename:
            file_bytes = await file.read()
            extraction = extract(file_bytes, file.filename)
            new_content = extraction.text
            file_name = extraction.file_name
            file_size = extraction.file_size
            source_format = extraction.source_format
            new_doc_type = suggested_doc_type(extraction.source_format)
        elif content:
            new_content = content
            source_format = "manual"
        else:
            raise HTTPException(
                status_code=400,
                detail="Provide either a file or text content to replace.",
            )

        parsed_meta = None
        if metadata:
            import json
            try:
                parsed_meta = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid metadata JSON.")

        document, chunk_count = await knowledge_service.replace_document_content(
            db=db,
            document_id=document_id,
            new_content=new_content,
            new_doc_type=new_doc_type,
            file_name=file_name,
            file_size=file_size,
            source_format=source_format,
            metadata=parsed_meta,
            profile=context.profile,
        )
        return _build_document_response(document, chunk_count)
    except ValueError as e:
        # ValueError covers both "document not found" and extraction failures
        status = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=status, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        request_id = getattr(request.state, "request_id", None)
        logger.error(f"[{request_id}] Replace failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to replace document content. Request ID: {request_id}",
        )


@router.post(
    "/documents/{document_id}/append",
    response_model=DocumentResponse,
    summary="Append content to a document",
    description="Append additional text or PDF content to an existing document. "
    "The full document is re-chunked and re-embedded because chunk boundaries shift.",
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def append_document_content(
    document_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(None, description="PDF file to append"),
    content: str | None = Form(None, description="Text content to append"),
    metadata: str | None = Form(None, description="Optional JSON metadata to merge"),
    context: KbContext = Depends(resolve_kb),
    db: AsyncSession = Depends(kb_db),
):
    """Append text or PDF content to an existing document."""
    try:
        additional_content = None

        if file and file.filename:
            file_bytes = await file.read()
            additional_content = extract(file_bytes, file.filename).text
        elif content:
            additional_content = content
        else:
            raise HTTPException(
                status_code=400,
                detail="Provide either a file or text content to append.",
            )

        parsed_meta = None
        if metadata:
            import json
            try:
                parsed_meta = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid metadata JSON.")

        document, chunk_count = await knowledge_service.append_document_content(
            db=db,
            document_id=document_id,
            additional_content=additional_content,
            metadata=parsed_meta,
            profile=context.profile,
        )
        return _build_document_response(document, chunk_count)
    except ValueError as e:
        # ValueError covers both "document not found" and extraction failures
        status = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=status, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        request_id = getattr(request.state, "request_id", None)
        logger.error(f"[{request_id}] Append failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to append content. Request ID: {request_id}",
        )


@router.get(
    "/tree",
    response_model=TreeResponse,
    summary="Knowledge base directory tree",
    description="Every folder and document in one payload, for the interactive "
    "directory tree. Folders are derived from document paths and include "
    "intermediate levels. Chunk embeddings are never loaded.",
)
async def get_tree(
    context: KbContext = Depends(resolve_kb),
    db: AsyncSession = Depends(kb_readonly_db),
):
    return TreeResponse(**await knowledge_service.get_tree(db, context.profile))


@router.get(
    "/formats",
    response_model=SupportedFormatsResponse,
    summary="Supported upload formats",
    description="File extensions the upload endpoint accepts, so the UI does "
    "not have to hardcode the list.",
)
async def get_supported_formats():
    return SupportedFormatsResponse(
        extensions=SUPPORTED_EXTENSIONS,
        tabular_formats=sorted(TABULAR_FORMATS),
        doc_types=KNOWN_DOC_TYPES,
        max_upload_size_mb=settings.max_upload_size_mb,
    )


# ── Runtime settings ──
#
# Only the embedding API key is changeable at runtime, because it is the one
# value an admin needs to rotate without a redeploy (free-tier quota runs out).
# Model and dimensions are deliberately NOT editable: changing either
# invalidates every stored vector, so it needs a re-embed, not a form field.

@router.get(
    "/settings/embedding",
    response_model=EmbeddingSettingsResponse,
    summary="Current embedding configuration",
    description="Runtime embedding settings. The API key is returned only as a "
    "masked preview — the value itself never leaves the server.",
)
async def get_embedding_settings(context: KbContext = Depends(resolve_kb)):
    # Model and dimensions belong to the knowledge base being viewed; the API
    # key belongs to the provider and is shared by every knowledge base using it.
    provider = context.profile.embedding.normalised_provider
    key = settings.gemini_api_key if provider == "gemini" else settings.fal_key
    return EmbeddingSettingsResponse(
        knowledge_base=context.slug,
        provider=provider,
        model=context.profile.model,
        dimensions=context.profile.dimensions,
        batch_size=context.profile.embedding.batch_size,
        requests_per_minute=context.profile.embedding.requests_per_minute,
        chunk_size=context.profile.chunk_size,
        chunk_overlap=context.profile.chunk_overlap,
        api_key_set=bool(key),
        api_key_preview=mask_api_key(key),
        known_models=sorted(
            m for m, spec in MODEL_SPECS.items() if spec["provider"] == provider
        ),
    )


@router.put(
    "/settings/embedding/api-key",
    response_model=ApiKeyUpdateResponse,
    summary="Replace the embedding API key",
    description="Verifies the key against the provider before accepting it, so a "
    "bad key can never replace a working one. Optionally persists it to .env.",
    responses={400: {"model": ErrorResponse}},
)
async def update_api_key(
    payload: ApiKeyUpdate,
    request: Request,
    context: KbContext = Depends(resolve_kb),
):
    provider = context.profile.embedding.normalised_provider
    api_key = payload.api_key.strip()

    ok, message = await verify_api_key(provider, api_key, context.profile.model)
    if not ok:
        # 400, not 500 — the submitted key is the problem, and the message comes
        # from the provider so the admin can see exactly why it was rejected.
        raise HTTPException(status_code=400, detail=message)

    await set_api_key(provider, api_key)

    persisted = False
    if payload.persist:
        env_name = "GEMINI_API_KEY" if provider == "gemini" else "FAL_KEY"
        persisted = update_env_var(env_name, api_key)
        if not persisted:
            message += " It is active now, but could not be written to .env, so it will be lost on restart."

    request_id = getattr(request.state, "request_id", None)
    logger.info(f"[{request_id}] Embedding API key replaced for provider '{provider}'.")

    return ApiKeyUpdateResponse(
        ok=True,
        message=message,
        api_key_preview=mask_api_key(api_key),
        persisted=persisted,
    )
