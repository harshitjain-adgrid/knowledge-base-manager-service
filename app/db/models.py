import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

# A table prefix reaches DDL, so it is constrained to something that can never
# need quoting or escaping.
TABLE_PREFIX_RE = re.compile(r"^kb_[a-z0-9_]{1,48}$")


class ControlBase(DeclarativeBase):
    """
    Control-plane tables — admin users, sessions, and the registry of knowledge
    bases. These only ever exist in the database named by DATABASE_URL.
    """
    pass


# ── Knowledge base tables ───────────────────────────────────────────────────
#
# Every knowledge base gets its own pair of tables in one schema, named after
# its registry prefix: kb_default_documents / kb_default_chunks,
# kb_api_catalog_documents / kb_api_catalog_chunks.
#
# Separate tables rather than one pair with a kb_id column, for one decisive
# reason: the embedding width lives on the column. A shared table has a single
# `embedding vector(N)` and would pin every knowledge base to the same model
# forever, which is the opposite of what the registry exists to allow. Separate
# tables also make it impossible to express "forgot the WHERE" — the wrong
# catalogue is not reachable rather than one clause away.
#
# The classes are built per prefix and cached. Each pair gets its own
# DeclarativeBase so their metadata and class registries never collide.

_MODEL_CACHE: dict[str, tuple[type, type]] = {}


def kb_models(table_prefix: str) -> tuple[type, type]:
    """
    The (Document, Chunk) ORM classes for one knowledge base.

    `table_prefix` reaches DDL, so it is validated here as well as at the point
    it is stored — this is the last line before a table name is built from it.
    """
    if not TABLE_PREFIX_RE.match(table_prefix):
        raise ValueError(
            f"'{table_prefix}' is not a usable table prefix. Expected something "
            f"like 'kb_api_catalog': lowercase letters, digits and underscores, "
            f"starting with 'kb_'."
        )

    cached = _MODEL_CACHE.get(table_prefix)
    if cached is not None:
        return cached

    documents_table = f"{table_prefix}_documents"
    chunks_table = f"{table_prefix}_chunks"

    class KbBase(DeclarativeBase):
        pass

    class KnowledgeDocument(KbBase):
        """A document uploaded by an admin, before it is split for retrieval."""

        __tablename__ = documents_table

        id: Mapped[uuid.UUID] = mapped_column(
            UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
        )
        title: Mapped[str] = mapped_column(String(512), nullable=False)
        content: Mapped[str] = mapped_column(Text, nullable=False)
        # Chunking strategy — an open vocabulary, not a DB enum, so new kinds of
        # knowledge can be introduced without a schema migration.
        doc_type: Mapped[str] = mapped_column(String(64), nullable=False)
        # Where the content came from: pdf, docx, html, md, xlsx, manual, ...
        # Deliberately separate from doc_type, which describes how it is chunked.
        source_format: Mapped[str] = mapped_column(
            String(32), nullable=False, default="manual", server_default="manual"
        )
        metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)
        file_name: Mapped[str | None] = mapped_column(
            String(512), nullable=True, default=None
        )
        file_size: Mapped[int | None] = mapped_column(
            Integer, nullable=True, default=None
        )
        # The tree view groups on this, so it is indexed.
        folder_path: Mapped[str] = mapped_column(
            String(1024), nullable=False, default="/", index=True
        )
        created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
        )
        updated_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True),
            default=lambda: datetime.now(timezone.utc),
            onupdate=lambda: datetime.now(timezone.utc),
        )

        chunks: Mapped[list["KnowledgeChunk"]] = relationship(
            back_populates="document",
            cascade="all, delete-orphan",
            lazy="selectin",
        )

        def __repr__(self) -> str:
            return f"<{documents_table}(id={self.id}, title='{self.title}')>"

    class KnowledgeChunk(KbBase):
        """One retrievable piece of a document, with its embedding."""

        __tablename__ = chunks_table

        id: Mapped[uuid.UUID] = mapped_column(
            UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
        )
        document_id: Mapped[uuid.UUID] = mapped_column(
            UUID(as_uuid=True),
            ForeignKey(f"{documents_table}.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
        chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
        content: Mapped[str] = mapped_column(Text, nullable=False)
        # Declared without a fixed size on purpose. Each knowledge base picks its
        # own model and therefore its own dimension count, so the width belongs
        # in that table's DDL rather than in a class shared by all of them.
        embedding = mapped_column(Vector(), nullable=True)
        metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)
        created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
        )

        document: Mapped["KnowledgeDocument"] = relationship(back_populates="chunks")

        def __repr__(self) -> str:
            return f"<{chunks_table}(doc={self.document_id}, index={self.chunk_index})>"

    _MODEL_CACHE[table_prefix] = (KnowledgeDocument, KnowledgeChunk)
    return KnowledgeDocument, KnowledgeChunk


class AdminUser(ControlBase):
    """
    An internal team member who can sign in to the admin UI.

    Deliberately minimal — no roles, no email, no reset flow. Everyone who can
    sign in can do everything, which matches how a small internal team actually
    works. Add roles when there is a real reason to, not before.
    """

    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    # bcrypt hash, never the password
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    sessions: Mapped[list["AdminSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<AdminUser(username='{self.username}', active={self.is_active})>"


class AdminSession(ControlBase):
    """
    A signed-in browser session.

    Only a hash of the token is stored, so a leaked database dump cannot be
    replayed as a live login. Sessions are rows rather than JWTs so that signing
    out actually revokes access instead of waiting for an expiry.
    """

    __tablename__ = "admin_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["AdminUser"] = relationship(back_populates="sessions", lazy="joined")

    def __repr__(self) -> str:
        return f"<AdminSession(user_id={self.user_id}, expires={self.expires_at})>"


class KnowledgeBase(ControlBase):
    """
    A registered knowledge base: where its documents live and how they are
    embedded.

    The registry is what makes more than one of these possible. The default
    knowledge base stores its documents in this same database and carries a
    NULL dsn_encrypted, so the primary connection string is still read from the
    environment and never written to a table. Additional ones store an
    encrypted DSN, because an admin types those in through the UI.

    provider / model / dimensions are fixed at creation. Changing any of them
    would invalidate every vector already stored, so it is a re-ingest rather
    than an edit.
    """

    __tablename__ = "knowledge_bases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # URL-safe identifier used by clients as ?kb=<slug>
    slug: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    # Names this knowledge base's tables: kb_api_catalog -> kb_api_catalog_documents
    # and kb_api_catalog_chunks. Unique, because two knowledge bases sharing a
    # prefix would share their rows.
    table_prefix: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )

    # NULL means "use DATABASE_URL" — the default knowledge base's connection
    # string stays in the environment.
    dsn_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    # host:port/database, never the password. Safe to show in the UI.
    dsn_preview: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    embedding_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)

    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1200)
    chunk_overlap: Mapped[int] = mapped_column(Integer, nullable=False, default=150)

    # Exactly one row is the default; it answers requests that name no knowledge
    # base, which is every request made before this feature existed.
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Last connection or schema failure, so the UI can explain an unreachable
    # knowledge base instead of just failing every request against it.
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeBase(slug='{self.slug}', model='{self.embedding_model}')>"
