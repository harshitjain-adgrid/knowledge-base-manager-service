"""
Upload named API cards, and only those.

`load_seeds.py` walks a whole folder: adding one card means deleting and
re-uploading all 43, which re-embeds everything and leaves a window where the
catalogue is half-written. That is a bad trade on a day when the knowledge base
has to work, so this does the same upload for a named subset and touches
nothing else.

Same client, same endpoints, same replace-by-title rule — so a card already in
the knowledge base is replaced rather than duplicated.

    python seeds/load_one.py offers/offers.deal.banner.md offers/offers.discount.banner.md
"""

import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))

from load_seeds import (  # noqa: E402  -- guarded by __main__, safe to import
    API_DIR,
    API_KB_SLUG,
    Client,
    existing_titles,
    title_of,
)


def main() -> int:
    names = sys.argv[1:]
    if not names:
        print(__doc__)
        return 2

    base = os.environ.get("CHOTU_BASE", "http://127.0.0.1:8100")
    token = os.environ.get("ADMIN_API_KEY")
    if not token:
        return int(bool(sys.stderr.write(
            "ADMIN_API_KEY is not set. Export it from chotu_rag/.env.\n")))

    client = Client(base, token)
    status, who = client.get("/api/v1/auth/me")
    if status != 200:
        print(f"Could not authenticate: {status} {who}")
        return 1
    print(f"signed in as {who.get('username')} at {base}")

    known = existing_titles(client, API_KB_SLUG)
    print(f"catalogue currently holds {len(known)} documents\n")

    failed = 0
    for name in names:
        path = API_DIR / name
        if not path.exists():
            print(f"  MISSING  {name}")
            failed += 1
            continue

        folder = "/" + str(path.parent.relative_to(API_DIR)).replace(
            os.sep, "/").strip("/")
        folder = "/" if folder == "/." else folder + "/"

        title = title_of(path)
        if title and title in known:
            client.delete(f"/api/v1/documents/{known[title]}", kb=API_KB_SLUG)
            print(f"  replacing existing '{title}'")

        status, body = client.upload(path, folder, API_KB_SLUG)
        if status == 201:
            print(f"  ok    {folder}{path.name}  ({body['chunk_count']} chunks)")
        else:
            failed += 1
            print(f"  FAIL  {folder}{path.name}\n        "
                  f"{str(body.get('detail'))[:400]}")

    status, stats = client.get("/api/v1/stats", kb=API_KB_SLUG)
    if status == 200:
        print(f"\n{API_KB_SLUG}: {stats['total_documents']} documents, "
              f"{stats['total_chunks']} chunks, "
              f"{stats['chunks_missing_embedding']} missing an embedding")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
