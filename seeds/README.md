# Seed content

Two knowledge bases' worth of content, plus the evaluation sets that measure how
well retrieval works against them.

> **Most of this is synthetic — check `status` before calling anything.**
>
> `status: example` — the product documents and the eight merchant domains
> (catalog, offers, khata, orders, payments, customers, store, reports). The
> paths, fields and error codes are **invented**: plausible, not real. Nothing
> here should reach a merchant, and nothing should call these paths. They exist
> so retrieval can be measured before the real content arrives, and so the
> format the backend team fills in is unambiguous.
>
> `status: live` — the `weather` and `reference` domains. These are real,
> key-free public APIs (Open-Meteo, sunrise-sunset.org, Frankfurter, CoinGecko,
> dictionaryapi.dev, Nager.Date), verified responding on 19 August 2026. They
> are here so an orchestrator can be tested end to end against something that
> actually answers. They need a `User-Agent` header — several return 403
> without one.
>
> The offers domain is modelled on the **real** AdGrid contract even though it
> is marked `example`: two actions, `DEAL_CREATE` and `DISCOUNT_CREATE`, behind
> one MPIN-gated endpoint. The shape is right; the surrounding cards are not.

---

## What is here

```
seeds/
  product/                     19 documents → the "default" knowledge base
    getting-started/  catalog/  offers/  khata/
    orders/  payments/  store/  reports/

  api-catalog/                 41 API cards → the "api-catalog" knowledge base
    catalog/  offers/  khata/  orders/  payments/
    customers/  store/  reports/       synthetic — cannot be called
    weather/  reference/               real public APIs — can be called

  api-catalog-domains.md       what each domain covers
  build_product_kb.py          regenerates product/
  build_api_catalog.py         regenerates api-catalog/
  load_seeds.py                uploads both into a running service

  eval/
    product_queries.yaml       41 questions → the document that should answer them
    action_queries.yaml        81 messages  → the API that should be retrieved
    selection.py               collapses chunk hits into one API per candidate
    run_eval.py                scores both, and sweeps thresholds
    BASELINE.md                the numbers to measure regressions against
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
  --dsn 'postgresql://user:password@127.0.0.1:5434/vector_qa'
```

After the first run the `--dsn` is not needed again:

```bash
python seeds/load_seeds.py --base http://127.0.0.1:8000
python seeds/load_seeds.py --base http://127.0.0.1:8000 --only api
```

Loading is idempotent by title — running it twice replaces rather than
duplicates. Expect around four minutes for the catalogue: 293 chunks, paced
against the embedding provider's rate limit.

The free embedding tier allows 1,000 requests a day and each text counts as one,
so a full catalogue reload is 293 of them. Reading is cheap; ingestion is what
exhausts the quota.

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

### Where the selection logic lives

`selection.py` holds the part that turns chunk hits into one candidate per API —
collapsing several chunks of the same card, ranking domains, and deciding
between act, ask and decline.

It sits in the evaluation tooling rather than in the service on purpose. **The
knowledge base stores and retrieves; deciding what to do with a retrieval, and
calling anything, belongs to the orchestrator** — a separate system that reads
the same pgvector database. What is needed here is measurement, and measuring
whether the catalogue retrieves correctly needs the same collapsing the
orchestrator will do.

It is also the clearest available description of that shape, for whoever builds
the orchestrator.

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
