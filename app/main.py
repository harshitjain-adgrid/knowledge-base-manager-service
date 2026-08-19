import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import text

from app.api.routes import router as documents_router
from app.api.upload_routes import router as upload_router
from app.api.auth_routes import router as auth_router
from app.api.kb_routes import router as kb_router
from app.api.middleware import (
    RequestIdMiddleware,
    RequestTimingMiddleware,
    AdminAuthMiddleware,
)
from app.api.schemas import HealthResponse
from app.config import get_settings
from app.db.init_db import (
    init_control_db,
    init_kb_schema,
    migrate_default_slug,
    migrate_to_prefixed_tables,
)
from app.db.database import (
    AsyncSessionLocal,
    ReadOnlySessionLocal,
    dispose_all_engines,
    engine,
)
from app.services import auth_service, kb_service
from app.services.embedding_service import close_clients, validate_embedding_config

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# How long to wait for one registered knowledge base at startup. A host that is
# down must not hold the whole service in its lifespan — the knowledge base is
# marked unreachable and everything else starts normally.
# Generous rather than tight: the probe opens a connection and runs a dozen
# statements, and over a tunnel at a couple of hundred milliseconds per round
# trip a healthy knowledge base can still take several seconds. Timing one out
# marks it unreachable, which is worse than waiting a moment longer.
KB_STARTUP_TIMEOUT_SECONDS = 25


async def _check_other_knowledge_bases() -> None:
    """
    Reach each additional knowledge base once, so the UI can show which ones are
    healthy instead of finding out on the first query.

    A failure here is recorded, never raised: one unreachable remote database is
    not a reason to refuse to start.
    """
    async with AsyncSessionLocal() as session:
        records = [kb for kb in await kb_service.list_kbs(session) if not kb.is_default]

        for kb in records:
            if not kb.is_active:
                continue
            try:
                kb_engine = await asyncio.wait_for(
                    kb_service.engine_for(kb), timeout=KB_STARTUP_TIMEOUT_SECONDS
                )
                await asyncio.wait_for(
                    init_kb_schema(kb_engine, kb.table_prefix, kb.embedding_dimensions),
                    timeout=KB_STARTUP_TIMEOUT_SECONDS,
                )
            except Exception as e:
                message = "Timed out." if isinstance(e, asyncio.TimeoutError) else str(e)
                logger.warning(f"Knowledge base '{kb.slug}' is unreachable: {message}")
                kb.last_error = message[:1000]
            else:
                kb.last_error = None
                logger.info(
                    f"Knowledge base '{kb.slug}' ready — {kb.embedding_model}, "
                    f"{kb.embedding_dimensions} dims at {kb.dsn_preview}."
                )

        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info(f"Starting up ({settings.environment})...")
    validate_embedding_config()
    logger.info("Initialising database...")
    # The control plane first: it holds the registry that says which knowledge
    # bases exist, including the default one this service was configured with.
    await init_control_db()
    # Moves a pre-prefix installation onto per-knowledge-base table names.
    # Catalogue-only renames, so no vector is rewritten and nothing is
    # re-embedded. Does nothing on a fresh install or a second start.
    await migrate_to_prefixed_tables()
    await migrate_default_slug()

    async with AsyncSessionLocal() as session:
        default_kb = await kb_service.ensure_default_kb(session)
        await kb_service.normalise_stored_dsns(session)
        await session.commit()

    await init_kb_schema(
        engine, default_kb.table_prefix, default_kb.embedding_dimensions
    )
    logger.info("Database initialised. Server is ready.")

    await _check_other_knowledge_bases()
    # Auth is mandatory, so a deployment with nobody able to sign in is broken
    # and should say so at startup rather than at the first sign-in attempt.
    async with AsyncSessionLocal() as session:
        user_count = await auth_service.count_users(session)
        purged = await auth_service.purge_expired_sessions(session)
        await session.commit()
    if user_count == 0 and not settings.admin_api_key:
        raise RuntimeError(
            "No admin users exist, so nobody could sign in. Create one first:\n"
            "    python -m app.admin_cli create <username>"
        )
    logger.info(
        f"Auth: {user_count} admin user(s), sessions valid "
        f"{settings.session_ttl_hours}h"
        + (f", purged {purged} expired session(s)" if purged else "")
    )
    logger.info(
        f"Default knowledge base '{default_kb.slug}': "
        f"{default_kb.embedding_provider} / {default_kb.embedding_model} "
        f"({default_kb.embedding_dimensions} dims)"
    )
    yield
    logger.info("Shutting down...")
    await close_clients()
    await dispose_all_engines()


app = FastAPI(
    title="Chotu RAG — Knowledge Base Ingestion Service",
    description=(
        "Admin service for managing the chatbot's knowledge base. "
        "Supports adding, updating, and deleting documents (text, API definitions, and PDFs). "
        "Documents are automatically chunked and embedded via the configured "
        "embedding provider (Gemini or fal.ai OpenRouter), and stored in "
        "PostgreSQL with pgvector for fast similarity search."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

# ── Middleware (order matters: outermost runs first) ──
app.add_middleware(AdminAuthMiddleware)
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(RequestIdMiddleware)

# CORS.
#
# Only registered when CORS_ORIGINS is set. In the normal deployment FastAPI
# serves the UI itself, so requests are same-origin and CORS is not involved at
# all. The previous "*" with credentials was both rejected by browsers and, if
# it had worked, would have let any website drive this API using a signed-in
# admin's session.
if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
    logger.info(f"CORS enabled for: {', '.join(settings.cors_origin_list)}")

# ── API Routes ──
app.include_router(auth_router)
app.include_router(kb_router)
app.include_router(documents_router)
app.include_router(upload_router)


# ── Admin UI ──
#
# The React app is served by this process once it has been built
# (`cd frontend && npm run build`), so a deployment is one service rather than a
# separate static host. In development you would normally run the Vite dev
# server instead, which proxies /api and /health back here.

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"

if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")
    logger.info(f"Serving admin UI from {FRONTEND_DIST}")
else:
    logger.warning(
        "frontend/dist not found — the admin UI will not be served. "
        "Build it with: cd frontend && npm run build"
    )


# ── Root & Health ──

@app.get("/", include_in_schema=False)
async def root():
    """Serve the admin UI if it has been built, otherwise the API docs."""
    if FRONTEND_INDEX.is_file():
        return FileResponse(FRONTEND_INDEX)
    return RedirectResponse(url="/docs")


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint — verifies the service and database are operational.
    """
    db_status = "disconnected"
    try:
        # Read-only session: a health check has nothing to commit, and the
        # transactional one costs three round trips instead of one.
        async with ReadOnlySessionLocal() as session:
            await session.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as e:
        logger.warning(f"Health check — database connection failed: {e}")

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        database=db_status,
        version="0.2.0",
        environment=settings.environment,
    )


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    """
    Client-side routes (/documents, /search, /settings) are resolved by the
    React router, so any unmatched GET returns index.html. Declared last, and
    API prefixes are excluded explicitly so a mistyped endpoint still 404s as
    JSON instead of quietly returning HTML.
    """
    if full_path.startswith(("api/", "health", "docs", "redoc", "openapi.json")):
        raise HTTPException(status_code=404, detail="Not found.")
    if FRONTEND_INDEX.is_file():
        return FileResponse(FRONTEND_INDEX)
    raise HTTPException(
        status_code=404,
        detail="Admin UI is not built. Run: cd frontend && npm run build",
    )
