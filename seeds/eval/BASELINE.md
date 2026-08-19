# Baseline results

> **These numbers predate the offers rewrite and the real public-API domains.**
> They were measured against a 33-card catalogue in which `offers.create` was a
> single invented endpoint. The catalogue is now 41 cards: `offers.create` has
> been replaced by `offers.deal.create` and `offers.discount.create` — one
> merchant word, two payloads behind one MPIN-gated endpoint — and the
> `weather` and `reference` domains have been added.
>
> **Re-run `run_eval.py` after reloading the catalogue and replace this file.**
> The action-selection numbers below are not valid for the current content; the
> product-knowledge numbers are, since that side did not change.

Measured 19 August 2026 against the seed content, `gemini-embedding-2` at 3072
dimensions, `min_score=0.65`, `decision_margin=0.02`.

Re-run after any change to the content, the chunking, or the thresholds. A drop
against these numbers is a regression.

```
PRODUCT KNOWLEDGE  (recall@5)
  easy          19/19  100.0%
  medium         8/8   100.0%
  confusable     5/5   100.0%
  negative       4/4   100.0%
  overall       36/36  100.0%

ACTION SELECTION
  easy          18/21   85.7%
  medium        14/16   87.5%
  confusable    14/16   87.5%
  negative       4/10   40.0%
  overall       50/63   79.4%

retrieval latency: 2058ms mean, 3898ms worst   (over an SSH tunnel)
```

### One change that measured as nothing

After these numbers were taken, the card chunk was given a line naming its
fields in words — *"Needs: offer name, discount type (percentage or flat),
discount value."* — so that a chunk read on its own says what the API takes.

The catalogue was re-embedded and the set re-run. **The result was identical:
50/63, the same failures in the same tiers.** The utterance chunks dominate
matching, which is by design, so enriching the card text moved nothing.

It was kept anyway, because it makes a chunk legible to a person reading it in
the simulator — but it is recorded here as no measured improvement, not as one.

---

## Reading these numbers

### Product knowledge is solved

100% across every tier, including the negatives — questions nothing in the
knowledge base covers ("how do I file my GST return") all score below the 0.70
floor, so the assistant will say it does not know rather than answering from the
nearest unrelated passage.

Heading-aware chunking is doing the work here. Every document is a set of
self-contained sections, and a question lands on the section that answers it.

### Action selection on real instructions: 46/53 (86.8%)

Counting only the tiers that contain actual instructions — easy, medium and
confusable — 46 of 53 resolve correctly.

The confusable tier at 87.5% is the number worth noting: those are pairs chosen
specifically to be hard (create versus update, credit given versus payment
received, orders versus catalogue). Fourteen of sixteen land on the right side.

### The negative tier is not a tuning problem

Six of ten questions were treated as instructions:

```
'what does khata actually mean'            -> khata.customer.list      @0.763
'explain how settlements work'             -> payments.settlement.list @0.756
"what happens if I don't accept an order"  -> orders.status.update     @0.727
'is it better to give a coupon or a flat discount' -> offers.coupon.create @0.729
```

**These score in the same range as correct actions.** "Explain how settlements
work" and "show me my settlements" are nearly identical in embedding space —
they differ in grammatical mood, not in meaning, and an embedding model captures
mood weakly.

The threshold sweep confirms there is no setting that fixes this:

| min_score | margin | easy | medium | confusable | negative | overall |
|---|---|---|---|---|---|---|
| 0.60 | 0.01 | 90% | 88% | 94% | 10% | 77.8% |
| **0.65** | **0.02** | **86%** | **88%** | **88%** | **40%** | **79.4%** |
| 0.70 | 0.02 | 86% | 88% | 81% | 50% | 79.4% |
| 0.75 | 0.00 | 76% | 75% | 69% | 80% | 74.6% |
| 0.75 | 0.06 | 57% | 62% | 12% | 80% | 50.8% |

Buying the negative tier costs the positive tiers roughly one-for-one. At
0.75/0.06 the negatives reach 80% and the confusable tier collapses to 12%.

**Conclusion: separating a question from an instruction belongs in the
orchestrator's intent step, before this call is made.** `confidence` is a safety
net for that classifier, not a replacement for it. Once intent is decided
upstream, the number that matters is 46/53 on real instructions.

If you want a second signal, the cheapest one is already available: resolve the
same message against *both* knowledge bases and compare. A message the product
knowledge base answers better than the catalogue is a question.

---

## The seven positive-tier failures

Two are the right API reported as ambiguous — the pipeline working as designed,
and the orchestrator would ask rather than guess:

```
"let me see everything I'm selling"   catalog.product.list vs offers.list      0.013 apart
'set up a fresh discount next month'  offers.create vs offers.coupon.create    0.014 apart
```

Five are genuine wrong picks:

```
'I want to give my customers 25 percent off'  -> offers.coupon.create  (wanted offers.create)
'show me what customers have ordered'         -> customers.get         (wanted orders.list)
'save this person so I can give them udhaar'  -> khata.entry.create    (wanted customers.create)
'ramesh ne 200 de diye aaj'                   -> khata.entry.create    (wanted khata.entry.settle)
'what came in today from customers'           -> payments.transaction.list (wanted orders.list)
```

Four of the five involve just two cards — `offers.coupon.create` and
`khata.entry.create`. Both have utterances broad enough to catch their siblings'
traffic. `offers.coupon.create` says *"give customers a code for 10% off"*, which
sits very close to *"give my customers 25 percent off"* while the word doing the
real work — **code** — carries little weight.

**That is a content diagnosis, and it is the right kind of fix.** Sharpening a
card's utterances so they lean on what makes it distinctive is exactly the
guidance in [API_CATALOG_GUIDE.md](../../docs/API_CATALOG_GUIDE.md).

### Why those cards have not been fixed here

Deliberate. Tuning the seed content against this evaluation set would make the
numbers go up and the measurement meaningless — the instrument would have been
calibrated against itself.

Fix cards using **real merchant messages** as you collect them, and keep this set
as the independent check. When you replace these queries with real ones, the same
discipline applies: never add an utterance copied from a query you are scoring
against.
