"""
Splitting documents into the units that get embedded and retrieved.

The guiding rule is that **a chunk must make sense on its own**, because that is
exactly how it reaches the assistant: alone, with no neighbours and no document
around it. A chunk reading "required when isLimited=true" or "same shape as the
deal validity above" is worse than useless — the model is pointed at text it
cannot see, and will either hedge or invent.

Two things follow from that rule:

* Structure decides the boundaries, not a character count. Sections are split at
  headings; tables and code blocks are never cut in half.
* Every chunk carries its own address — "Document > Section > Subsection" — so
  the reader always knows what it is looking at.
"""

import logging
import re
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class Chunk:
    """A single unit of retrievable text."""
    content: str
    chunk_index: int
    metadata: dict


# ── Markdown block parsing ──

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|?\s*$")
TABLE_DIVIDER_RE = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")
BULLET_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s+")

BLOCK_HEADING = "heading"
BLOCK_TEXT = "text"
BLOCK_TABLE = "table"
BLOCK_CODE = "code"


@dataclass
class Block:
    """A structural unit of the source document."""
    kind: str
    text: str
    level: int = 0          # heading depth, 0 for everything else
    title: str = ""         # heading text without the hashes
    table_header: str = ""  # header + divider rows, repeated if a table is split


def parse_blocks(content: str) -> list[Block]:
    """
    Break markdown into headings, paragraphs, tables and fenced code blocks.

    Tables and code blocks are kept whole here so the chunker can treat them as
    atomic. Anything that is not markdown simply produces text blocks, which is
    why plain .txt and PDF extractions still work through the same path.
    """
    # Normalise line endings so \r\n input cannot leave stray carriage returns
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    blocks: list[Block] = []
    buffer: list[str] = []

    def flush_text() -> None:
        text = "\n".join(buffer).strip()
        if text:
            blocks.append(Block(kind=BLOCK_TEXT, text=text))
        buffer.clear()

    i = 0
    while i < len(lines):
        line = lines[i]

        # Fenced code — copied verbatim until the closing fence, so markdown
        # inside a code sample is never mistaken for structure.
        fence = FENCE_RE.match(line)
        if fence:
            flush_text()
            marker = fence.group(1)
            code = [line]
            i += 1
            while i < len(lines):
                code.append(lines[i])
                if lines[i].strip().startswith(marker):
                    i += 1
                    break
                i += 1
            else:
                # Unclosed fence: treat what we have as a block rather than
                # swallowing the rest of the document into limbo.
                logger.debug("Unclosed code fence; treating the remainder as code.")
            blocks.append(Block(kind=BLOCK_CODE, text="\n".join(code)))
            continue

        heading = HEADING_RE.match(line)
        if heading:
            flush_text()
            blocks.append(
                Block(
                    kind=BLOCK_HEADING,
                    text=line.strip(),
                    level=len(heading.group(1)),
                    title=heading.group(2).strip(),
                )
            )
            i += 1
            continue

        # A table is a run of pipe rows. Requiring a divider row keeps a stray
        # sentence containing a pipe from being read as a one-row table.
        if TABLE_ROW_RE.match(line):
            look = i + 1
            if look < len(lines) and TABLE_DIVIDER_RE.match(lines[look]):
                flush_text()
                rows = [lines[i], lines[look]]
                header = "\n".join(rows)
                j = look + 1
                while j < len(lines) and TABLE_ROW_RE.match(lines[j]):
                    rows.append(lines[j])
                    j += 1
                blocks.append(
                    Block(kind=BLOCK_TABLE, text="\n".join(rows), table_header=header)
                )
                i = j
                continue

        if not line.strip():
            flush_text()
            i += 1
            continue

        buffer.append(line)
        i += 1

    flush_text()
    return blocks


# ── Splitting oversized blocks ──

def _split_plain_text(text: str, max_size: int, overlap: int) -> list[str]:
    """Last resort for a single block larger than a chunk."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_size,
        chunk_overlap=overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", "; ", ", ", " ", ""],
    )
    return [piece for piece in splitter.split_text(text) if piece.strip()]


def _split_table(block: Block, max_size: int) -> list[str]:
    """
    Split a table that does not fit, repeating the header in every piece.

    Without the header a fragment is just a grid of values with no column names —
    unreadable to a person and unmatchable by a query.
    """
    lines = block.text.split("\n")
    header_lines = block.table_header.split("\n")
    body = lines[len(header_lines):]
    header_size = len(block.table_header) + 1

    pieces, current = [], []
    size = header_size
    for row in body:
        if current and size + len(row) + 1 > max_size:
            pieces.append(block.table_header + "\n" + "\n".join(current))
            current, size = [], header_size
        current.append(row)
        size += len(row) + 1

    if current:
        pieces.append(block.table_header + "\n" + "\n".join(current))
    return pieces or [block.text]


def _split_code(block: Block, max_size: int, overlap: int) -> list[str]:
    """
    Split an oversized code block on line boundaries, never mid-line, and
    re-fence every piece.

    Without re-fencing, the middle pieces of a split block carry no fence at all
    and stop being recognisable as code to a reader or a renderer.
    """
    lines = block.text.split("\n")

    has_fence = bool(FENCE_RE.match(lines[0])) if lines else False
    opening = lines[0] if has_fence else "```"
    closing = opening.strip()[:3]
    inner = lines[1:] if has_fence else lines
    if inner and FENCE_RE.match(inner[-1]):
        inner = inner[:-1]

    wrapper = len(opening) + len(closing) + 2
    pieces, current, size = [], [], wrapper
    for line in inner:
        if current and size + len(line) + 1 > max_size:
            pieces.append("\n".join([opening, *current, closing]))
            current, size = [], wrapper
        current.append(line)
        size += len(line) + 1
    if current:
        pieces.append("\n".join([opening, *current, closing]))
    return pieces or [block.text]


def _split_block(block: Block, max_size: int, overlap: int) -> list[str]:
    if block.kind == BLOCK_TABLE:
        return _split_table(block, max_size)
    if block.kind == BLOCK_CODE:
        return _split_code(block, max_size, overlap)
    return _split_plain_text(block.text, max_size, overlap)


# ── The chunker ──

def _normalise_title(value: str) -> str:
    """
    Loose comparison key for "is this heading just the title again?".

    \w is Unicode-aware, so Devanagari and other scripts are kept — stripping to
    ASCII would make "Khata — खाता" look identical to "Khata" and silently drop
    the Hindi half of a heading.
    """
    return re.sub(r"\W+", " ", value.lower(), flags=re.UNICODE).strip()


def _breadcrumb(doc_title: str | None, heading_stack: list[Block]) -> str:
    """
    Build "Document > Section > Subsection".

    A document's H1 almost always repeats its title — the recommended authoring
    style — so the leading heading is dropped when it does. "Offers > Offers >
    Validity" wastes context and reads like a bug.
    """
    parts = [doc_title] if doc_title else []
    headings = [h.title for h in heading_stack if h.title]

    if doc_title and headings and _normalise_title(headings[0]) == _normalise_title(doc_title):
        headings = headings[1:]

    return " > ".join([*parts, *headings])


def chunk_text_document(
    content: str,
    doc_metadata: dict | None = None,
    doc_title: str | None = None,
    max_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """
    Split prose into self-contained chunks.

    Boundaries follow the document's own structure: a new heading always starts a
    new chunk, and tables and code blocks stay intact. Every chunk is prefixed
    with its breadcrumb, so it is readable in isolation — the prefix is stored,
    not just embedded, because retrieval hands this exact text to the assistant.
    """
    # Sizes come from the knowledge base being written to; the environment's
    # values are the fallback for the default one.
    max_size = max_size if max_size is not None else settings.chunk_size
    overlap = overlap if overlap is not None else settings.chunk_overlap
    blocks = parse_blocks(content)

    if not blocks:
        return []

    chunks: list[Chunk] = []
    heading_stack: list[Block] = []
    buffer: list[str] = []
    buffer_size = 0
    # The heading stack as it was when the current buffer started, so a chunk is
    # labelled with the section it belongs to rather than one we have moved on to
    buffer_stack: list[Block] = []

    def emit(body: str, stack: list[Block], part: int | None = None) -> None:
        # Strip blank lines, not indentation — leading spaces are meaningful in
        # code and YAML, and stripping them corrupts a split code block.
        body = body.strip("\n").rstrip()
        if not body.strip():
            return
        crumb = _breadcrumb(doc_title, stack)
        content_out = f"{crumb}\n\n{body}" if crumb else body
        meta = {
            **(doc_metadata or {}),
            "chunk_type": "text",
            "heading_path": [h.title for h in stack if h.title],
        }
        if stack:
            meta["section"] = stack[-1].title
        if part is not None:
            meta["section_part"] = part
        chunks.append(
            Chunk(content=content_out, chunk_index=len(chunks), metadata=meta)
        )

    def flush() -> None:
        nonlocal buffer, buffer_size, buffer_stack
        if buffer:
            emit("\n\n".join(buffer), buffer_stack)
        buffer, buffer_size = [], 0
        buffer_stack = list(heading_stack)

    for block in blocks:
        if block.kind == BLOCK_HEADING:
            # A heading is a hard boundary: whatever came before belongs to the
            # previous section and must not bleed into this one.
            flush()
            heading_stack = [h for h in heading_stack if h.level < block.level]
            heading_stack.append(block)
            buffer_stack = list(heading_stack)
            continue

        block_len = len(block.text)

        if block_len > max_size:
            # Too big to sit in a chunk with anything else
            flush()
            pieces = _split_block(block, max_size, overlap)
            for index, piece in enumerate(pieces):
                emit(piece, heading_stack, part=index if len(pieces) > 1 else None)
            buffer_stack = list(heading_stack)
            continue

        if buffer and buffer_size + block_len + 2 > max_size:
            flush()

        buffer.append(block.text)
        buffer_size += block_len + 2

    flush()

    logger.info(
        f"Split into {len(chunks)} chunks "
        f"({sum(len(c.content) for c in chunks)} chars, max_size={max_size})."
    )
    return chunks


def chunk_document(
    content: str,
    doc_type: str,
    doc_metadata: dict | None = None,
    doc_title: str | None = None,
    max_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """Route to the chunking strategy for this document type."""
    # 'api' is what authors write in front matter; 'tool_card' names the same
    # strategy from the retrieval side. Both accepted, so neither reading is wrong.
    if doc_type in ("api", "tool_card"):
        return chunk_tool_card(content, doc_metadata, doc_title, max_size)
    return chunk_text_document(content, doc_metadata, doc_title, max_size, overlap)


# ────────────────────────────────────────────────────────────────────────────
# Tool cards — one API per document
# ────────────────────────────────────────────────────────────────────────────
#
# A tool card is retrieved to answer one question: "is this the API the
# merchant just asked for?" That makes it a classification target rather than a
# passage of prose, and it needs two things ordinary chunking cannot give.
#
# It must never be split. Half a card is worse than no card — retrieval returns
# a description with no api_id, or an api_id with no description, and either
# way a candidate slot is spent on something unusable.
#
# And its example utterances are indexed one per chunk. A merchant types
# "start a 20% off sale"; matching that against another short phrase a person
# wrote is a far stronger signal than matching it against a paragraph of
# description. This is the largest single lever on selection accuracy, and it
# costs one row per utterance.

TOOL_CARD_REQUIRED = ("api_id", "domain", "method", "path")
HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
API_ID_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)+$")
MIN_UTTERANCES = 3


def validate_tool_card(meta: dict) -> list[str]:
    """
    Everything wrong with a tool card's front matter, in one pass.

    Returns a list of problems rather than raising on the first, because an
    author fixing a card wants to see all of them at once instead of
    resubmitting five times. An empty list means the card is usable.
    """
    problems: list[str] = []
    meta = meta or {}

    for key in TOOL_CARD_REQUIRED:
        if not str(meta.get(key) or "").strip():
            problems.append(f"'{key}' is missing from the front matter.")

    api_id = str(meta.get("api_id") or "").strip()
    if api_id and not API_ID_RE.match(api_id):
        problems.append(
            f"api_id '{api_id}' should be lowercase and name both the area and "
            f"the action, separated by a dot — for example 'offers.create'."
        )

    method = str(meta.get("method") or "").strip().upper()
    if method and method not in HTTP_METHODS:
        problems.append(
            f"method '{method}' is not one of {', '.join(sorted(HTTP_METHODS))}."
        )

    path = str(meta.get("path") or "").strip()
    if path and not path.startswith("/"):
        problems.append(f"path '{path}' should start with '/'.")

    utterances = meta.get("utterances")
    if not isinstance(utterances, list) or len(utterances) < MIN_UTTERANCES:
        problems.append(
            f"'utterances' needs at least {MIN_UTTERANCES} example phrases in the "
            f"merchant's own words. They are what retrieval actually matches on."
        )
    elif any(not str(u).strip() for u in utterances):
        problems.append("One of the entries under 'utterances' is empty.")

    fields = meta.get("fields")
    if fields is not None and not isinstance(fields, list):
        problems.append("'fields' should be a list, one entry per request field.")
    elif isinstance(fields, list):
        for index, field in enumerate(fields):
            if not isinstance(field, dict):
                problems.append(
                    f"fields[{index}] should be a mapping, not a bare value."
                )
                continue
            if not str(field.get("name") or "").strip():
                problems.append(f"fields[{index}] has no 'name'.")
            if field.get("required") and not str(field.get("prompt") or "").strip():
                problems.append(
                    f"fields[{index}] ('{field.get('name')}') is required but has "
                    f"no 'prompt'. Without one there is nothing to ask the merchant."
                )

    return problems


def _describe_fields(fields, *, required: bool) -> str:
    """
    Render a card's fields as a phrase a person would say.

    `discount_type` with values [percentage, flat] becomes "discount type
    (percentage or flat)". The underscores and the enum values are what make it
    matchable — a merchant writes "flat 100 off", never "discount_type".
    """
    if not isinstance(fields, list):
        return ""

    parts: list[str] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        if bool(field.get("required")) is not required:
            continue
        name = str(field.get("name") or "").strip().replace("_", " ")
        if not name:
            continue
        values = field.get("values")
        if isinstance(values, list) and values:
            readable = " or ".join(str(v).replace("_", " ") for v in values)
            parts.append(f"{name} ({readable})")
        else:
            parts.append(name)

    return ", ".join(parts)


def chunk_tool_card(
    content: str,
    doc_metadata: dict | None = None,
    doc_title: str | None = None,
    max_size: int | None = None,
) -> list[Chunk]:
    """
    Turn one API's card into a card chunk plus one chunk per example utterance.

    Raises ValueError when the front matter is unusable or the description is
    too long to keep whole. Both are author mistakes, and both must surface at
    upload — while someone is looking at the file — rather than as a wrong API
    call weeks later.
    """
    meta = dict(doc_metadata or {})
    max_size = max_size if max_size is not None else settings.chunk_size

    problems = validate_tool_card(meta)
    if problems:
        raise ValueError(
            "This API card cannot be stored:\n  - " + "\n  - ".join(problems)
        )

    api_id = str(meta["api_id"]).strip()
    domain = str(meta["domain"]).strip()
    method = str(meta["method"]).strip().upper()
    path = str(meta["path"]).strip()

    body = content.strip()
    if not body:
        raise ValueError(
            f"'{api_id}' has no description. The body is what a merchant's "
            f"question is matched against when their phrasing is not already in "
            f"the utterance list."
        )

    shared = {
        **meta,
        "api_id": api_id,
        "domain": domain,
        "method": method,
        "path": path,
    }

    # The card itself: prefixed with the call it describes and suffixed with what
    # it needs, so the chunk identifies both its API and its inputs when read on
    # its own — which is how it reaches the assistant, and how a person reads it
    # in the search simulator.
    #
    # The needs line is words rather than field names, because it is embedded:
    # "discount type (percentage or flat)" can match a merchant who says "flat
    # 100 off", where `discount_type` cannot.
    header = f"{doc_title or api_id} ({method} {path})"
    card = f"{header}\n\n{body}"

    needs = _describe_fields(meta.get("fields"), required=True)
    optional = _describe_fields(meta.get("fields"), required=False)
    if needs:
        card += f"\n\nNeeds: {needs}."
    if optional:
        card += f"\nOptionally: {optional}."

    if len(card) > max_size:
        raise ValueError(
            f"'{api_id}' is {len(card)} characters, over this knowledge base's "
            f"limit of {max_size}. An API card has to fit in a single chunk — "
            f"shorten the description, or raise the knowledge base's chunk size. "
            f"Splitting it would return half a tool."
        )

    chunks = [
        Chunk(
            content=card,
            chunk_index=0,
            metadata={**shared, "chunk_kind": "card"},
        )
    ]

    # One chunk per utterance, stored the way a merchant would say it.
    # Deduplicated case-insensitively: a repeated phrase would occupy two
    # candidate slots while carrying the same evidence.
    seen: set[str] = set()
    for utterance in meta.get("utterances", []):
        text = str(utterance).strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        chunks.append(
            Chunk(
                content=text,
                chunk_index=len(chunks),
                metadata={
                    **shared,
                    "chunk_kind": "utterance",
                    "utterance_index": len(chunks) - 1,
                },
            )
        )

    logger.info(
        f"Tool card '{api_id}' indexed as 1 card + {len(chunks) - 1} utterances."
    )
    return chunks
