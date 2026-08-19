# Baseline results

Measured 19 August 2026 against the 41-card catalogue and 22 product documents.
`gemini-embedding-2` at 3072 dimensions, `min_score=0.65`,
`decision_margin=0.02`.

Re-run after any change to the content, the chunking, or the thresholds. A drop
against these numbers is a regression.

Measured through `/search`. The knowledge base retrieves; the collapsing and
ranking that turn chunk hits into one API live in `selection.py` beside the
evaluation, because that decision belongs to the orchestrator rather than to
this service.

Re-measured unchanged after the move to one schema with a table pair per
knowledge base (`kb_product_knowledge_*`, `kb_api_catalog_*`) — identical numbers
tier, which is what confirms the migration moved the data rather than rebuilding
it.

```
PRODUCT KNOWLEDGE  (recall@5)
  easy          19/19  100.0%
  medium         8/8   100.0%
  confusable     5/5   100.0%
  negative       4/4   100.0%
  overall       36/36  100.0%

ACTION SELECTION
  easy          25/27   92.6%
  medium        18/20   90.0%
  confusable    22/25   88.0%
  negative       3/9    33.3%
  overall       68/81   84.0%

retrieval latency: 2306ms mean, 5024ms worst   (over an SSH tunnel)
```

**On real instructions — every tier except `negative` — 65 of 72, 90.3%.**

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

### Product knowledge is solved

100% across every tier, including negatives — questions nothing in the knowledge
base covers ("how do I file my GST return") all score below the 0.70 floor, so
the assistant says it does not know rather than answering from the nearest
unrelated passage.

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

The Gemini free tier allows **1,000 embed requests per day**, and each text
counts as one.

| | requests |
|---|---|
| Full catalogue reload (41 cards) | 293 |
| Full product reload (19 documents) | ~115 |
| One action evaluation | 81 |
| One product evaluation | 36 |
| Threshold sweep | 81 |

Reading is cheap — one request per query. **Ingestion is what exhausts the
quota**, and a day of iterating on content will hit the ceiling. Rotate the key
in Settings, or move off the free tier before doing bulk reloads.
