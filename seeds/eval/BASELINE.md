# Baseline results

Measured 20 August 2026 against the 41-card catalogue and the 28 real product
documents in `content/product-knowledge/`. `gemini-embedding-2` at 3072
dimensions, `min_score=0.65`, `decision_margin=0.02`.

Re-measured 21 August 2026 after moving from Google's API to fal.ai, **same
model, same numbers — 67/68 and 68/81, tier for tier, failure for failure.**

### Why the provider change needed no re-embedding

fal reaches `gemini-embedding-2` through OpenRouter's OpenAI-compatible
endpoint. Embedding identical text through both paths and comparing gave
**cosine 1.000000** — on the query form, on the document form, and on a second
query. Same model, same vectors, so all 488 stored vectors stayed valid.

That was worth measuring rather than assuming, in both directions. Re-embedding
488 chunks because the vendor changed would have been wasted work; *not*
re-embedding when the vectors had shifted would have been silent corruption —
search would return plausible nonsense rather than fail. A wrong model measures
about 0.006 cosine against the right one, which is the failure this check rules
out.

Two things did change, neither affecting the numbers:

- **The request now carries `dimensions`.** The Google path never sent it. It is
  honoured (3072 and 1536 both verified), and the identical scores confirm it
  does not perturb the 3072 case.
- **`openai/text-embedding-3-large` and `-small` are no longer offered.** Both
  return 401 — reaching OpenAI through OpenRouter needs an OpenAI account this
  one does not have. They were in the model dropdown and would have failed at
  first ingest.

Re-run after any change to the content, the chunking, or the thresholds. A drop
against these numbers is a regression.

Measured through `/search`. The knowledge base retrieves; the collapsing and
ranking that turn chunk hits into one API live in `selection.py` beside the
evaluation, because that decision belongs to the orchestrator rather than to
this service.

```
PRODUCT KNOWLEDGE  (recall@5)      28 documents, 195 chunks
  easy          28/28  100.0%
  medium        17/17  100.0%
  confusable    13/14   92.9%
  negative       9/9   100.0%
  overall       67/68   98.5%

ACTION SELECTION                   41 cards, 293 chunks
  easy          25/27   92.6%
  medium        18/20   90.0%
  confusable    22/25   88.0%
  negative       3/9    33.3%
  overall       68/81   84.0%

retrieval latency: 2700ms mean, 6280ms worst   (over an SSH tunnel)
```

**On real instructions — every tier except `negative` — 65 of 72, 90.3%.**

### The one product failure

```
[confusable] 'difference between giving money off and paying for reach'
    -> 'Deals and Discounts — the Difference' at rank 1
       beat 'What Promotions Are' at rank 2
```

"Giving money off" is discount vocabulary, and it pulled the discount document
ahead of the one that actually answers the question — `What Promotions Are`,
which carries the section separating offers from promotions.

Both documents are in the top 5, so an assistant reading that context would
probably still answer correctly. It is recorded as a failure because the
confusable tier enforces `not_expect`: retrieving the neighbour *first* is the
thing being measured, since the assistant answers from what it reads first.

**Deliberately not fixed.** Adding "money off" and "paying for reach" to that
document would make it pass and make the 98.5% meaningless — the instrument
would have been calibrated against itself. The same rule applies here as to the
API cards: fix content from real merchant messages, not from the queries you
score with.

### What the product numbers do and do not show

The confusable tier was predicted to be the one that moved, and it was. The
superseded synthetic set scored 36/36 across eight well-separated domains; the
real content contains pairs merchants genuinely conflate — offers against
promotions, wallet against payments — and the single miss falls on exactly that
pair.

The negative tier is the one worth trusting. All nine questions the knowledge
base does not cover (GST invoices, staff users, loans, Tally export, khata) score
below the floor, so the assistant declines rather than answering from the nearest
unrelated passage. For a merchant asking about their own money, that is the
failure mode that costs something.

### Superseded measurement

The 19 August run scored **36/36** on product knowledge. That measured 22
synthetic documents against a different set of 36 queries, and is not comparable
to the numbers above. It is kept only as evidence that the chunking and
retrieval path works; it says nothing about the content now in place.

---

## What changed since the previous measurement

The earlier run scored 46/53 (86.8%) on instructions against a 33-card
catalogue. Two things moved the number, and only one of them was a code change.

### Modelling offers correctly

`offers.create` was an invented endpoint. In the real contract there is no such
thing: a merchant says "offer" for two different actions that share one
MPIN-gated endpoint and differ only by a discriminator.

```
POST /v1/merchant/{merchantId}/mpin-actions
  purpose = DEAL_CREATE      -> what the customer receives changes
  purpose = DISCOUNT_CREATE  -> what the customer pays changes
```

Six confusable pairs were added for exactly this — *"free dessert with any bill
over 500"* against *"flat 100 rupees off on orders above 800"*, and four more.
**All six pass.** Describing a domain the way it actually works, rather than the
way it was convenient to invent, was worth more than any tuning.

### A negative case that stopped being negative

`"what's the weather like today"` was written as a negative when there was no
weather domain. Once one existed it became a legitimate action, and the resolver
was right to act on it. It is now labelled `easy` with `expect: weather.current`.

Worth remembering: **the negative tier has to be maintained alongside the
catalogue.** A question today is an instruction as soon as an API can answer it.

---

## Reading these numbers

### Product knowledge holds up on real content

67/68, with the only miss on the offers-versus-promotions pair described above.
Both halves of that pair reach the assistant's context; they arrive in the wrong
order.

The tier that matters is `negative`: 9/9. Questions the knowledge base genuinely
does not cover — GST invoices, staff users, loan eligibility, Tally export,
khata — all score below the floor, so the assistant declines instead of answering
from the nearest unrelated passage.

Khata is worth calling out, because it is the one place where content policy and
retrieval meet. The source material mentions it once in passing, so no document
was written for it, and inventing one to fill the gap would have produced a
confident wrong answer to a question about a merchant's own credit book. Leaving
the gap is what makes "I don't know" the outcome.

### The negative tier is not a tuning problem

Six of nine questions are still treated as instructions:

```
'what does khata actually mean'             -> khata.customer.list      @0.763
'explain how settlements work'              -> payments.settlement.list @0.756
"what happens if I don't accept an order"   -> orders.status.update     @0.727
'is it better to run a deal or a discount'  -> offers.deal.create       @0.737
```

**These score in the same range as correct actions.** "Explain how settlements
work" and "show me my settlements" are nearly identical in embedding space — they
differ in grammatical mood, not in meaning, and an embedding model captures mood
weakly.

The threshold sweep confirms no setting fixes it. Buying the negative tier costs
the positive tiers roughly one-for-one; at `min_score=0.75, margin=0.06` the
negatives reach 80% and the confusable tier collapses to 12%.

**Separating a question from an instruction belongs in the orchestrator's intent
step, before this call is made.** `confidence` is a safety net for that
classifier, not a replacement. Once intent is decided upstream, the number that
matters is **65/72**.

If you want a second signal, the cheapest is already available: resolve the same
message against *both* knowledge bases and compare. A message the product
knowledge base answers better than the catalogue is a question.

---

## The seven positive-tier failures

Three are the right API reported as ambiguous — the pipeline working as designed,
and the orchestrator would ask rather than guess:

```
"let me see everything I'm selling"     catalog.product.list vs offers.list             0.013 apart
'make my existing weekend sale bigger'  offers.update vs offers.discount.create         0.015 apart
'take 20 percent off everything'        offers.discount.create vs catalog.product.list  0.004 apart
```

Four are genuine wrong picks:

```
'show me what customers have ordered'         -> customers.get             (wanted orders.list)
'save this person so I can give them udhaar'  -> khata.entry.create        (wanted customers.create)
'ramesh ne 200 de diye aaj'                   -> khata.entry.create        (wanted khata.entry.settle)
'what came in today from customers'           -> payments.transaction.list (wanted orders.list)
```

Three of the four involve one card — `khata.entry.create` — whose utterances are
broad enough to catch its siblings' traffic. That is a content diagnosis, and
sharpening those utterances is exactly the guidance in
[API_CATALOG_GUIDE.md](../../docs/API_CATALOG_GUIDE.md).

### Why that card has not been fixed here

Deliberate. Tuning the seed content against this evaluation set would make the
numbers go up and the measurement meaningless — the instrument would have been
calibrated against itself.

Fix cards using **real merchant messages** as you collect them, and keep this set
as the independent check. The same discipline applies when you replace these
queries with real ones: never add an utterance copied from a query you score
against.

---

## One change that measured as nothing

The card chunk was given a line naming its fields in words — *"Needs: offer name,
discount type (percentage or flat), discount value."* — so a chunk read on its
own says what the API takes. The catalogue was re-embedded and the set re-run:
**identical results, same failures in the same tiers.** The utterance chunks
dominate matching, which is by design.

Kept for legibility. Recorded as no measured improvement, not as one.

---

## Cost of a run

fal bills per token rather than per request, so there is no daily ceiling to
plan around any more — only a bill. Measured at roughly **$0.0000002 per
token**, from `cost` on the responses.

| | texts | approx tokens |
|---|---|---|
| Full catalogue reload (41 cards) | 293 | ~35,000 |
| Full product reload (28 documents) | 195 | ~20,000 |
| One action evaluation | 81 | ~1,200 |
| One product evaluation | 68 | ~800 |
| Threshold sweep | 81 | ~1,200 |

Every figure here is fractions of a cent. Reloading both knowledge bases and
running the full evaluation costs well under a cent, so iterating on content is
no longer rationed — which is the main practical gain from the move.

### What the free tier used to cost us, kept as a warning

Before 21 August this ran on Gemini's free tier, capped at **1,000 embed
requests per day**, one per text. Two things about it cost real time and are
worth remembering if anything is ever moved back onto a free tier:

- **The quota was per Google *project*, not per key.** A fresh key from the same
  project inherited the exhausted quota, so rotating only helped when the new
  key belonged to a different project.
- **A 429 on a daily quota still returned a `retryDelay` of ~50s**, which reads
  exactly like a per-minute limit. The service backed off five times, burned
  four minutes per document, and failed anyway. When a load stalls, read
  `quotaId` from the error body before assuming it will clear.
