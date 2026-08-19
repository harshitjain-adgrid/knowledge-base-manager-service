import uuid
from datetime import datetime

from typing import Annotated

from pydantic import BaseModel, Field


# ── Document types ──
#
# doc_type is an open vocabulary rather than an enum: it selects the chunking
# strategy, and new kinds of knowledge should not require a schema migration.
# These are the values the UI offers by default.

DOC_TYPE_TEXT = "text"
DOC_TYPE_API_DEFINITION = "api_definition"

KNOWN_DOC_TYPES = [DOC_TYPE_TEXT, DOC_TYPE_API_DEFINITION]

DocTypeField = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9_-]+$",
        examples=KNOWN_DOC_TYPES,
        description="Chunking strategy. 'api_definition' chunks per endpoint; "
                    "anything else is chunked as prose.",
    ),
]


# ── Request Schemas ──

class DocumentCreate(BaseModel):
    """Schema for creating a new knowledge base document."""
    title: str = Field(..., min_length=1, max_length=512, examples=["Refund Policy"])
    content: str = Field(..., min_length=1, examples=["Our refund policy allows..."])
    doc_type: DocTypeField = DOC_TYPE_TEXT
    metadata: dict | None = Field(default=None, examples=[{"category": "policies"}])
    folder_path: str = Field(default="/", examples=["/policies/"])


class DocumentUpdate(BaseModel):
    """Schema for updating an existing document. All fields optional."""
    title: str | None = Field(None, min_length=1, max_length=512)
    content: str | None = None
    doc_type: DocTypeField | None = None
    metadata: dict | None = None
    folder_path: str | None = None


class SearchRequest(BaseModel):
    """Schema for similarity search."""
    query: str = Field(..., min_length=1, examples=["How to process a refund?"])
    top_k: int = Field(default=5, ge=1, le=50)
    doc_type: DocTypeField | None = Field(
        default=None,
        description="Optional filter to search only one kind of document.",
    )
    folder: str | None = Field(
        default=None,
        description="Optional filter restricting the search to one folder.",
    )


# ── Response Schemas ──

class ChunkResponse(BaseModel):
    """Single chunk in a document response."""
    id: uuid.UUID
    chunk_index: int
    content: str
    metadata: dict | None = None
    created_at: datetime


class DocumentResponse(BaseModel):
    """Full document response including its chunks."""
    id: uuid.UUID
    title: str
    content: str
    doc_type: str
    source_format: str = "manual"
    metadata: dict | None = None
    chunk_count: int
    embedded_chunk_count: int | None = None
    file_name: str | None = None
    file_size: int | None = None
    folder_path: str = Field(default="/")
    created_at: datetime
    updated_at: datetime


class DocumentDetailResponse(DocumentResponse):
    """Document response with full chunk details."""
    chunks: list[ChunkResponse] = []


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""
    documents: list[DocumentResponse]
    total: int
    skip: int
    limit: int


class SearchResultItem(BaseModel):
    """Single search result with similarity score."""
    chunk_id: str
    document_id: str
    document_title: str
    doc_type: str
    folder_path: str = "/"
    chunk_index: int
    content: str
    similarity: float
    metadata: dict | None = None


class SearchResponse(BaseModel):
    """Similarity search response."""
    query: str
    results: list[SearchResultItem]
    total_results: int
    # Which knowledge base answered. Two of them can hold documents with the
    # same title, so a result set without this is ambiguous.
    knowledge_base: str = "default"
    # Which embedding space the query was projected into. Without this a result
    # set is ambiguous the moment the configured model changes.
    embedding_model: str
    embed_ms: float
    search_ms: float


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    detail: str | None = None


class ErrorResponse(BaseModel):
    """Structured error response for production APIs."""
    error: str
    detail: str | None = None
    request_id: str | None = None


class HealthResponse(BaseModel):
    """Health check response with service status."""
    status: str
    database: str
    version: str
    environment: str


class RecentDocument(BaseModel):
    """Compact document summary for the dashboard's recent-uploads list."""
    id: str
    title: str
    doc_type: str
    source_format: str
    folder_path: str
    created_at: datetime


class StatsResponse(BaseModel):
    """Knowledge base statistics and embedding health."""
    knowledge_base: str = "default"
    total_documents: int
    total_chunks: int
    chunks_missing_embedding: int
    documents_by_type: dict[str, int]
    documents_by_format: dict[str, int]
    documents_by_folder: dict[str, int]
    recent_documents: list[RecentDocument]

    # Embedding health. configured_dimensions comes from settings,
    # stored_dimensions is measured from the data itself.
    embedding_provider: str
    embedding_model: str
    configured_dimensions: int
    stored_dimensions: int | None = None
    dimensions_match: bool
    chunk_storage_bytes: int


class TreeDocument(BaseModel):
    """A document as it appears in the directory tree."""
    id: str
    title: str
    folder_path: str
    doc_type: str
    source_format: str
    file_name: str | None = None
    file_size: int | None = None
    chunk_count: int
    embedded_chunk_count: int
    created_at: datetime
    updated_at: datetime


class TreeFolder(BaseModel):
    """A folder node. document_count is direct children only, not recursive."""
    path: str
    document_count: int


class TreeResponse(BaseModel):
    """Flat directory listing; the client assembles the nesting."""
    folders: list[TreeFolder]
    documents: list[TreeDocument]
    total_documents: int
    total_chunks: int


class SupportedFormatsResponse(BaseModel):
    """What the upload endpoint accepts, so the UI never has to hardcode it."""
    extensions: list[str]
    tabular_formats: list[str]
    doc_types: list[str]
    max_upload_size_mb: int


class EmbeddingSettingsResponse(BaseModel):
    """
    Runtime embedding configuration for the settings screen.

    The API key is only ever exposed as a masked preview — the real value stays
    on the server and is never sent to a browser.
    """
    knowledge_base: str = "default"
    provider: str
    model: str
    dimensions: int
    batch_size: int
    requests_per_minute: int
    chunk_size: int
    chunk_overlap: int
    api_key_set: bool
    api_key_preview: str | None = None
    known_models: list[str]


class ApiKeyUpdate(BaseModel):
    """Replace the embedding provider's API key at runtime."""
    api_key: str = Field(
        ..., min_length=8, max_length=512,
        description="The new API key. Verified against the provider before it is accepted.",
    )
    persist: bool = Field(
        default=True,
        description="Also write it to .env so it survives a restart.",
    )


class ApiKeyUpdateResponse(BaseModel):
    """Outcome of an API key change."""
    ok: bool
    message: str
    api_key_preview: str | None = None
    persisted: bool = False


# ── Auth ──

class LoginRequest(BaseModel):
    """Credentials for the admin UI."""
    username: str = Field(..., min_length=1, max_length=64, examples=["admin"])
    password: str = Field(..., min_length=1, max_length=256)


class LoginResponse(BaseModel):
    """A new session. The token is shown once and never returned again."""
    token: str
    username: str
    expires_in_hours: int


class CurrentUserResponse(BaseModel):
    """Who is signed in, and whether sign-in is required at all."""
    auth_enabled: bool
    authenticated: bool
    username: str | None = None


# ── Knowledge bases ──
#
# The connection string is write-only across this boundary: it goes in on
# create, and only ever comes back as a preview with the password removed.

SlugField = Annotated[
    str,
    Field(
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$",
        examples=["merchant-ops"],
        description="URL-safe identifier, used as ?kb=<slug>.",
    ),
]


class KnowledgeBaseCreate(BaseModel):
    """
    Register a new knowledge base.

    provider, model and dimensions are fixed here and cannot be changed
    afterwards — every vector in the knowledge base is produced by this model,
    and vectors from two models are not comparable.
    """

    name: str = Field(..., min_length=1, max_length=128, examples=["Merchant Ops"])
    slug: SlugField | None = Field(
        default=None,
        description="Derived from the name when omitted.",
    )
    description: str | None = Field(default=None, max_length=2000)

    dsn: str = Field(
        ...,
        min_length=12,
        max_length=1024,
        examples=["postgresql://kb_user:password@10.0.0.7:5432/merchant_ops"],
        description=(
            "Postgres connection string, including credentials. Stored "
            "encrypted and never returned. The host must be reachable from the "
            "server — if it sits behind SSH, run the tunnel on the server and "
            "point this at the local end of it."
        ),
    )

    embedding_provider: str = Field(default="gemini", examples=["gemini"])
    embedding_model: str = Field(..., examples=["gemini-embedding-2"])
    embedding_dimensions: int = Field(..., ge=64, le=4096, examples=[3072])

    chunk_size: int | None = Field(default=None, ge=200, le=8000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=2000)


class KnowledgeBaseUpdate(BaseModel):
    """
    Edit a knowledge base.

    Model, provider and dimensions are absent on purpose: changing them would
    invalidate every stored vector without any error surfacing, so it is a
    re-ingest into a new knowledge base rather than an edit.
    """

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None
    make_default: bool = Field(
        default=False,
        description="Make this the knowledge base used when a request names none.",
    )
    dsn: str | None = Field(
        default=None,
        min_length=12,
        max_length=1024,
        description="Replace the connection string. Tested before it is accepted.",
    )


class KnowledgeBaseResponse(BaseModel):
    """A registered knowledge base. Never includes the connection string."""

    id: uuid.UUID
    slug: str
    name: str
    description: str | None = None
    # user@host:port/database — the password is not part of this
    dsn_preview: str
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int
    chunk_size: int
    chunk_overlap: int
    is_default: bool
    is_active: bool
    # True when the connection string comes from DATABASE_URL rather than a row
    from_environment: bool = False
    last_error: str | None = None
    last_checked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseListResponse(BaseModel):
    """Every registered knowledge base, default first."""

    knowledge_bases: list[KnowledgeBaseResponse]
    total: int
    default_slug: str | None = None


class ConnectionTestRequest(BaseModel):
    """Check a connection string before committing to it."""

    dsn: str = Field(..., min_length=12, max_length=1024)


class ConnectionTestResponse(BaseModel):
    """Outcome of a connection test, in words an admin can act on."""

    ok: bool
    message: str
    dsn_preview: str | None = None


class EmbeddingModelOption(BaseModel):
    """One option in the model dropdown, with the constraints that go with it."""

    model: str
    provider: str
    allowed_dimensions: list[int]
    default_dimensions: int
    input_token_limit: int
    multimodal: bool
    # False when the provider's API key is not set on this server, so the UI can
    # explain why an option cannot be chosen rather than failing on submit.
    key_configured: bool

    model_config = {"protected_namespaces": ()}


class EmbeddingModelsResponse(BaseModel):
    """Models available when creating a knowledge base."""

    models: list[EmbeddingModelOption]
