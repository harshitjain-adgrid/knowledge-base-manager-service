"""
The description of one knowledge base that the rest of the service works with.

Chunking and embedding used to read the environment directly, which was correct
while there was exactly one knowledge base. With several, those settings differ
per knowledge base and have to travel with the request instead — that is all
this profile is: a small, immutable bundle handed down from the request to the
services that need it.
"""

import uuid
from dataclasses import dataclass

from app.config import get_settings
from app.db.models import kb_models
from app.services.embedding_service import EmbeddingConfig, default_config

settings = get_settings()


@dataclass(frozen=True)
class KbProfile:
    """Everything about a knowledge base except how to connect to it."""

    id: uuid.UUID
    slug: str
    name: str
    # Names this knowledge base's tables. Everything that reads or writes its
    # content goes through the classes this resolves to, so there is no way to
    # touch one knowledge base while holding another's profile.
    table_prefix: str
    embedding: EmbeddingConfig
    chunk_size: int
    chunk_overlap: int

    @property
    def tables(self) -> tuple[type, type]:
        """The (Document, Chunk) ORM classes for this knowledge base."""
        return kb_models(self.table_prefix)

    @property
    def model(self) -> str:
        return self.embedding.model

    @property
    def dimensions(self) -> int:
        return self.embedding.dimensions


def default_profile() -> KbProfile:
    """
    A profile built from the environment.

    Used by code paths that predate multiple knowledge bases — the unit tests,
    and any call that has not been handed a profile — so their behaviour is
    unchanged.
    """
    return KbProfile(
        id=uuid.UUID(int=0),
        slug="product-knowledge",
        name="Product knowledge",
        table_prefix="kb_product_knowledge",
        embedding=default_config(),
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
