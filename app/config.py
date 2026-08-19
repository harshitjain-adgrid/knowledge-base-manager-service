from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # ── Environment ──
    environment: str = "development"  # "development" | "staging" | "production"

    # ── Database ──
    #
    # The *control plane*: admin users, sessions, and the knowledge-base
    # registry live here. It is also the default knowledge base's own storage,
    # so a single-KB deployment needs nothing else.
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/chotu_rag"

    # ── Secrets ──
    #
    # Encrypts the connection strings of *additional* knowledge bases before
    # they are written to the registry table. The primary DATABASE_URL is never
    # stored in the database at all — it is read from here every time.
    #
    # Without this, a dump of the control database would hand over working
    # credentials to every other Postgres host the team has registered. Generate
    # one with:
    #     python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    secret_key: str = ""

    # ── Embedding provider ──
    embedding_provider: str = "gemini"  # "gemini" | "fal"

    # fal.ai OpenRouter
    fal_key: str = ""

    # Google Gemini (AI Studio)
    gemini_api_key: str = ""

    # ── Embedding configuration ──
    #
    # These are the defaults for the *default* knowledge base. Every additional
    # knowledge base carries its own provider, model and dimensions in the
    # registry, chosen when it is created.
    # gemini  -> "gemini-embedding-2" (3072 native dims, 8192-token input)
    # fal     -> "openai/text-embedding-3-large" (3072 dims)
    embedding_model: str = "gemini-embedding-2"
    embedding_dimensions: int = 3072
    max_embedding_batch_size: int = 20  # Texts per API request
    # Gemini free tier allows 100 embed requests/min, and each text in a batch
    # counts as one request. Set to 0 to disable client-side pacing.
    embedding_requests_per_minute: int = 90

    # ── Chunking configuration ──
    # Sized in characters. ~1200 chars is roughly 300 tokens, well inside every
    # supported model's input limit, and large enough that a typical section and
    # its table survive in one piece.
    chunk_size: int = 1200
    chunk_overlap: int = 150

    # ── Auth ──
    # Always on. There is no switch to turn it off, so there is no way to end up
    # serving an open admin API by forgetting a setting.
    session_ttl_hours: int = 12

    # Optional machine key for scripts and curl, checked alongside user sessions.
    # Not needed for the admin UI, which signs in with a username and password.
    admin_api_key: str = ""

    # ── CORS ──
    # Comma-separated origins allowed to call the API from a browser. Empty is
    # correct for the normal deployment, where FastAPI serves the UI itself and
    # requests are same-origin. Only set this if the frontend is hosted
    # separately (e.g. on Vercel) from the API.
    cors_origins: str = ""

    # ── File Uploads ──
    max_upload_size_mb: int = 20  # Maximum PDF upload size in MB

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
