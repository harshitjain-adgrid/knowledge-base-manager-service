# Seed content

Two knowledge bases' worth of content, plus the evaluation sets that measure how
well retrieval works against them.

> **All of this is synthetic.** Every document carries `status: example` in its
> front matter, and every API card additionally says
> `status: example  # synthetic seed data — replace with the real contract`.
>
> The API paths, request fields and error codes are **invented**. They are
> plausible, not real. Nothing here should reach a merchant, and no orchestrator
> should call the paths in these cards. They exist so that retrieval and action
> selection can be measured before the real content arrives, and so the format
> the backend team fills in is unambiguous.

---

## What is here

```
seeds/
  product/                     19 documents → the "default" knowledge base
    getting-started/  catalog/  offers/  khata/
    orders/  payments/  store/  reports/

  api-catalog/                 33 API cards → the "api-catalog" knowledge base
    catalog/  offers/  khata/  orders/
    payments/  customers/  store/  reports/

  api-catalog-domains.md       what each domain covers
  build_product_kb.py          regenerates product/
  build_api_catalog.py         regenerates api-catalog/
  load_seeds.py                uploads both into a running service

  eval/
    product_queries.yaml       41 questions → the document that should answer them
    action_queries.yaml        63 messages  → the API that should be selected
    run_eval.py                scores both, and sweeps thresholds
```

The two `build_*.py` scripts hold the content as data and emit the markdown.
Edit the script, re-run it, re-load. The markdown files are what you read and
what the loader uploads.

---

## Loading it

The API catalogue knowledge base is created on first run. It needs a connection
string; a schema on the same Postgres is enough and needs no new database.

```bash
python seeds/load_seeds.py \
  --base http://127.0.0.1:8000 \
  --dsn 'postgresql://user:password@127.0.0.1:5434/vector_qa?schema=api_catalog'
```

After the first run the `--dsn` is not needed again:

```bash
python seeds/load_seeds.py --base http://127.0.0.1:8000
python seeds/load_seeds.py --base http://127.0.0.1:8000 --only api
```

Loading is idempotent by title — running it twice replaces rather than
duplicates. Expect around four minutes for the catalogue: 242 chunks, paced
against the embedding provider's rate limit.

---

## Measuring it

```bash
python seeds/eval/run_eval.py --base http://127.0.0.1:8000
python seeds/eval/run_eval.py --base http://127.0.0.1:8000 --only action
python seeds/eval/run_eval.py --base http://127.0.0.1:8000 --sweep
```

Results break down by tier, because an overall percentage hides the failures
that actually matter.

| Tier | What it contains | Why it is separate |
|---|---|---|
| `easy` | Plainly worded, one obvious answer | If this is not near perfect, something is broken |
| `medium` | Indirect phrasing, Hindi and Hinglish | Where real merchant messages live |
| `confusable` | Deliberately close to a sibling; the sibling is named | Where wrong actions come from |
| `negative` | Not an instruction at all | **The one that matters most.** A confident wrong action is far worse than an admitted miss |

Every evaluation query is a **paraphrase**. None is copied from a card's
`utterances` list — a test that feeds a string back to the index containing it
measures nothing but that cosine similarity works.

### The sweep

`--sweep` resolves each query once at permissive thresholds, then re-applies the
act/ask/decline rules offline across combinations of `min_score` and
`decision_margin`. One embedding call per query rather than one per query per
combination.

It ranks settings by overall accuracy **but only among those that refuse every
non-instruction**. A setting that acts on "what does khata mean" is not a
candidate however well it scores elsewhere.

---

## Replacing it with real content

**Product knowledge.** Follow [CONTENT_GUIDE.md](../docs/CONTENT_GUIDE.md).
Delete the seed documents as real ones land, or keep both while comparing — they
are all marked `status: example`, so they are easy to find and remove.

**API catalogue.** Follow [API_CATALOG_GUIDE.md](../docs/API_CATALOG_GUIDE.md).
If the backend team has an OpenAPI spec or a Postman collection, generate the
front matter from it and have people write only the body and the utterances —
that is the half that decides whether retrieval works.

**The evaluation sets are worth keeping either way.** Replace the queries with
real merchant messages as you collect them, and keep the tier structure. A
labelled set of a few hundred real messages is the only way to know whether a
change to the content, the chunking or the thresholds made things better or
worse.
