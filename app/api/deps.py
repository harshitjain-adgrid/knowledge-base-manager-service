"""
Which knowledge base is this request about, and how do we talk to it.

Every content endpoint used to open a session on the one configured database.
Now it opens a session on the one the request names, so the choice has to be
resolved before the route body runs — which is exactly what a dependency is for.

Requests that name nothing get the default knowledge base, so every client
written before this existed keeps working unchanged.
"""

import logging
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db.database import (
    ReadOnlySessionLocal,
    kb_readonly_sessionmaker,
    kb_sessionmaker,
)
from app.services import crypto_service, kb_service
from app.services.kb_types import KbProfile

logger = logging.getLogger(__name__)

KB_HEADER = "X-Knowledge-Base"


@dataclass(frozen=True)
class KbContext:
    """The resolved knowledge base: what it is, and where to write to."""

    profile: KbProfile
    engine: AsyncEngine
    dsn_preview: str
    is_default: bool

    @property
    def slug(self) -> str:
        return self.profile.slug


async def resolve_kb(
    request: Request,
    kb: str | None = Query(
        None,
        description=(
            "Identifier of the knowledge base to act on. Defaults to the "
            f"default one. Can also be sent as the {KB_HEADER} header."
        ),
    ),
) -> KbContext:
    """
    Resolve ?kb=<slug>, then the X-Knowledge-Base header, then the default.

    The query parameter wins so a single request can be aimed somewhere else
    without changing the client's standing configuration — which is what the
    admin UI's knowledge-base switcher does.
    """
    requested = (kb or request.headers.get(KB_HEADER) or "").strip() or None

    async with ReadOnlySessionLocal() as session:
        if requested:
            record = await kb_service.get_by_slug(session, requested)
            if record is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"There is no knowledge base called '{requested}'.",
                )
        else:
            record = await kb_service.get_default(session)
            if record is None:
                raise HTTPException(
                    status_code=503,
                    detail="No default knowledge base is registered. Restart the "
                           "service, which registers the one from its environment.",
                )

        if not record.is_active:
            raise HTTPException(
                status_code=409,
                detail=f"'{record.name}' is deactivated. Reactivate it before "
                       f"reading from or writing to it.",
            )

        profile = kb_service.profile_for(record)
        dsn_preview = record.dsn_preview
        is_default = record.is_default

        try:
            engine = await kb_service.engine_for(record)
        except crypto_service.SecretsUnavailable as e:
            # A configuration problem on the server, not a bad request — and the
            # message says exactly which one, because the alternative is an
            # admin staring at a 500 with no idea that SECRET_KEY moved.
            raise HTTPException(status_code=503, detail=str(e))

    return KbContext(
        profile=profile,
        engine=engine,
        dsn_preview=dsn_preview,
        is_default=is_default,
    )


async def kb_db(context: KbContext = Depends(resolve_kb)) -> AsyncSession:
    """A transactional session on the resolved knowledge base, for writes."""
    async with kb_sessionmaker(context.engine)() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def kb_readonly_db(context: KbContext = Depends(resolve_kb)) -> AsyncSession:
    """
    A read-only session on the resolved knowledge base.

    No transaction is opened and nothing is committed, so a read costs a single
    round trip. Using this for a write would leave each statement
    self-committing, so writes must use kb_db().
    """
    async with kb_readonly_sessionmaker(context.engine)() as session:
        yield session
