# Chotu RAG — Knowledge Base Ingestion Service

Admin service for managing the chatbot's knowledge base. Built with **FastAPI**, **pgvector**, and **Google Gemini** embeddings.

## Quick Start

### 1. Set up a virtual environment

```bash
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # macOS/Linux
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
copy .env.example .env
```

Edit `.env` with your actual values:
- `DATABASE_URL` — Your PostgreSQL connection string (with pgvector extension installed)
- `GEMINI_API_KEY` — Your Google Gemini API key
- `SECRET_KEY` — Only needed if you add a second knowledge base. It encrypts the
  connection strings of the ones you add through the UI, so a database dump does
  not hand over credentials to other hosts. Generate one with:
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

### 4. Build the admin UI

```bash
cd frontend
npm install
npm run build
cd ..
```

### 5. Create an admin user

Auth is always on, so the service needs at least one account before it will start:

```bash
python -m app.admin_cli create <username>
```

### 6. Run the server

```bash
uvicorn app.main:app --reload
```

Everything is served from one process at `http://localhost:8000` — the admin UI at
`/`, the API under `/api/v1`, and Swagger at `/docs`.

**For frontend development** run Vite instead, which hot-reloads and proxies
`/api` and `/health` back to port 8000:

```bash
cd frontend && npm run dev     # http://localhost:5173
```

## Embeddings

The provider is selected with `EMBEDDING_PROVIDER` in `.env`:

| Provider | `EMBEDDING_MODEL` | Dims | Input limit | Task handling |
|----------|-------------------|------|-------------|---------------|
| `gemini` (default) | `gemini-embedding-2` | 3072 | 8192 tok | Prompt prefixes: `title: … \| text: …` for chunks, `task: search result \| query: …` for searches. Auto-normalises. |
| `gemini` | `gemini-embedding-001` | 3072 | 2048 tok | `taskType`: `RETRIEVAL_DOCUMENT` for chunks, `RETRIEVAL_QUERY` for searches. |
| `fal` | `openai/text-embedding-3-large` | 3072 | 8191 tok | None. Note the `openai/` prefix. |

Models differ in how the task is signalled, and getting it wrong degrades retrieval
*silently* — `gemini-embedding-2` accepts a `taskType` parameter and ignores it,
returning HTTP 200. `MODEL_SPECS` in `embedding_service.py` records the correct
handling per model, and `validate_embedding_config()` refuses to start on a
provider/model/dimension mismatch.

`EMBEDDING_DIMENSIONS` must match the `vector(N)` column on `knowledge_chunks`.
Changing it requires dropping and recreating that column — mixing vectors from
different models or dimensions in one table makes similarity search meaningless.

Gemini's free tier allows **100 embed requests per minute**, and each text
inside a batch counts as one request. `EMBEDDING_REQUESTS_PER_MINUTE` paces
calls client-side so large PDFs wait instead of failing with 429s.

## Editing documents

Any content change deletes every chunk for that document and re-embeds the whole
thing. Chunk boundaries shift when text is edited, so patching individual chunks
would mean tracking a diff-to-chunk mapping for very little gain at this scale.

Moving a document does **not** re-embed. Renaming does *only when the configured
model folds the title into the embedded text* — `gemini-embedding-2` does (the
title is part of its document prompt prefix), `gemini-embedding-001` does not.
`model_uses_title()` decides, so the behaviour follows the model automatically.

**Switching embedding models requires re-embedding everything.** Vectors from two
models are not comparable: the same chunk embedded by `gemini-embedding-001` and
`gemini-embedding-2` scores ~0.00 cosine against itself. Changing `EMBEDDING_MODEL`
without re-embedding leaves the old vectors in place and searches return
near-random results with no error anywhere. There is no re-embed job yet, so the
migration today is: drop `knowledge_chunks` and `knowledge_documents`, restart
(the schema is recreated automatically), and re-upload.

## Deploying

See **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**. Short version: one Docker
container on the EC2 host that already runs Postgres, with nginx terminating TLS
in front of it.

**Vercel cannot host the API.** Postgres is bound to `localhost` on that host and
only reachable over an SSH tunnel, which a serverless function cannot hold open —
and uploads routinely run past any serverless duration cap. The deployment doc
covers this in detail.

## Authentication

**Always on.** There is no setting to disable it, so there is no way to end up
serving an open admin API by forgetting one.

```bash
python -m app.admin_cli create alice     # prompts for a password
python -m app.admin_cli list
python -m app.admin_cli passwd alice     # also signs out that user everywhere
python -m app.admin_cli disable alice    # revokes their sessions immediately
```

Signing in exchanges a username and password for a session token, which the UI
stores and sends as `Authorization: Bearer <token>`. Sessions are rows in
`admin_sessions`, not JWTs, so signing out revokes access immediately rather
than waiting for an expiry; only a SHA-256 hash of each token is stored, so a
database dump cannot be replayed as a live login. Passwords are bcrypt-hashed.

`ADMIN_API_KEY` still works alongside sessions, as a machine key for scripts:

```bash
curl -H "Authorization: Bearer $ADMIN_API_KEY" localhost:8000/api/v1/stats
```

**Starting with no admin users is refused**, with a message telling you to
create one — a deployment nobody can sign in to is broken, and should say so at
startup rather than at the first sign-in attempt.

`/health` and the UI's own HTML stay public — you cannot show a sign-in screen
without being able to load the page that shows it.

## Rotating the embedding API key

Gemini's free tier runs out, so the key is replaceable at runtime from
**Settings** in the admin UI, or:

```bash
curl -X PUT localhost:8000/api/v1/settings/embedding/api-key   -H 'Content-Type: application/json'   -d '{"api_key": "AQ.…"}'
```

The key is verified against the provider before it is accepted, so a bad key can
never displace a working one, and it is written back to `.env` so it survives a
restart. It is returned to clients only as a masked preview — never in full.

**This endpoint is only as protected as the service is.** With `ADMIN_API_KEY`
unset, anyone who can reach the port can replace the key. Set it before running
anywhere but localhost.

## Schema migrations

There is no Alembic. `app/db/init_db.py` holds a list of idempotent SQL statements
applied on every startup, run after `create_all`. Any schema change needs an entry
there that is safe to run repeatedly — `create_all` never alters an existing table.

## Verifying ingestion

After uploading a document, run `sql/verify_ingestion.sql` against the database
to confirm chunks were written and embedded.

## API Endpoints

**[docs/API_GUIDE.md](docs/API_GUIDE.md)** documents every endpoint with a real
request and the response it actually returns, plus the error shapes. The table
below is the index.

Every content endpoint acts on one knowledge base, chosen with `?kb=<slug>` or an
`X-Knowledge-Base` header, and falls back to the default when neither is given.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/documents` | Add a new document |
| `GET` | `/api/v1/documents` | List all documents (paginated) |
| `GET` | `/api/v1/documents/{id}` | Get a document with its chunks |
| `PUT` | `/api/v1/documents/{id}` | Update a document |
| `DELETE` | `/api/v1/documents/{id}` | Delete a document |
| `PUT` | `/api/v1/documents/{id}/replace` | Replace content with a new file or text |
| `POST` | `/api/v1/documents/{id}/append` | Append content and re-chunk |
| `POST` | `/api/v1/documents/upload` | Upload a file (multipart: `file`, `title`, `metadata`, `folder_path`, `doc_type`) |
| `POST` | `/api/v1/search` | Similarity search (filters: `doc_type`, `folder`) |
| `GET` | `/api/v1/tree` | Full directory tree — folders + documents, one call |
| `GET` | `/api/v1/stats` | Counts, per-folder breakdown, embedding health |
| `GET` | `/api/v1/formats` | Supported upload extensions and doc types |
| `POST` | `/api/v1/auth/login` | Sign in, returns a session token |
| `POST` | `/api/v1/auth/logout` | Revoke the current session |
| `GET` | `/api/v1/auth/me` | Who is signed in, and whether auth is on |
| `GET` | `/api/v1/settings/embedding` | Active embedding config (API key masked) |
| `PUT` | `/api/v1/settings/embedding/api-key` | Replace the embedding API key |
| `GET` | `/api/v1/knowledge-bases` | List registered knowledge bases |
| `POST` | `/api/v1/knowledge-bases` | Register another pgvector database, choosing its model |
| `GET` | `/api/v1/knowledge-bases/{slug}` | One knowledge base |
| `PUT` | `/api/v1/knowledge-bases/{slug}` | Rename, deactivate, make default, or repoint |
| `POST` | `/api/v1/knowledge-bases/{slug}/check` | Re-check reachability |
| `DELETE` | `/api/v1/knowledge-bases/{slug}` | Unregister (never drops its tables) |
| `POST` | `/api/v1/knowledge-bases/test-connection` | Try a connection string without storing it |
| `GET` | `/api/v1/embedding-models` | Models available when creating a knowledge base |

## Supported file formats

Upload accepts `.pdf`, `.docx`, `.pptx`, `.md`, `.txt`, `.html`, `.csv`, `.xlsx`,
and `.json`. Text extraction is the only format-specific step — once a file is
text, chunking and embedding are identical for every format. `GET /api/v1/formats`
returns the live list so the UI never hardcodes it.

Two caveats:

- **Scanned PDFs are rejected.** There is no OCR; an image-only PDF has no
  extractable text and fails with a 400 rather than storing an empty document.
- **Spreadsheets are a poor fit for retrieval.** `.csv` / `.xlsx` are stored one
  record per chunk with column names repeated, which works for reference tables
  (fee slabs, plan comparisons). Data you would query with a `WHERE` clause
  belongs in Postgres, not here.

## Authoring content

**[docs/CONTENT_GUIDE.md](docs/CONTENT_GUIDE.md) is the format to hand to whoever
writes knowledge base content**, with two conformant examples in
[docs/examples/](docs/examples/).

Markdown is the preferred format, because it is the only one where the author
controls where the content gets split.

### How chunking works

A chunk is what the assistant retrieves — **alone**, with no document around it.
So the chunker follows the document's own structure rather than a character
count:

- **Headings are hard boundaries.** Two sections never share a chunk.
- **Tables and fenced code blocks are never split.** If a table is too large,
  its header row is repeated in every piece.
- **Every chunk is prefixed with its breadcrumb** — `Document > Section >
  Subsection`. This is stored, not just embedded, because retrieval hands that
  exact text to the assistant. A chunk reading "same shape as the deal validity
  above" is worse than useless: there is no "above".
- Blocks are merged up to `CHUNK_SIZE` (default 1200 characters) and only split
  mid-block when a single block exceeds it.

`.docx`, `.html` and `.pptx` extraction promotes their headings to markdown, so
they benefit from the same structure-aware splitting. Plain `.txt` and PDFs have
no headings to work with and fall back to paragraph boundaries.

### Front matter drives real behaviour

YAML front matter on a markdown file is not decoration:

| Key | Becomes |
|-----|---------|
| `title` | The document title (so the upload form's title becomes optional) |
| `type` | `doc_type` — the chunking strategy and retrieval filter |
| everything else | Document metadata, filterable later |

Dates are coerced to ISO strings, since `last_reviewed: 2026-08-18` is parsed by
YAML as a `date` object that JSONB cannot store.

## Document types

`doc_type` selects the **chunking strategy** and is an open vocabulary:

- **`text`** — prose (FAQs, policies, guides). Recursive character splitting.
- **`api`** — one API in an API catalogue knowledge base. Kept whole,
  never split, with each example utterance indexed separately so a merchant's
  phrasing matches directly. See [docs/API_CATALOG_GUIDE.md](docs/API_CATALOG_GUIDE.md).

`source_format` records **where the content came from** (`pdf`, `docx`, `html`,
`md`, `manual`, …). The two are deliberately separate: a `.docx` and a `.pdf`
holding the same policy are the same *type* of knowledge from different
*sources*.

## What belongs in this knowledge base

Product knowledge only — what features do, how they work, policies, guides.

**Never upload merchant data.** Coupon lists, khata balances, transaction
exports and the like belong in the application database, reached by a tool at
query time. Embedded data goes stale immediately, cannot be redacted from a
vector, and there is no per-merchant isolation in `knowledge_chunks`.

## Multiple knowledge bases

The service starts with one: the database in `DATABASE_URL`, embedded with the
model in `EMBEDDING_MODEL`. That one is the **default** — it answers every request
that names no other, and its connection string stays in the environment rather
than being copied into a table.

More can be added from the **Knowledge Bases** page. Each needs a Postgres
connection string and an embedding model, chosen from a dropdown at that moment
and fixed from then on:

- **The model cannot be changed later.** Every vector in a knowledge base comes
  from one model, and vectors from two models are not comparable — the same
  sentence embedded by `gemini-embedding-001` and `gemini-embedding-2` scores near
  zero against itself. Moving to a different model means a new knowledge base and
  a re-ingest, with both searchable while you do it.
- **Connection strings are encrypted** with `SECRET_KEY` before they are stored,
  and only ever come back as `user@host:port/database` with the password removed.
- **API keys are not per knowledge base.** They stay in the environment, one per
  provider, and are shared by every knowledge base using that provider.
- **No database can serve two knowledge bases.** Each one writes an ownership
  marker into the database it uses, so the clash is caught even when the same
  host is spelled two different ways.
- **Removing one never drops its tables.** Unregistering is reversible; deleting
  data is not.

If the Postgres user cannot create databases — which is the common case — give the
knowledge base its own schema instead by appending `?schema=name` to the
connection string. The tables land there, and two knowledge bases on one database
cannot see each other's.

The host has to be reachable **from the server**, not from your laptop. For a
database behind SSH, run the tunnel on the server and point the connection string
at the local end of it; this service does not manage tunnels, because a tunnel it
opened would die with the process and its key would have to be stored somewhere.

## Two knowledge bases, two jobs

The assistant this service feeds has two modes, and they want different
retrieval:

| | Product knowledge | API catalogue |
|---|---|---|
| Answers | "How do I create an offer?" | "Start a 20% off sale" |
| Retrieval finds | Passages that help answer | One action, or nothing |
| Optimises for | Recall | Precision |
| Being approximately right | Fine — the answer still reads well | **A failure** — the wrong thing gets done |
| Chunking | Split on headings, ~1200 chars | One API per chunk, never split |

They are separate knowledge bases because almost every setting wants a
different value — chunk size above all, since a tool card that splits returns
half a tool. Separation also means the catalogue can be rebuilt when the backend
ships without touching product knowledge.

### What this service does not do

**It never calls the APIs in the catalogue.** The only outbound requests it makes
are to the embedding provider and to Postgres. It stores cards, retrieves them,
and shows the team what a query returns.

Selecting an action at runtime and calling it is the orchestrator's job — a
separate system that reads the same pgvector database. `seeds/eval/selection.py`
is a readable reference for the collapsing and ranking that turns chunk hits into
one API, and `seeds/eval/run_eval.py` uses it to measure whether the catalogue
retrieves correctly.

The format the backend team fills in:
**[docs/API_CATALOG_GUIDE.md](docs/API_CATALOG_GUIDE.md)**.

## Seed content and measuring retrieval

`seeds/` holds synthetic content for both knowledge bases — 19 product documents
and 41 API cards across 10 domains — plus labelled evaluation sets.

```bash
python seeds/load_seeds.py --base http://127.0.0.1:8000   --dsn 'postgresql://user:pass@host:5432/db?schema=api_catalog'

python seeds/eval/run_eval.py --base http://127.0.0.1:8000
python seeds/eval/run_eval.py --base http://127.0.0.1:8000 --sweep
```

Everything in `seeds/` is marked `status: example`. **The API paths and fields
are invented** — they exist to measure retrieval before the real catalogue
arrives, not to be called.

Results break down by tier, because one overall number hides the failures that
matter. See [seeds/README.md](seeds/README.md).

## Architecture

```
Admin → REST API ─┬─ control plane   : admin users, sessions, knowledge-base registry
                  │
                  └─ Knowledge Service → Chunking + Embedding → pgvector
                       (one per knowledge base, its own database and model)
```

The service is the **write side** of the RAG pipeline. The chatbot's orchestrator service will read from the same pgvector database for retrieval.
