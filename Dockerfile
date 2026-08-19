# Two stages: build the React bundle with Node, then run it from the Python
# image. The final image has no Node in it, and the frontend is baked in so the
# app is a single container serving both the UI and the API.

FROM node:20-slim AS frontend

WORKDIR /build
# Copy manifests first so `npm ci` is cached until dependencies actually change
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.11-slim

# lxml and bcrypt ship wheels, so no compiler is needed. curl is here only for
# the container healthcheck below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY --from=frontend /build/dist ./frontend/dist

# Run as a non-root user. The app writes to .env when an admin rotates the
# embedding API key, so that file must be writable by this user — mount it with
# the right ownership (see docker-compose.yml).
RUN useradd --create-home --uid 10001 chotu && chown -R chotu:chotu /app
USER chotu

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# One worker on purpose. The client-side embedding rate limiter is per-process,
# so N workers would allow N times the configured requests per minute and start
# collecting 429s from Gemini. This is an internal admin tool — one worker is
# plenty, and correctness matters more than throughput here.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
