"""
Loads the seed content into the two knowledge bases.

  python seeds/load_seeds.py --base http://127.0.0.1:8000 --user admin

Creates the API catalogue knowledge base if it is missing, then uploads every
markdown file: product documents into the default knowledge base, API cards into
the catalogue. Front matter carries the title, type and metadata, so nothing is
passed on the command line except the folder.

Idempotent by title within a folder — running it twice replaces rather than
duplicates.
"""

import argparse
import getpass
import io
import json
import mimetypes
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
import uuid

HERE = pathlib.Path(__file__).parent
PRODUCT_DIR = HERE / "product"
PRODUCT_KB_SLUG = "product-knowledge"
API_DIR = HERE / "api-catalog"

API_KB_SLUG = "api-catalog"
API_KB_NAME = "API Catalog"

# Big enough that a card is never split, and no overlap — there is nothing for
# a single-chunk document to overlap with.
API_KB_CHUNK_SIZE = 4000
API_KB_CHUNK_OVERLAP = 0


class Client:
    def __init__(self, base: str, token: str):
        self.base = base.rstrip("/")
        self.token = token

    def _request(self, method, path, body=None, kb=None, form=None):
        headers = {"Authorization": f"Bearer {self.token}"}
        if kb:
            headers["X-Knowledge-Base"] = kb
        data = None
        if form is not None:
            boundary = uuid.uuid4().hex
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
            data = _encode_multipart(form, boundary)
        elif body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()

        request = urllib.request.Request(
            f"{self.base}{path}", data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return response.status, json.loads(response.read().decode())
        except urllib.error.HTTPError as error:
            raw = error.read().decode()
            try:
                return error.code, json.loads(raw)
            except Exception:
                return error.code, {"detail": raw[:400]}

    get = lambda self, path, kb=None: self._request("GET", path, kb=kb)          # noqa: E731
    post = lambda self, path, body=None, kb=None: self._request("POST", path, body, kb)   # noqa: E731
    delete = lambda self, path, kb=None: self._request("DELETE", path, kb=kb)    # noqa: E731

    def upload(self, path: pathlib.Path, folder: str, kb: str):
        return self._request(
            "POST", "/api/v1/documents/upload", kb=kb,
            form=[
                ("folder_path", folder),
                ("file", path.name, path.read_bytes()),
            ],
        )


def _encode_multipart(parts, boundary: str) -> bytes:
    buffer = io.BytesIO()
    for part in parts:
        buffer.write(f"--{boundary}\r\n".encode())
        if len(part) == 2:
            name, value = part
            buffer.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            buffer.write(str(value).encode())
        else:
            name, filename, content = part
            mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            buffer.write(
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                f"Content-Type: {mime}\r\n\r\n".encode()
            )
            buffer.write(content)
        buffer.write(b"\r\n")
    buffer.write(f"--{boundary}--\r\n".encode())
    return buffer.getvalue()


def sign_in(base: str, username: str, password: str) -> str:
    request = urllib.request.Request(
        f"{base.rstrip('/')}/api/v1/auth/login",
        data=json.dumps({"username": username, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode())["token"]
    except urllib.error.HTTPError as error:
        sys.exit(f"Sign-in failed: {error.code} {error.read().decode()[:200]}")


def ensure_api_kb(client: Client, dsn: str) -> None:
    status, body = client.get(f"/api/v1/knowledge-bases/{API_KB_SLUG}")
    if status == 200:
        print(f"  knowledge base '{API_KB_SLUG}' already exists "
              f"({body['embedding_model']}, {body['embedding_dimensions']}d)")
        return

    if not dsn:
        sys.exit(
            "The API catalogue knowledge base does not exist yet and no --dsn was\n"
            "given. Pass the connection string for it, for example:\n"
            "  --dsn 'postgresql://user:pass@host:5432/vector_qa'\n"
            "The same database this service already uses is fine — a knowledge\n"
            "base gets its own tables, not its own schema."
        )

    print(f"  creating knowledge base '{API_KB_SLUG}'...")
    status, body = client.post("/api/v1/knowledge-bases", {
        "name": API_KB_NAME,
        "slug": API_KB_SLUG,
        "description": "One card per API. Retrieval here selects an action; "
                       "the product knowledge base answers questions.",
        "dsn": dsn,
        "embedding_provider": "gemini",
        "embedding_model": "gemini-embedding-2",
        "embedding_dimensions": 3072,
        "chunk_size": API_KB_CHUNK_SIZE,
        "chunk_overlap": API_KB_CHUNK_OVERLAP,
    })
    if status != 201:
        sys.exit(f"Could not create it: {status} {body.get('detail')}")
    print(f"  created — {body['dsn_preview']}")


def existing_titles(client: Client, kb: str) -> dict:
    """Every document already in a knowledge base, by title."""
    found = {}
    skip = 0
    while True:
        status, body = client.get(f"/api/v1/documents?skip={skip}&limit=100", kb=kb)
        if status != 200:
            return found
        for document in body["documents"]:
            found[document["title"]] = document["id"]
        skip += 100
        if skip >= body["total"]:
            return found


def load_folder(client: Client, root: pathlib.Path, kb: str, label: str) -> None:
    files = sorted(root.rglob("*.md"))
    if not files:
        print(f"  nothing to load from {root}")
        return

    print(f"\n{label}: {len(files)} files -> knowledge base '{kb}'")
    known = existing_titles(client, kb)

    loaded = replaced = failed = 0
    started = time.time()

    for path in files:
        folder = "/" + str(path.parent.relative_to(root)).replace(os.sep, "/").strip("/")
        folder = "/" if folder == "/." else folder + "/"

        # Read the title out of the front matter so a re-run replaces rather
        # than duplicating. Cheap, and avoids needing an id on disk.
        text = path.read_text(encoding="utf-8")
        title = None
        for line in text.splitlines()[1:20]:
            if line.lower().startswith("title:"):
                title = line.split(":", 1)[1].strip().strip('"')
                break

        if title and title in known:
            client.delete(f"/api/v1/documents/{known[title]}", kb=kb)
            replaced += 1

        status, body = client.upload(path, folder, kb)
        if status == 201:
            loaded += 1
            print(f"  ok    {folder}{path.name}  ({body['chunk_count']} chunks)")
        else:
            failed += 1
            detail = str(body.get("detail"))
            print(f"  FAIL  {folder}{path.name}\n        {detail[:300]}")

    print(f"  {loaded} loaded ({replaced} replaced), {failed} failed, "
          f"{time.time() - started:.0f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", default=os.environ.get("CHOTU_PASSWORD"))
    parser.add_argument("--dsn", default=os.environ.get("CHOTU_API_KB_DSN"),
                        help="Connection string for the API catalogue knowledge "
                             "base. Only needed the first time. The same database "
                             "as the service's own is fine.")
    parser.add_argument("--only", choices=["product", "api"],
                        help="Load just one side.")
    args = parser.parse_args()

    password = args.password or getpass.getpass(f"Password for {args.user}: ")
    client = Client(args.base, sign_in(args.base, args.user, password))

    status, health = client.get("/api/v1/auth/me")
    print(f"signed in as {health.get('username')} at {args.base}")

    if args.only != "product":
        ensure_api_kb(client, args.dsn)

    if args.only != "api":
        load_folder(client, PRODUCT_DIR, PRODUCT_KB_SLUG, "Product knowledge")
    if args.only != "product":
        load_folder(client, API_DIR, API_KB_SLUG, "API catalogue")

    print("\nTotals")
    for kb in ([PRODUCT_KB_SLUG] if args.only != "api" else []) + \
              ([API_KB_SLUG] if args.only != "product" else []):
        status, stats = client.get("/api/v1/stats", kb=kb)
        if status == 200:
            print(f"  {kb:<12} {stats['total_documents']:>3} documents, "
                  f"{stats['total_chunks']:>4} chunks, "
                  f"{stats['chunks_missing_embedding']} missing an embedding")


if __name__ == "__main__":
    main()
