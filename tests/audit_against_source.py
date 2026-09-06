"""
Does every document say only what the product document says?

    python tests/audit_against_source.py --source <path to the .docx>

WHY

The corpus is a rewrite of a single product document into 44 merchant-facing
pages. A rewrite drifts, and drift here is invisible: a page that reads
perfectly and states a fact the product never agreed to is indistinguishable
from a good page until a merchant acts on it.

Four defects were found by hand in the five documents that happened to be open
while chasing an unrelated test failure -- two status tables using a state name
the source never uses, and two documents built on a paid-credits model that
appears nowhere in it. That hit rate is the reason this exists: nobody had
checked the other thirty-nine.

WHAT IS MECHANICAL, AND WHAT IS NOT

This pass is deterministic and free. It cannot judge meaning, so it does not
try. It finds the three things that ARE checkable without judgement, and each
one is where a real defect was actually found:

  figures      The source marks a long list of numbers [TBD]. Any number in our
               corpus that is not in the source is either invented or a rewrite
               of one -- and an invented figure about money is the worst thing
               this system can produce. Every one is printed for a human.

  vocabulary   A product noun the source never uses is a concept we invented.
               "package", "top-up", "bucket" and "campaign" appear zero times
               in the source and carried four documents between them.

  states       Named states in a table are the corpus's most load-bearing
               facts and its easiest drift: Success for Received, Success for
               Completed. Table keys are compared against the source's own.

Everything else -- whether a paragraph's CLAIM matches -- needs reading, and is
what the model pass in evals/ is for. This runs first and for nothing, so the
paid pass only has to look at what survives.
"""

import argparse
import io
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parents[1]
CORPUS = HERE / "content" / "product-knowledge-v2"

# Numbers that are structure rather than product facts: a list of three things,
# a section numbered 2. These carry no claim about how LessPay behaves.
_STRUCTURAL = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "12",
               "24", "100"}

# Words that look like product nouns but are ordinary English. Kept explicit so
# that a term added here is a visible decision rather than a silent exclusion.
_ORDINARY = {
    "app", "account", "shop", "shops", "money", "payment", "payments", "bank",
    "customer", "customers", "merchant", "merchants", "offer", "offers",
    "message", "messages", "screen", "date", "time", "day", "days", "reason",
    "status", "state", "states", "list", "page", "phone", "number", "name",
    "address", "photo", "photos", "review", "reviews", "order", "orders",
    "balance", "amount", "total", "link", "step", "steps", "support", "team",
    "product", "products", "price", "prices", "stock", "item", "items",
}

_WORD = re.compile(r"[A-Za-z][A-Za-z-]{2,}")
_NUMBER = re.compile(r"\b\d[\d,]*(?:\.\d+)?\s*(?:%|percent|rupees|rs\.?|inr|"
                     r"days?|hours?|minutes?|mins?|working days?|km|digits?)?",
                     re.I)


def read_docx(path: pathlib.Path) -> str:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(str(path))
    out = []
    for child in doc.element.body.iterchildren():
        if child.tag.endswith("}p"):
            out.append(Paragraph(child, doc).text)
        elif child.tag.endswith("}tbl"):
            for row in Table(child, doc).rows:
                out.append(" | ".join(c.text for c in row.cells))
    return "\n".join(out)


def documents() -> dict[str, tuple[pathlib.Path, str, str]]:
    """title -> (path, front matter, body)."""
    out = {}
    for path in sorted(CORPUS.rglob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        raw = io.open(path, encoding="utf-8").read()
        parts = raw.split("---", 2)
        if len(parts) < 3:
            continue
        title = next((l.split(":", 1)[1].strip().strip('"')
                      for l in parts[1].splitlines()
                      if l.lower().startswith("title:")), path.stem)
        out[title] = (path, parts[1], parts[2])
    return out


def numbers(text: str) -> set[str]:
    found = set()
    for m in _NUMBER.finditer(text):
        raw = " ".join(m.group(0).split()).lower().rstrip(".")
        digits = re.sub(r"[^\d]", "", raw)
        if digits and digits not in _STRUCTURAL:
            found.add(raw)
    return found


def table_keys(body: str) -> list[str]:
    """The first column of every markdown table row that is not a separator."""
    keys = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|") or set(line) <= set("|-: "):
            continue
        cell = line.strip("|").split("|")[0].strip().strip("*")
        if cell and cell.lower() not in ("status", "state", "term", "bucket",
                                         "stage", "tier", "category", "event",
                                         "trigger", "scenario", ""):
            keys.append(cell)
    return keys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    args = ap.parse_args()

    src = read_docx(pathlib.Path(args.source))
    src_low = src.lower()
    src_words = set(w.lower() for w in _WORD.findall(src))
    src_numbers = numbers(src)
    docs = documents()

    print(f"{len(docs)} documents against {pathlib.Path(args.source).name}")
    print(f"source: {len(src)} characters, {len(src_words)} distinct words, "
          f"{len(src_numbers)} figures\n")

    fig, vocab, states = [], [], []
    for title, (path, front, body) in sorted(docs.items()):
        rel = path.relative_to(CORPUS)

        for n in sorted(numbers(body)):
            digits = re.sub(r"[^\d]", "", n)
            if digits and digits not in "".join(src_numbers):
                fig.append((str(rel), title, n))

        for w in sorted({w.lower() for w in _WORD.findall(body)}):
            if w in src_words or w in _ORDINARY or len(w) < 4:
                continue
            # Only report a word used as a product term: capitalised mid
            # sentence, or bolded. Otherwise every ordinary verb lands here.
            if re.search(r"\*\*" + re.escape(w) + r"\*\*", body, re.I):
                vocab.append((str(rel), title, w))

        for k in table_keys(body):
            for part in re.split(r"\s*/\s*", k):
                part = part.strip()
                if part and len(part) > 2 and part.lower() not in src_low:
                    states.append((str(rel), title, k, part))

    def show(name, rows, note):
        print(f"── {name}  ({len(rows)})")
        print(f"   {note}")
        for row in rows:
            print("   " + "  ".join(str(x) for x in row[1:]))
        print()

    show("figures not in the source", fig,
         "a number the product document does not contain")
    show("bolded terms the source never uses", vocab,
         "a concept presented as a product term that the source has no word for")
    show("table states not in the source", states,
         "a named state the source does not use")

    total = len(fig) + len(vocab) + len(states)
    print(f"{total} thing(s) to look at by hand.")
    print("None of these is automatically wrong -- a rewrite may legitimately")
    print("say 'a few days' where the source says nothing. They are the places")
    print("where our text asserts something the source does not.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
