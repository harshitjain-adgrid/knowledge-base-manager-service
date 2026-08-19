# API guide

Every endpoint this service exposes, with a real request and the response it
actually returns. The examples below were captured from a running instance, not
written by hand — the field names, shapes and error messages are what you will
see.

Interactive docs are also served at `/docs` (Swagger) and `/redoc`.

---

## Contents

- [The basics](#the-basics) — base URL, authentication, choosing a knowledge base, errors
- [Authentication](#authentication) — `/auth/login`, `/auth/me`, `/auth/logout`
- [Knowledge bases](#knowledge-bases) — list, add, test, re-check, update, remove
- [Documents](#documents) — create, list, read, update, delete
- [Uploading files](#uploading-files) — upload, replace, append
- [Search](#search)
- [Browsing and statistics](#browsing-and-statistics) — `/tree`, `/stats`, `/formats`
- [Settings](#settings) — embedding configuration and the API key
- [Health](#health)
- [Error reference](#error-reference)
- [A worked example](#a-worked-example)

---

## The basics

### Base URL

Everything lives under `/api/v1`, except `/health`, which is deliberately
outside it so a load balancer can reach it without a token.

```
https://kb.internal.example.com/api/v1
```

### Authentication

Every `/api/v1` endpoint requires a bearer token. There are two kinds and the
server accepts either:

| Credential | Where it comes from | Use it for |
|---|---|---|
| Session token | `POST /api/v1/auth/login` | The admin UI, and anything a person drives |
| `ADMIN_API_KEY` | The server's environment | Scripts, cron jobs, curl |

```http
Authorization: Bearer 9f3c1a2b4d5e6f708192a3b4c5d6e7f8
```

Only three paths are open without one: `/health`, `/api/v1/auth/login`, and
`/api/v1/auth/me` (which answers "am I signed in?" and so has to be reachable
when you are not).

### Choosing a knowledge base

Every content endpoint acts on exactly one knowledge base. Name it in one of two
ways, or leave it out and get the default:

```http
GET /api/v1/documents?kb=merchant-ops
```

```http
GET /api/v1/documents
X-Knowledge-Base: merchant-ops
```

The query parameter wins when both are present. **A request that names none goes
to the default knowledge base**, which is why every client written before
multiple knowledge bases existed still works unchanged.

Responses that could be ambiguous say which knowledge base answered — `/stats`,
`/search` and `/settings/embedding` all carry a `knowledge_base` field.

### Errors

Errors come back as JSON with a `detail` field:

```json
{ "detail": "There is no knowledge base called 'nope'." }
```

Authentication failures use a slightly different shape, because they are produced
by middleware before the route is reached:

```json
{ "error": "Unauthorized", "detail": "Sign in to continue." }
```

Validation failures (422) list the offending fields:

```json
{
  "detail": [
    {
      "type": "string_pattern_mismatch",
      "loc": ["body", "doc_type"],
      "msg": "String should match pattern '^[a-z0-9_-]+$'",
      "input": "Not Valid"
    }
  ]
}
```

Every response carries an `X-Request-ID` header. A 500 puts the same id in its
message, so a report of "it failed at 11:04" can be found in the logs exactly.

---

## Authentication

### `POST /api/v1/auth/login`

Exchange a username and password for a session token.

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "correct horse battery staple"
}
```

```json
{
  "token": "9f3c1a2b4d5e6f708192a3b4c5d6e7f8",
  "username": "admin",
  "expires_in_hours": 12
}
```

The token is shown once and never returned again — only a hash of it is stored,
so a database dump cannot be replayed as a live session.

**401** — `{"detail": "Incorrect username or password."}`. One message for both
cases: saying which half was wrong tells an attacker which usernames exist.

Accounts are created on the server, not through the API:

```bash
python -m app.admin_cli create <username>
```

### `GET /api/v1/auth/me`

Who is signed in. Public, so the UI can ask before it has a token.

```json
{
  "auth_enabled": true,
  "authenticated": true,
  "username": "admin"
}
```

With no token, `authenticated` is `false` and `username` is `null` — still a 200.

### `POST /api/v1/auth/logout`

Revokes the token immediately. Sessions are rows rather than JWTs precisely so
that signing out actually revokes access instead of waiting for an expiry.

```json
{ "message": "Signed out.", "detail": null }
```

---

## Knowledge bases

A knowledge base is one Postgres database with pgvector, plus the embedding model
its vectors were produced with. Those two travel together because they have to:
vectors written by one model are meaningless to another.

### `GET /api/v1/knowledge-bases`

```json
{
  "knowledge_bases": [
    {
      "id": "f66e2232-5344-47a5-aafb-9fb45771e978",
      "slug": "default",
      "name": "Primary knowledge base",
      "description": "The knowledge base configured in the server's environment.",
      "table_prefix": "kb_default",
      "dsn_preview": "qa@localhost:5434/vector_qa",
      "embedding_provider": "gemini",
      "embedding_model": "gemini-embedding-2",
      "embedding_dimensions": 3072,
      "chunk_size": 1200,
      "chunk_overlap": 150,
      "is_default": true,
      "is_active": true,
      "from_environment": true,
      "last_error": null,
      "last_checked_at": null,
      "created_at": "2026-08-19T05:13:50.377520Z",
      "updated_at": "2026-08-19T05:28:51.827200Z"
    }
  ],
  "total": 1,
  "default_slug": "default"
}
```

`dsn_preview` is `user@host:port/database` — **the password is never part of any
response.** `from_environment: true` marks the knowledge base whose connection
string comes from `DATABASE_URL` rather than from a stored row.

`table_prefix` names this knowledge base's tables — `kb_default_documents` and
`kb_default_chunks`. Every knowledge base has its own pair in one schema, so a
consumer reading the database directly routes on a table name rather than a
filter. Two knowledge bases can share a database; they cannot share a prefix.

### `GET /api/v1/embedding-models`

What the model dropdown offers, and the constraints that go with each choice.

```json
{
  "models": [
    {
      "model": "gemini-embedding-2",
      "provider": "gemini",
      "allowed_dimensions": [768, 1536, 3072],
      "default_dimensions": 3072,
      "input_token_limit": 8192,
      "multimodal": true,
      "key_configured": true
    },
    {
      "model": "openai/text-embedding-3-large",
      "provider": "fal",
      "allowed_dimensions": [256, 1024, 1536, 3072],
      "default_dimensions": 3072,
      "input_token_limit": 8191,
      "multimodal": false,
      "key_configured": false
    }
  ]
}
```

`key_configured: false` means that provider's API key is not set on this server,
so the model cannot be used. Keys live in the environment, one per provider —
they are never stored per knowledge base.

### `POST /api/v1/knowledge-bases/test-connection`

Opens a throwaway connection and reports what happened. Nothing is stored, so
this is safe to call as often as you like while someone types.

```http
POST /api/v1/knowledge-bases/test-connection
Content-Type: application/json

{ "dsn": "postgresql://kb_user:secret@10.0.0.7:5432/merchant_ops" }
```

```json
{
  "ok": true,
  "message": "Connected — PostgreSQL 16.15 (Debian 16.15-1.pgdg12+2), pgvector 0.8.6 installed.",
  "dsn_preview": "kb_user@10.0.0.7:5432/merchant_ops"
}
```

Failures are still `200` with `ok: false`, because a failed test is an answer
rather than an error:

```json
{ "ok": false, "message": "Rejected by the server: password authentication failed for user \"qa\"" }
```

```json
{ "ok": false, "message": "'mysql' is not a Postgres connection string. It should look like postgresql://user:password@host:5432/database" }
```

### `POST /api/v1/knowledge-bases`

Register another database and choose the model its content will be embedded
with.

```http
POST /api/v1/knowledge-bases
Content-Type: application/json

{
  "name": "Merchant Ops",
  "description": "Support runbooks for the ops team",
  "dsn": "postgresql://kb_user:secret@10.0.0.7:5432/merchant_ops",
  "embedding_provider": "gemini",
  "embedding_model": "gemini-embedding-2",
  "embedding_dimensions": 3072
}
```

```json
{
  "id": "1b8d5b1e-1f2c-4a77-9a2c-0f2b7d3e9c41",
  "slug": "merchant-ops",
  "name": "Merchant Ops",
  "description": "Support runbooks for the ops team",
  "dsn_preview": "kb_user@10.0.0.7:5432/merchant_ops",
  "embedding_provider": "gemini",
  "embedding_model": "gemini-embedding-2",
  "embedding_dimensions": 3072,
  "chunk_size": 1200,
  "chunk_overlap": 150,
  "is_default": false,
  "is_active": true,
  "from_environment": false,
  "last_error": null,
  "last_checked_at": "2026-08-19T05:36:12.463560Z",
  "created_at": "2026-08-19T05:36:12.471782Z",
  "updated_at": "2026-08-19T05:36:12.471782Z"
}
```

| Field | Required | Notes |
|---|---|---|
| `name` | yes | 1–128 characters |
| `dsn` | yes | Stored encrypted, never returned |
| `embedding_model` | yes | One of `GET /embedding-models` |
| `embedding_dimensions` | yes | Must be in that model's `allowed_dimensions` |
| `slug` | no | Derived from the name — `Merchant Ops` → `merchant-ops`. Also names its tables: `kb_merchant_ops_documents` and `kb_merchant_ops_chunks` |
| `description` | no | |
| `chunk_size` | no | Defaults to the server's `CHUNK_SIZE` |
| `chunk_overlap` | no | Defaults to the server's `CHUNK_OVERLAP` |

The order of work is validate → connect → create the tables → write the row. A
knowledge base that appears in the list has been proven to work; if anything
fails, nothing is registered.

**Sharing a database is fine.** A knowledge base gets its own tables, named
after its identifier, so several can live in one schema without touching each
other — including this service's own database. No `CREATE DATABASE` privilege
needed, and no schema of its own.

**Things that are refused, and why** — all `400`:

| Message | Cause |
|---|---|
| `'not-a-model' is not a known embedding model. Choose one of: …` | Typo, or a model this build cannot call |
| `'gemini-embedding-2' is a gemini model, but the provider given was 'fal'.` | Mismatched pair |
| `999 dimensions is not supported by 'gemini-embedding-2'. Supported: 768, 1536, 3072.` | Width the model cannot produce |
| `'openai/text-embedding-3-large' needs a fal API key, and FAL_KEY is not set…` | Provider has no key on this server |
| `'x' would use the same tables as 'y'…` | Two identifiers shortened to the same table prefix |
| `kb_x_chunks already holds 25 3072-dimension vectors, but this knowledge base is configured for 768…` | Existing vectors the chosen model cannot read |
| `SECRET_KEY is not set on the server, so a connection string cannot be stored safely…` | Add one to `.env` and restart |

### `GET /api/v1/knowledge-bases/{slug}`

One knowledge base, same shape as a list entry. **404** if the slug is unknown.

### `PUT /api/v1/knowledge-bases/{slug}`

```http
PUT /api/v1/knowledge-bases/merchant-ops
Content-Type: application/json

{ "description": "Runbooks and escalation paths", "make_default": true }
```

| Field | Effect |
|---|---|
| `name` | Rename |
| `description` | Replace the description |
| `is_active` | Deactivate or reactivate |
| `make_default` | Answer requests that name no knowledge base |
| `dsn` | Point at a different database — tested before it is accepted |

**The model, provider and dimensions are not editable.** Changing any of them
would leave the stored vectors describing one embedding space and new ones
describing another, with no error anywhere — retrieval would just quietly get
worse. Moving to a different model means adding a new knowledge base and
re-ingesting; both stay searchable while you do.

The default knowledge base is further protected: it cannot be deactivated, and
its connection string comes from `DATABASE_URL`, so `dsn` is refused with a
message saying where to change it instead.

### `POST /api/v1/knowledge-bases/{slug}/check`

Reach a registered knowledge base again and update its status. Use it to clear a
stale `last_error` after a host comes back.

```json
{
  "ok": true,
  "message": "Connected — PostgreSQL 16.15 (Debian 16.15-1.pgdg12+2), pgvector 0.8.6 installed.",
  "dsn_preview": "kb_user@10.0.0.7:5432/merchant_ops"
}
```

### `DELETE /api/v1/knowledge-bases/{slug}`

```json
{
  "message": "'merchant-ops' was removed from the registry.",
  "detail": "Its tables (kb_merchant_ops_documents, kb_merchant_ops_chunks) at kb_user@10.0.0.7:5432/merchant_ops were left untouched."
}
```

**This never drops tables.** Unregistering is reversible; deleting data is not,
and the database belongs to whoever set it up. Re-registering under the same
identifier finds the same tables and picks up where it left off.

The default knowledge base cannot be removed — **400**, `"Make another one the
default first."`

---

## Documents

All of these act on the knowledge base named by `?kb=` or `X-Knowledge-Base`,
defaulting to the default one.

### `POST /api/v1/documents`

Add a document as text. It is chunked and embedded before the response returns.

```http
POST /api/v1/documents?kb=merchant-ops
Content-Type: application/json

{
  "title": "Refund window",
  "content": "# Refund window\n\nA merchant can reverse a completed transaction within 24 hours…",
  "doc_type": "text",
  "folder_path": "/payments/",
  "metadata": { "owner": "support", "audience": "merchant" }
}
```

**201**

```json
{
  "id": "9c1f0f4a-2a55-4c8e-90a2-3b5f6c1d2e34",
  "title": "Refund window",
  "content": "# Refund window\n\nA merchant can reverse…",
  "doc_type": "text",
  "source_format": "manual",
  "metadata": { "owner": "support", "audience": "merchant" },
  "chunk_count": 2,
  "embedded_chunk_count": null,
  "file_name": null,
  "file_size": null,
  "folder_path": "/payments/",
  "created_at": "2026-08-19T05:36:24.117320Z",
  "updated_at": "2026-08-19T05:36:24.117320Z"
}
```

| Field | Required | Notes |
|---|---|---|
| `title` | yes | 1–512 characters |
| `content` | yes | Markdown is understood — headings drive the chunking |
| `doc_type` | no | Default `text`. `api_definition` chunks one endpoint per chunk. Must match `^[a-z0-9_-]+$` |
| `folder_path` | no | Default `/`. Normalised, so `HR`, `/HR` and `/HR/` are one folder |
| `metadata` | no | Any JSON object; copied onto every chunk |

**400** if the content produces no chunks — whitespace, or a scanned PDF with no
text layer. Storing it would create a document nothing can ever retrieve, with no
error at the point someone added it.

### `GET /api/v1/documents`

```http
GET /api/v1/documents?folder=/offers/&limit=20
```

```json
{
  "documents": [
    {
      "id": "c66983ab-9d94-48a6-ab1c-29581b4b3e6a",
      "title": "Deals & Discounts - Create API",
      "content": "Create Deal / Create Discount — Request & Response Structure…",
      "doc_type": "text",
      "source_format": "pdf",
      "metadata": { "source": "file_upload", "page_count": 10 },
      "chunk_count": 15,
      "embedded_chunk_count": null,
      "file_name": "deals-discounts-create-api.pdf",
      "file_size": 490832,
      "folder_path": "/product/offers/",
      "created_at": "2026-08-18T10:49:48.027762Z",
      "updated_at": "2026-08-18T11:18:01.896196Z"
    }
  ],
  "total": 3,
  "skip": 0,
  "limit": 1
}
```

| Parameter | Default | Notes |
|---|---|---|
| `doc_type` | — | Exact match |
| `search` | — | Case-insensitive substring of title or content. Not vector search — use `/search` for that |
| `folder` | — | Exact folder, normalised |
| `skip` | `0` | |
| `limit` | `20` | 1–100 |

`embedded_chunk_count` is `null` here on purpose: counting it would mean loading
every chunk's vector, which is megabytes per document. `GET /documents/{id}`
returns it.

### `GET /api/v1/documents/{id}`

The document with all of its chunks, in order.

```json
{
  "id": "440b753f-25b5-4fde-b956-ab951c23990e",
  "title": "Creating an Offer",
  "content": "---\ntitle: Creating an Offer\n…",
  "doc_type": "guide",
  "source_format": "md",
  "chunk_count": 6,
  "embedded_chunk_count": 6,
  "folder_path": "/offers/",
  "chunks": [
    {
      "id": "fca5bfae-2f3e-49f7-af5b-201c251028e1",
      "chunk_index": 0,
      "content": "Creating an Offer > Creating an Offer\n\nA merchant can create a percentage or flat-amount offer…",
      "metadata": {
        "section": "Creating an Offer",
        "heading_path": ["Creating an Offer"],
        "chunk_type": "text",
        "owner": "growth-team"
      },
      "created_at": "2026-08-18T10:47:49.702124Z"
    }
  ],
  "created_at": "2026-08-18T10:47:49.515457Z",
  "updated_at": "2026-08-18T10:47:49.515457Z"
}
```

`chunk_count` vs `embedded_chunk_count` differing means some chunks have no
vector and cannot be retrieved — worth checking after a failed upload.

**404** — `{"detail": "Document not found."}`

### `PUT /api/v1/documents/{id}`

Every field is optional; only what you send changes.

```http
PUT /api/v1/documents/440b753f-25b5-4fde-b956-ab951c23990e
Content-Type: application/json

{ "folder_path": "/offers/merchant/", "metadata": { "status": "review" } }
```

Two behaviours worth knowing:

- **Metadata is merged, not replaced.** A `PUT` that mentions only `status` keeps
  every other key. Replacing was a quiet way to lose data.
- **Changing `content` or `doc_type` re-chunks and re-embeds the whole
  document.** Moving it between folders, or editing only its metadata, does not.
  Renaming it re-embeds only when the knowledge base's model folds the title into
  the embedded text, which `gemini-embedding-2` does and `gemini-embedding-001`
  does not.

### `DELETE /api/v1/documents/{id}`

```json
{
  "message": "Document deleted successfully.",
  "detail": "Document 440b753f-… and all its chunks have been removed."
}
```

Chunks cascade with the document. There is no undo.

---

## Uploading files

### `POST /api/v1/documents/upload`

`multipart/form-data`. The file's text is extracted, chunked and embedded.

```bash
curl -X POST 'https://kb.example.com/api/v1/documents/upload?kb=merchant-ops' \
  -H "Authorization: Bearer $TOKEN" \
  -F 'file=@creating-an-offer.md' \
  -F 'folder_path=/offers/' \
  -F 'metadata={"owner":"growth-team"}'
```

| Part | Required | Notes |
|---|---|---|
| `file` | yes | See `GET /formats` for accepted types |
| `title` | no | Taken from markdown front matter when omitted |
| `folder_path` | no | Default `/` |
| `doc_type` | no | Inferred from the file type |
| `metadata` | no | A JSON **string** — this is a form field, not JSON body |

Response is the same `DocumentResponse` shape as `POST /documents`.

For markdown, front matter is authoritative for what it declares — `title`,
`doc_type` and any other keys become the document's metadata — but an explicit
form value still wins. See [CONTENT_GUIDE.md](CONTENT_GUIDE.md) for the format
the team should be writing.

| Status | Cause |
|---|---|
| **400** | Unsupported type, empty file, invalid metadata JSON, no extractable text, or no title anywhere |
| **413** | Larger than `MAX_UPLOAD_SIZE_MB` (20 MB by default) |

**Uploads are synchronous.** Embedding a 50-page PDF takes around 47 seconds and
a 150-page one around 141; the request stays open throughout. If a proxy sits in
front of this service, its read timeout must be well above 60 seconds.

### `PUT /api/v1/documents/{id}/replace`

Swap a document's content entirely — a new revision of the same PDF, say. Every
old chunk and vector is deleted and rebuilt.

```bash
curl -X PUT "https://kb.example.com/api/v1/documents/$ID/replace" \
  -H "Authorization: Bearer $TOKEN" \
  -F 'file=@deals-discounts-create-api-v2.pdf'
```

Send either `file` or `content`; sending neither is a **400**.

### `POST /api/v1/documents/{id}/append`

Add to the end of an existing document. The whole document is re-chunked, because
appending shifts every boundary after the join.

```bash
curl -X POST "https://kb.example.com/api/v1/documents/$ID/append" \
  -H "Authorization: Bearer $TOKEN" \
  -F 'content=## Escalation

Contact the payments on-call rota.'
```

---

## Search

### `POST /api/v1/search`

Vector similarity search. This is the endpoint that shows what the assistant
would retrieve for a question.

```http
POST /api/v1/search
Content-Type: application/json

{ "query": "how do I create an offer", "top_k": 2 }
```

```json
{
  "query": "how do I create an offer",
  "results": [
    {
      "chunk_id": "fca5bfae-2f3e-49f7-af5b-201c251028e1",
      "document_id": "440b753f-25b5-4fde-b956-ab951c23990e",
      "document_title": "Creating an Offer",
      "doc_type": "guide",
      "folder_path": "/offers/",
      "chunk_index": 0,
      "content": "Creating an Offer > Creating an Offer\n\nA merchant can create a percentage or flat-amount offer from the Offers screen…",
      "similarity": 0.8305,
      "metadata": {
        "section": "Creating an Offer",
        "heading_path": ["Creating an Offer"],
        "chunk_type": "text",
        "owner": "growth-team",
        "audience": "merchant",
        "last_reviewed": "2026-08-18"
      }
    }
  ],
  "total_results": 2,
  "knowledge_base": "default",
  "embedding_model": "gemini-embedding-2",
  "embed_ms": 656.1,
  "search_ms": 2251.6
}
```

| Field | Default | Notes |
|---|---|---|
| `query` | — | Natural language. Any language — the models are multilingual |
| `top_k` | `5` | 1–200. Generous because a caller may be collapsing chunks into one entry per document rather than reading them |
| `doc_type` | — | Restrict to one kind of document |
| `folder` | — | Restrict to one folder |

`similarity` is cosine similarity in 0–1; higher is closer. As a rough guide on
this corpus, above 0.80 is a direct answer, 0.70–0.80 is related, and below 0.65
usually means nothing in the knowledge base covers the question.

`embed_ms` and `search_ms` are separated on purpose: the first is an API round
trip to the embedding provider, the second is the database. They grow for
completely different reasons, and only the second one tells you when an index is
needed.

The query is embedded with **this knowledge base's model**. Searching a knowledge
base built with a different model would project the query into a different space
and return noise rather than an error, which is why the model is fixed at
creation.

---

## Browsing and statistics

### `GET /api/v1/tree`

Everything the directory tree needs, in one payload. Folders are derived from
document paths and include intermediate levels, so `/product/` exists as a node
even though nothing is filed directly in it.

```json
{
  "folders": [
    { "path": "/", "document_count": 0 },
    { "path": "/khata/", "document_count": 1 },
    { "path": "/offers/", "document_count": 1 },
    { "path": "/product/", "document_count": 0 },
    { "path": "/product/offers/", "document_count": 1 }
  ],
  "documents": [
    {
      "id": "75936d04-36d2-45dc-95ec-2e1238bb6c29",
      "title": "What is Khata",
      "folder_path": "/khata/",
      "doc_type": "concept",
      "source_format": "md",
      "file_name": "what-is-khata.md",
      "file_size": 852,
      "chunk_count": 4,
      "embedded_chunk_count": 4,
      "created_at": "2026-08-18T10:47:56.306227Z",
      "updated_at": "2026-08-18T10:47:56.306227Z"
    }
  ],
  "total_documents": 3,
  "total_chunks": 25
}
```

`document_count` is direct children only, not recursive. The nesting is assembled
by the client, which keeps expanding and filtering instant.

### `GET /api/v1/stats`

```json
{
  "knowledge_base": "default",
  "total_documents": 3,
  "total_chunks": 25,
  "chunks_missing_embedding": 0,
  "documents_by_type": { "text": 1, "guide": 1, "concept": 1 },
  "documents_by_format": { "md": 2, "pdf": 1 },
  "documents_by_folder": { "/khata/": 1, "/offers/": 1, "/product/offers/": 1 },
  "recent_documents": [
    {
      "id": "c66983ab-9d94-48a6-ab1c-29581b4b3e6a",
      "title": "Deals & Discounts - Create API",
      "doc_type": "text",
      "source_format": "pdf",
      "folder_path": "/product/offers/",
      "created_at": "2026-08-18T10:49:48.027762Z"
    }
  ],
  "embedding_provider": "gemini",
  "embedding_model": "gemini-embedding-2",
  "configured_dimensions": 3072,
  "stored_dimensions": 3072,
  "dimensions_match": true,
  "chunk_storage_bytes": 1425408
}
```

Two fields deserve attention:

- `chunks_missing_embedding` above zero means some content is stored but
  unreachable by search.
- `dimensions_match: false` means the vectors in the database were produced at a
  different width from the one configured. That is the failure that destroys
  retrieval without any error surfacing, which is why it is measured from the
  data rather than assumed.

The whole thing is one database query. It used to be seven, which cost five
seconds over an SSH tunnel — the work was trivial, the latency was not.

### `GET /api/v1/formats`

What the upload endpoint accepts, so a client never has to hardcode it.

```json
{
  "extensions": [".csv", ".docx", ".htm", ".html", ".json", ".log", ".markdown",
                 ".md", ".pdf", ".pptx", ".text", ".txt", ".xlsx"],
  "tabular_formats": ["csv", "xlsx"],
  "doc_types": ["text", "api_definition"],
  "max_upload_size_mb": 20
}
```

---

## Settings

### `GET /api/v1/settings/embedding`

```json
{
  "knowledge_base": "default",
  "provider": "gemini",
  "model": "gemini-embedding-2",
  "dimensions": 3072,
  "batch_size": 20,
  "requests_per_minute": 90,
  "chunk_size": 1200,
  "chunk_overlap": 150,
  "api_key_set": true,
  "api_key_preview": "AQ.Ab…9BI-ALw",
  "known_models": ["gemini-embedding-001", "gemini-embedding-2"]
}
```

Model, dimensions and chunk sizes belong to the knowledge base being viewed. The
API key belongs to the provider and is shared by every knowledge base using it.

**The key is only ever a masked preview.** The real value never leaves the
server, in any response, ever.

### `PUT /api/v1/settings/embedding/api-key`

Rotate the provider's key without a redeploy — which is what you need when a
free-tier quota runs out mid-week.

```http
PUT /api/v1/settings/embedding/api-key
Content-Type: application/json

{ "api_key": "<the new key>", "persist": true }
```

```json
{
  "ok": true,
  "message": "Key accepted — gemini-embedding-2 responded with 3072 dimensions. Saved to .env, so it survives a restart.",
  "api_key_preview": "AQ.Ab…9BI-ALw",
  "persisted": true
}
```

The key is checked against the provider before it is accepted, so **a bad key can
never replace a working one**. A rejection is a **400** carrying the provider's
own reason:

```json
{ "detail": "Key rejected by Gemini: API key not valid. Please pass a valid API key." }
```

`persist: false` applies the key in memory only, and it is lost on restart.

---

## Health

### `GET /health`

No authentication. Safe for a load balancer or a container healthcheck.

```json
{
  "status": "healthy",
  "database": "connected",
  "version": "0.2.0",
  "environment": "development"
}
```

`status` is `degraded` and `database` is `disconnected` when the control-plane
database cannot be reached. The service still answers, so the failure is visible
rather than a connection refused.

---

## Error reference

| Status | Meaning | Typical cause |
|---|---|---|
| **400** | The request is wrong in a way only you can fix | Empty content, invalid metadata JSON, an impossible model and dimension pair, a database already in use |
| **401** | Not signed in | Missing, expired or revoked token |
| **404** | No such thing | Unknown document id, or a knowledge base slug that does not exist |
| **409** | The knowledge base is deactivated | Reactivate it before reading or writing |
| **413** | File too large | Above `MAX_UPLOAD_SIZE_MB` |
| **422** | The request body does not match the schema | Wrong type, missing field, a `doc_type` with capitals or spaces |
| **500** | Something broke on the server | The response carries a request id; find it in the logs |
| **503** | The service cannot reach a knowledge base | No default registered, or `SECRET_KEY` changed so a stored connection string cannot be decrypted |

---

## A worked example

Sign in, add a knowledge base, put a document in it, and search it.

```bash
#!/usr/bin/env bash
set -euo pipefail
BASE=https://kb.internal.example.com

# 1. Sign in
TOKEN=$(curl -sS -X POST "$BASE/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"…"}' | jq -r .token)
AUTH=(-H "Authorization: Bearer $TOKEN")

# 2. Check the connection before committing to it
curl -sS "${AUTH[@]}" -X POST "$BASE/api/v1/knowledge-bases/test-connection" \
  -H 'Content-Type: application/json' \
  -d '{"dsn":"postgresql://kb_user:secret@10.0.0.7:5432/merchant_ops"}' | jq .

# 3. Register it, choosing the model once and for all
curl -sS "${AUTH[@]}" -X POST "$BASE/api/v1/knowledge-bases" \
  -H 'Content-Type: application/json' \
  -d '{
        "name": "Merchant Ops",
        "dsn": "postgresql://kb_user:secret@10.0.0.7:5432/merchant_ops",
        "embedding_provider": "gemini",
        "embedding_model": "gemini-embedding-2",
        "embedding_dimensions": 3072
      }' | jq .

# 4. Upload into it — note ?kb=
curl -sS "${AUTH[@]}" -X POST "$BASE/api/v1/documents/upload?kb=merchant-ops" \
  -F 'file=@refund-window.md' \
  -F 'folder_path=/payments/' | jq '{id, title, chunk_count}'

# 5. Ask it something
curl -sS "${AUTH[@]}" -X POST "$BASE/api/v1/search?kb=merchant-ops" \
  -H 'Content-Type: application/json' \
  -d '{"query":"how long do I have to reverse a payment","top_k":3}' \
  | jq '.results[] | {document_title, similarity, section: .metadata.section}'
```

Scripts that run unattended should use `ADMIN_API_KEY` from the server's
environment instead of step 1 — it does not expire, so a cron job never wakes up
to a dead session.

---

## What this API does not do

Worth knowing before you build on it:

- **It never calls anything.** The only outbound requests this service makes are
  to the embedding provider and to Postgres. Selecting and calling an API from
  the catalogue is the orchestrator's job, and deliberately not this service's.

- **No re-embed job.** Changing a knowledge base's model means creating a new one
  and re-ingesting.
- **No rate limiting on `/auth/login`.** Brute force is bounded only by bcrypt's
  cost. Keep the service off the public internet.
- **No optimistic locking.** Two simultaneous `PUT`s to one document — last write
  wins, silently.
- **No pagination on `/tree`.** Fine for thousands of documents, not for
  hundreds of thousands.
- **Uploads are synchronous.** Anything past roughly 50 pages wants a background
  job rather than a longer timeout.
