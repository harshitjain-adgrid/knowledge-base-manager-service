# Deploying

## Why not Vercel

Vercel is a good host for static frontends and short-lived serverless functions.
This service is neither, and one of the reasons is absolute rather than a matter
of taste.

**The database is unreachable from Vercel.** Postgres on the EC2 host listens on
`localhost:5434` and is not exposed to the internet — a port scan of the host
finds only SSH open:

```
CLOSED  <ec2-host>:5434
CLOSED  <ec2-host>:5432
OPEN    <ec2-host>:22
```

Every connection today goes through an SSH tunnel. A Vercel function cannot hold
one open: it has no long-lived process to keep the tunnel up, no way to store a
private key safely, and a new sandbox per invocation. There is no configuration
that fixes this — it would mean exposing Postgres to the internet, which is a far
worse trade than picking a different host.

Four more reasons it would not work even with a reachable database:

| | Why it breaks |
|---|---|
| **Request duration** | A 50-page PDF takes ~47s to embed, 150 pages ~141s, in one request. Vercel caps function duration well below that on most plans. |
| **Read-only filesystem** | Rotating the embedding API key writes back to `.env`. Serverless filesystems are read-only apart from an ephemeral `/tmp`. |
| **Per-process rate limiter** | The Gemini rate limiter lives in memory. Ten concurrent function instances would allow ten times the configured rate and start collecting 429s. |
| **Cold-start migrations** | `init_db()` runs schema migrations at startup. On serverless that is DDL on every cold start, from every instance at once. |

The right shape for this app is **one long-lived process next to the database** —
which is also the simplest thing to operate.

---

## Recommended: Docker on the EC2 host

The app already serves the React bundle itself, so this is a single container.
Because it runs on the same host as Postgres, the SSH tunnel disappears
entirely — `localhost:5434` is simply correct there.

### 1. Get the code onto the host

```bash
ssh -i <your-key>.pem ec2-user@<ec2-host>
git clone <your-repo> chotu_rag && cd chotu_rag
```

### 2. Write the production `.env`

Never copy your local one — its `DATABASE_URL` is the tunnel, and the key in it
has been shared around.

```bash
cat > .env <<'EOF'
ENVIRONMENT=production

# Postgres is on this host, so no tunnel and no exposure to the network
DATABASE_URL=postgresql+asyncpg://qa:<password>@localhost:5434/vector_qa

# Needed only for a knowledge base on a *different* Postgres host — it encrypts
# that connection string before storing it. Knowledge bases in this service's own
# database store nothing and work without it. Generate with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
SECRET_KEY=<generated>

EMBEDDING_PROVIDER=fal
FAL_AI_API_KEY=<a fresh key, not the development one>
EMBEDDING_MODEL=gemini-embedding-2
EMBEDDING_DIMENSIONS=3072
MAX_EMBEDDING_BATCH_SIZE=20
EMBEDDING_REQUESTS_PER_MINUTE=90

CHUNK_SIZE=1200
CHUNK_OVERLAP=150

SESSION_TTL_HOURS=12
ADMIN_API_KEY=

MAX_UPLOAD_SIZE_MB=20
EOF

chmod 600 .env
```

### 3. Build and start

```bash
docker compose up -d --build
docker compose logs -f
```

Startup is expected to fail the first time with *"No admin users exist"*. That is
the fail-closed guard working — the service refuses to run in a state where
nobody can sign in.

### 4. Create the first admin user

```bash
docker compose run --rm chotu-rag python -m app.admin_cli create <username>
docker compose up -d
```

### 5. Put TLS in front of it

The container listens on port 8000 over plain HTTP. Session tokens travel in an
`Authorization` header, so **without TLS anyone on the network path can read a
token and use it.** Terminate TLS in nginx or an ALB:

```nginx
server {
    listen 443 ssl;
    server_name kb.internal.example.com;

    ssl_certificate     /etc/letsencrypt/live/.../fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/.../privkey.pem;

    # Uploads are embedded synchronously; a large PDF can take a couple of
    # minutes, so the default 60s proxy timeout would cut it off.
    proxy_read_timeout 300s;
    client_max_body_size 25M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Then restrict the security group so 8000 is not reachable from outside the host,
and 443 is open only to your office or VPN range. This is an internal admin tool
with no rate limiting on the login endpoint; it should not be on the open
internet.

### Updating

```bash
git pull
docker compose up -d --build
```

Schema migrations run automatically at startup and are idempotent.

---

## If you still want the frontend on Vercel

Workable, but it buys nothing here: the bundle is 230 kB, it is only used by your
internal team, and splitting it means the API must be publicly reachable and CORS
must be opened.

1. Host the API somewhere with a persistent process and network access to the
   database — the EC2 box, Railway, Render or Fly.io. Only Vercel is ruled out.
2. Point the frontend at it. `frontend/src/api.ts` uses relative paths (`/api/v1`),
   so add a rewrite in `vercel.json`:

   ```json
   {
     "rewrites": [
       { "source": "/api/:path*", "destination": "https://kb-api.example.com/api/:path*" },
       { "source": "/health", "destination": "https://kb-api.example.com/health" }
     ]
   }
   ```

3. Set `CORS_ORIGINS=https://your-app.vercel.app` on the API. Without it the
   browser blocks every request — CORS is off by default because the normal
   deployment is same-origin.

Vercel's build settings: root directory `frontend`, framework Vite, build
command `npm run build`, output `dist`.

---

## Alternative: systemd instead of Docker

If you would rather not run Docker on that host:

```ini
# /etc/systemd/system/chotu-rag.service
[Unit]
Description=Chotu RAG admin service
After=network.target postgresql.service

[Service]
Type=simple
User=chotu
WorkingDirectory=/opt/chotu_rag
EnvironmentFile=/opt/chotu_rag/.env
ExecStart=/opt/chotu_rag/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Build the frontend once with `cd frontend && npm run build` — the Python process
serves `frontend/dist` from there.

---

## Pre-deploy checklist

- [ ] `.env` is **not** committed (it is in `.gitignore`; confirm before the first push)
- [ ] Production `FAL_AI_API_KEY` is a fresh key, not the development one
- [ ] `ENVIRONMENT=production`
- [ ] `DATABASE_URL` points at `localhost` on the host, not the tunnel
- [ ] At least one admin user created
- [ ] Any account created while testing has had its password changed, or the
      account removed
- [ ] TLS terminating in front of port 8000
- [ ] Port 8000 not reachable from outside the host
- [ ] Proxy read timeout raised above 60s, or large uploads will be cut off
- [ ] `pg_dump` scheduled — `knowledge_chunks` holds vectors that cost API calls to regenerate
- [ ] `SECRET_KEY` backed up somewhere other than the database it protects — losing
      it makes every stored knowledge-base connection string unreadable. Only
      knowledge bases on another host store one; those in this service's own
      database are unaffected
- [ ] One `pg_dump` covers everything: all knowledge bases live in one schema,
      with a table pair each (`kb_<slug>_documents`, `kb_<slug>_chunks`)
- [ ] Any additional knowledge base's host is reachable **from this server**, not
      only from a laptop. If it is behind SSH, run the tunnel here (autossh under
      systemd) and point the connection string at the local end

## What is not handled yet

Known gaps, none of which block an internal deployment:

- **No rate limiting on `/api/v1/auth/login`** — brute force is only bounded by
  bcrypt's cost. Keep the service off the public internet.
- **Uploads are synchronous.** Anything past roughly 50 pages needs a background
  job rather than a longer timeout.
- **One worker.** Correct while the rate limiter is in-process; moving it to
  Postgres or Redis would allow more.
- **No re-embed job**, so changing the embedding model still means re-ingesting.
