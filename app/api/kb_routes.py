import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    ConnectionTestRequest,
    ConnectionTestResponse,
    EmbeddingModelsResponse,
    ErrorResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    MessageResponse,
)
from app.db.database import dispose_kb_engine, get_db, get_readonly_db
from app.db.models import KnowledgeBase
from app.services import kb_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Knowledge Bases"])


def _to_response(kb: KnowledgeBase) -> KnowledgeBaseResponse:
    return KnowledgeBaseResponse(
        id=kb.id,
        slug=kb.slug,
        name=kb.name,
        description=kb.description,
        dsn_preview=kb.dsn_preview,
        embedding_provider=kb.embedding_provider,
        embedding_model=kb.embedding_model,
        embedding_dimensions=kb.embedding_dimensions,
        chunk_size=kb.chunk_size,
        chunk_overlap=kb.chunk_overlap,
        is_default=kb.is_default,
        is_active=kb.is_active,
        from_environment=kb.dsn_encrypted is None,
        last_error=kb.last_error,
        last_checked_at=kb.last_checked_at,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


@router.get(
    "/embedding-models",
    response_model=EmbeddingModelsResponse,
    summary="Embedding models available for a new knowledge base",
    description="The models this build knows how to call, with the dimension "
    "counts each supports and whether its provider's API key is configured on "
    "this server. Populates the model dropdown on the create form.",
)
async def list_embedding_models():
    return EmbeddingModelsResponse(models=kb_service.available_models())


@router.get(
    "/knowledge-bases",
    response_model=KnowledgeBaseListResponse,
    summary="List knowledge bases",
    description="Every registered knowledge base, default first. Connection "
    "strings are never included — only a preview with the password removed.",
)
async def list_knowledge_bases(db: AsyncSession = Depends(get_readonly_db)):
    records = await kb_service.list_kbs(db)
    default = next((kb.slug for kb in records if kb.is_default), None)
    return KnowledgeBaseListResponse(
        knowledge_bases=[_to_response(kb) for kb in records],
        total=len(records),
        default_slug=default,
    )


@router.post(
    "/knowledge-bases/test-connection",
    response_model=ConnectionTestResponse,
    summary="Test a Postgres connection",
    description="Opens a throwaway connection and reports what happened, "
    "including whether pgvector is available. Nothing is stored.",
)
async def test_connection(payload: ConnectionTestRequest):
    try:
        dsn = kb_service.normalise_dsn(payload.dsn)
    except kb_service.KbError as e:
        return ConnectionTestResponse(ok=False, message=str(e))

    ok, message = await kb_service.test_connection(dsn)
    return ConnectionTestResponse(
        ok=ok, message=message, dsn_preview=kb_service.dsn_preview(dsn)
    )


@router.post(
    "/knowledge-bases",
    response_model=KnowledgeBaseResponse,
    status_code=201,
    summary="Add a knowledge base",
    description="Register another pgvector database and choose the embedding "
    "model its content will be stored with. The connection is tested and the "
    "schema created before the knowledge base appears in the list, so anything "
    "listed is known to work. The model cannot be changed afterwards.",
    responses={400: {"model": ErrorResponse}},
)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        kb = await kb_service.create_kb(
            db,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            dsn=payload.dsn,
            embedding_provider=payload.embedding_provider,
            embedding_model=payload.embedding_model,
            embedding_dimensions=payload.embedding_dimensions,
            chunk_size=payload.chunk_size,
            chunk_overlap=payload.chunk_overlap,
        )
    except kb_service.KbError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        request_id = getattr(request.state, "request_id", None)
        logger.error(
            f"[{request_id}] Failed to register knowledge base: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Could not register the knowledge base. Request ID: {request_id}",
        )

    # Read back inside the same transaction so the response carries the server's
    # defaults rather than what was submitted.
    await db.flush()
    return _to_response(kb)


@router.get(
    "/knowledge-bases/{slug}",
    response_model=KnowledgeBaseResponse,
    summary="Get a knowledge base",
    responses={404: {"model": ErrorResponse}},
)
async def get_knowledge_base(slug: str, db: AsyncSession = Depends(get_readonly_db)):
    kb = await kb_service.get_by_slug(db, slug)
    if kb is None:
        raise HTTPException(status_code=404, detail=f"No knowledge base called '{slug}'.")
    return _to_response(kb)


@router.put(
    "/knowledge-bases/{slug}",
    response_model=KnowledgeBaseResponse,
    summary="Update a knowledge base",
    description="Rename it, deactivate it, make it the default, or point it at "
    "a different database. The embedding model is deliberately not editable.",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def update_knowledge_base(
    slug: str,
    payload: KnowledgeBaseUpdate,
    db: AsyncSession = Depends(get_db),
):
    kb = await kb_service.get_by_slug(db, slug)
    if kb is None:
        raise HTTPException(status_code=404, detail=f"No knowledge base called '{slug}'.")

    try:
        kb = await kb_service.update_kb(
            db,
            kb,
            name=payload.name,
            description=payload.description,
            is_active=payload.is_active,
            make_default=payload.make_default,
            dsn=payload.dsn,
        )
    except kb_service.KbError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if payload.dsn is not None:
        # The old pool points at the previous host; retire it so nothing keeps
        # reading from a database this knowledge base no longer means.
        await dispose_kb_engine(kb.id)

    await db.flush()
    return _to_response(kb)


@router.post(
    "/knowledge-bases/{slug}/check",
    response_model=ConnectionTestResponse,
    summary="Re-check a knowledge base",
    description="Connects to a registered knowledge base again and updates its "
    "status. Use it to clear a stale 'unreachable' after the host comes back.",
    responses={404: {"model": ErrorResponse}},
)
async def recheck_knowledge_base(slug: str, db: AsyncSession = Depends(get_db)):
    kb = await kb_service.get_by_slug(db, slug)
    if kb is None:
        raise HTTPException(status_code=404, detail=f"No knowledge base called '{slug}'.")

    ok, message = await kb_service.recheck(db, kb)
    return ConnectionTestResponse(ok=ok, message=message, dsn_preview=kb.dsn_preview)


@router.delete(
    "/knowledge-bases/{slug}",
    response_model=MessageResponse,
    summary="Unregister a knowledge base",
    description="Removes it from the registry. The documents and vectors in its "
    "database are left exactly as they are — this service never drops tables it "
    "does not own.",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def delete_knowledge_base(slug: str, db: AsyncSession = Depends(get_db)):
    kb = await kb_service.get_by_slug(db, slug)
    if kb is None:
        raise HTTPException(status_code=404, detail=f"No knowledge base called '{slug}'.")

    kb_id, preview = kb.id, kb.dsn_preview
    try:
        await kb_service.delete_kb(db, kb)
    except kb_service.KbError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await dispose_kb_engine(kb_id)
    return MessageResponse(
        message=f"'{slug}' was removed from the registry.",
        detail=f"Its documents and vectors at {preview} were left untouched.",
    )
