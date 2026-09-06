"""
Does today's chunker still produce what is stored in kb_product_knowledge_v3?

    python tests/verify_chunker_matches_v3.py

The question this answers is a specific worry, not a general one. The upload
path was written before chunk roles, per-utterance indexing and the authoring
contract existed. v3 was ingested at some point along the way. If the chunker
has moved since, then re-uploading ONE edited document would silently give it
different boundaries, different roles, or different text from the other
forty-three -- and every measurement taken against v3 would quietly stop being
comparable.

Reading the code cannot settle that. Running it can.

For every document in the corpus this re-chunks the file exactly as an upload
would and compares the result, chunk by chunk, against the rows actually in
v3: how many chunks, their order, their text, their recorded role, and the
section each one names.

No embeddings, no service, no writes -- pure functions against stored rows. It
costs nothing and can be re-run any time the chunker is touched.

A difference here is not automatically a bug. It means the chunker and the
stored corpus disagree, and the two possible causes -- the chunker changed, or
v3 was built by something else -- need different responses. So it prints what
differs rather than deciding.
"""

import io
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import asyncio  # noqa: E402

import asyncpg  # noqa: E402
import yaml  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.services.chunking_service import chunk_document  # noqa: E402

CORPUS = pathlib.Path(__file__).resolve().parents[1] / "content" / "product-knowledge-v2"
PREFIX = "kb_product_knowledge_v3"


def dsn() -> str:
    return get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")


def as_dict(meta) -> dict:
    if isinstance(meta, dict):
        return dict(meta)
    if isinstance(meta, str) and meta:
        try:
            return json.loads(meta)
        except json.JSONDecodeError:
            return {}
    return {}


async def main() -> int:
    con = await asyncpg.connect(dsn())
    try:
        stored: dict[str, list] = {}
        rows = await con.fetch(
            f"SELECT d.title, ch.chunk_index, ch.content, ch.metadata "
            f"FROM {PREFIX}_chunks ch "
            f"JOIN {PREFIX}_documents d ON d.id = ch.document_id "
            f"ORDER BY d.title, ch.chunk_index")
        for r in rows:
            stored.setdefault(r["title"], []).append(r)
    finally:
        await con.close()

    files = sorted(CORPUS.rglob("*.md"))
    print(f"{len(files)} files on disk, {len(stored)} documents in {PREFIX}\n")

    same = differing = missing = 0
    problems: list[str] = []

    for path in files:
        raw = io.open(path, encoding="utf-8").read()
        parts = raw.split("---", 2)
        meta = yaml.safe_load(parts[1]) or {}
        body = parts[2]
        title = meta.get("title", path.stem)

        if title not in stored:
            missing += 1
            problems.append(f"{title!r}: on disk but not in {PREFIX}")
            continue

        fresh = chunk_document(body, meta.get("type", "concept"), meta, title)
        old = stored[title]

        if len(fresh) != len(old):
            differing += 1
            problems.append(
                f"{title!r}: chunker makes {len(fresh)}, v3 holds {len(old)}")
            continue

        diffs = []
        for i, (f, o) in enumerate(zip(fresh, old)):
            o_meta = as_dict(o["metadata"])
            f_meta = f.metadata or {}
            if f.content.strip() != (o["content"] or "").strip():
                diffs.append(f"chunk {i}: text differs")
            if f_meta.get("chunk_role") != o_meta.get("chunk_role"):
                diffs.append(
                    f"chunk {i}: role {f_meta.get('chunk_role')!r} vs "
                    f"{o_meta.get('chunk_role')!r}")
            if f_meta.get("section") != o_meta.get("section"):
                diffs.append(
                    f"chunk {i}: section {f_meta.get('section')!r} vs "
                    f"{o_meta.get('section')!r}")
        if diffs:
            differing += 1
            problems.append(f"{title!r}: " + "; ".join(diffs[:3]))
        else:
            same += 1

    print(f"  identical : {same}")
    print(f"  differing : {differing}")
    print(f"  missing   : {missing}")
    if problems:
        print("\nwhat differs:")
        for p in problems[:20]:
            print("   -", p)
    print()
    if differing == 0 and missing == 0:
        print("The chunker reproduces v3 exactly. Re-uploading one document gives")
        print("it the same treatment as the other forty-three, so measurements")
        print("taken against v3 stay comparable.")
        return 0
    print("The chunker and v3 disagree. Re-uploading a document would give it")
    print("different chunks from its neighbours -- resolve this before editing")
    print("the corpus.")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
