import json
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.api.deps import KbContext, kb_db, resolve_kb
from app.api.schemas import DocumentResponse, ErrorResponse
from app.services import knowledge_service
from app.services.extraction_service import (
    SUPPORTED_EXTENSIONS,
    extract,
    get_extension,
    is_supported,
    promote_frontmatter,
    suggested_doc_type,
)

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/v1", tags=["File Upload"])


@router.post(
    "/documents/upload",
    response_model=DocumentResponse,
    status_code=201,
    summary="Upload a document file",
    description="Upload a file to the knowledge base. Text is extracted, chunked, "
    "and embedded automatically. Supported types: "
    f"{', '.join(SUPPORTED_EXTENSIONS)} — up to {settings.max_upload_size_mb}MB.",
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def upload_document(
    request: Request,
    file: UploadFile = File(..., description="File to upload"),
    title: str | None = Form(
        None,
        max_length=512,
        description="Document title. Optional for markdown carrying a front matter "
                    "title, which is then used instead.",
    ),
    metadata: str | None = Form(
        None,
        description='Optional JSON metadata string, e.g. {"category": "policies"}',
    ),
    folder_path: str = Form(
        "/",
        description="Folder path to store the document in, e.g. /HR/Policies/",
    ),
    doc_type: str | None = Form(
        None,
        description="Chunking strategy. Inferred from the file type when omitted.",
    ),
    context: KbContext = Depends(resolve_kb),
    db: AsyncSession = Depends(kb_db),
):
    """Upload a file, extract its text, chunk it, embed it, and store it."""

    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file has no name.")

    if not is_supported(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{get_extension(file.filename)}'. "
                   f"Supported types: {', '.join(SUPPORTED_EXTENSIONS)}.",
        )

    content = await file.read()

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content) / 1024 / 1024:.1f}MB). "
                   f"Maximum allowed size is {settings.max_upload_size_mb}MB.",
        )

    parsed_metadata = None
    if metadata:
        try:
            parsed_metadata = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Invalid metadata JSON. Please provide valid JSON.",
            )
        if not isinstance(parsed_metadata, dict):
            raise HTTPException(
                status_code=400,
                detail="Metadata must be a JSON object, not a list or scalar.",
            )

    try:
        extraction = extract(content, file.filename)

        # Front matter is authoritative for what it declares, because it lives
        # with the content and is reviewed with it. Explicit form values still
        # win — an admin overriding on the way in means to override.
        front = promote_frontmatter(extraction)

        effective_title = (title or "").strip() or front["title"]
        if not effective_title:
            raise HTTPException(
                status_code=400,
                detail="No title given. Provide one, or add 'title:' to the "
                       "document's front matter.",
            )

        effective_doc_type = (
            doc_type
            or front["doc_type"]
            or suggested_doc_type(extraction.source_format)
        )

        # Format findings (page count, sheet names) sit underneath front matter,
        # which sits underneath anything the admin passed explicitly.
        format_meta = {k: v for k, v in extraction.metadata.items() if k != "frontmatter"}
        doc_metadata = {
            **format_meta,
            **front["metadata"],
            **(parsed_metadata or {}),
            "source": "file_upload",
        }

        document, chunk_count = await knowledge_service.add_document(
            db=db,
            title=effective_title,
            content=extraction.text,
            doc_type=effective_doc_type,
            metadata=doc_metadata,
            file_name=extraction.file_name,
            file_size=extraction.file_size,
            folder_path=folder_path,
            source_format=extraction.source_format,
            profile=context.profile,
        )

        return DocumentResponse(
            id=document.id,
            title=document.title,
            content=document.content,
            doc_type=document.doc_type,
            source_format=document.source_format,
            metadata=document.metadata_,
            chunk_count=chunk_count,
            file_name=document.file_name,
            file_size=document.file_size,
            folder_path=document.folder_path,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    except ValueError as e:
        # Extraction problems are the admin's to fix (wrong file, scanned PDF,
        # empty spreadsheet), so they come back as 400 with the real reason.
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        request_id = getattr(request.state, "request_id", None)
        logger.error(
            f"[{request_id}] Failed to process upload of '{file.filename}': {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process file. Please check the logs. "
                   f"Request ID: {request_id}",
        )
