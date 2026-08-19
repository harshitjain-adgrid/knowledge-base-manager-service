import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    LoginRequest,
    LoginResponse,
    CurrentUserResponse,
    MessageResponse,
    ErrorResponse,
)
from app.config import get_settings
from app.db.database import get_db
from app.services import auth_service

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    return header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Sign in",
    description="Exchange a username and password for a session token. Send the "
    "token as `Authorization: Bearer <token>` on subsequent requests.",
    responses={401: {"model": ErrorResponse}},
)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await auth_service.authenticate(db, payload.username, payload.password)

    if result is None:
        request_id = getattr(request.state, "request_id", None)
        logger.warning(
            f"[{request_id}] Failed sign-in for {payload.username!r} "
            f"from {request.client.host if request.client else 'unknown'}."
        )
        # One message for both cases — saying which half was wrong tells an
        # attacker which usernames exist.
        raise HTTPException(status_code=401, detail="Incorrect username or password.")

    token, user = result
    return LoginResponse(
        token=token,
        username=user.username,
        expires_in_hours=settings.session_ttl_hours,
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Sign out",
    description="Revokes the current session token immediately.",
)
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    revoked = await auth_service.revoke_session(db, _bearer_token(request))
    return MessageResponse(
        message="Signed out." if revoked else "No active session to sign out.",
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Who am I",
    description="Returns the signed-in user, and whether auth is switched on at all. "
    "The admin UI calls this on load to decide whether to show a sign-in screen.",
)
async def me(request: Request):
    # AdminAuthMiddleware has already validated the token and attached the user
    username = getattr(request.state, "username", None)
    return CurrentUserResponse(
        auth_enabled=True,
        authenticated=bool(username),
        username=username,
    )
