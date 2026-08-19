import logging
import secrets
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Adds a unique X-Request-ID header to every request/response.
    If the client sends one, it is reused; otherwise a new UUID is generated.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """
    Logs the method, path, status code, and duration of every request.
    """

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        request_id = getattr(request.state, "request_id", "N/A")
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} "
            f"→ {response.status_code} ({duration_ms:.1f}ms)"
        )
        return response


class AdminAuthMiddleware(BaseHTTPMiddleware):
    """
    Requires a signed-in session for every API request.

    Two credentials are accepted, both as `Authorization: Bearer <value>`:

    * a session token from POST /api/v1/auth/login — what the admin UI uses;
    * ADMIN_API_KEY, if set — a machine key for scripts and curl.

    The admin UI's own HTML and assets stay public. They contain nothing
    sensitive, and serving a sign-in screen requires being able to load the page
    that shows it.
    """

    # Never require auth for these
    PUBLIC_PATHS = ("/health", "/docs", "/openapi.json", "/redoc")
    PUBLIC_API_PATHS = ("/api/v1/auth/login", "/api/v1/auth/me")

    async def dispatch(self, request: Request, call_next):
        request.state.username = None
        path = request.url.path
        if path.startswith(self.PUBLIC_PATHS) or path in self.PUBLIC_API_PATHS:
            # /auth/me is public so the UI can ask "do I need to sign in?" —
            # it still resolves the token when one is supplied.
            if path in self.PUBLIC_API_PATHS:
                await self._attach_user(request)
            return await call_next(request)

        # Non-API paths are the built UI; the sign-in screen lives there
        if not path.startswith("/api/"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Unauthorized",
                    "detail": "Sign in to continue.",
                },
            )

        if not await self._attach_user(request):
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Unauthorized",
                    "detail": "Your session has expired or is invalid. Sign in again.",
                },
            )

        return await call_next(request)

    async def _attach_user(self, request: Request) -> bool:
        """Resolve the bearer token onto request.state.username."""
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return False
        token = header.removeprefix("Bearer ").strip()
        if not token:
            return False

        # Machine key, for scripts. Compared in constant time.
        if settings.admin_api_key and secrets.compare_digest(token, settings.admin_api_key):
            request.state.username = "api-key"
            return True

        # Imported here to keep module import order simple at startup
        from app.db.database import ReadOnlySessionLocal
        from app.services import auth_service

        try:
            async with ReadOnlySessionLocal() as session:
                user = await auth_service.resolve_session(session, token)
        except Exception as e:
            # A database problem must not be mistaken for a valid credential
            logger.error(f"Could not verify session token: {e}")
            return False

        if user is None:
            return False

        request.state.username = user.username
        return True
