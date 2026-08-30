# Baseline results

Measured 20 August 2026 against the 41-card catalogue and the 28 real product
documents in `content/product-knowledge/`. `gemini-embedding-2` at 3072
dimensions, `min_score=0.65`, `decision_margin=0.02`.

Re-measured 21 August 2026 after moving from Google's API to fal.ai, **same
model, same numbers — 67/68 and 68/81, tier for tier, failure for failure.**

---

## Product knowledge v2 — 27 August 2026

A second corpus, `content/product-knowledge-v2/` in `kb_product_knowledge_v2`:
18 documents, 146 chunks, written to Document Contract v2 from `APP_OVERVIEW.md`
and the internal product knowledge base draft. New subject matter — KYC, joining,
WhatsApp login, the Champion Program, placement, categories, the loyalty economy,
notifications, the customer app — not a rewrite of the 28.

```
PRODUCT KNOWLEDGE v2  (recall@5)   18 documents, 146 chunks, 83 queries
  easy          18/18  100.0%
  medium        26/26  100.0%     18 Roman Hinglish + 8 Devanagari
  procedural     6/6   100.0%
  entity         6/6   100.0%
  confusable     8/12   66.7%
  negative      10/15   66.7%
  overall       74/83   89.2%
```

**The set can fail.** That was the requirement in §2.8 of the strategy — at v1's
98.5% a change that halved retrieval failures showed up as +1 query. There is now
somewhere for the number to go.

### The two tiers that were built to fail did not

`procedural` 6/6 and `entity` 6/6, both perfect on the first run.

- **`procedural`** is the class that produced the only failure a real merchant
  reported — *"offer kaise banau, step by step bataio"* refusing because the
  offers corpus had no numbered procedure to land on. Contract v2 makes numbered
  steps mandatory for every guide and `validate_text_document` rejects a guide
  without them. Six procedural queries, six hits.
- **`entity`** was expected to be the case for a lexical index (§2.1). UTR, KYC,
  STOP, PIN, *Stalls & Kiosks*, *Under review* all retrieved correctly at
  recall@5 from the dense index alone.

**Read the entity result as a caution about §2.1, not a refutation of it.** These
literals appear in body prose and in front-matter `entities`, and this corpus is
18 documents. The BM25 case is about rare tokens in a *large* corpus; a tier that
passes at 18 documents says little about 150. It does mean this tier cannot
currently justify the work — build the corpus out first, then re-measure.

### The negative tier is the finding that matters

Five of six failures are the same shape, and every one is a value the source
document marks `[TBD]`:

```
'what does the champion program tablet cost'   -> What the Champion Program Is  @0.803
'how many coins do I get per referral'         -> How Referral Rewards Are Earned @0.772
'how many times can I resubmit my documents'   -> When Your KYC Is Rejected      @0.772
'how many digits is the pin'                   -> Your PIN and What It Authorises @0.730
'how much is a paid placement per month'       -> Where Your Deal Appears        @0.706
```

This is §1.3 reproduced exactly, on a corpus built after reading §1.3. The
*topic* is covered richly and only the *number* is missing, so the nearest
document scores 0.70–0.80 — higher than plenty of genuinely covered questions.
No threshold separates these from real answers.

It is also the more dangerous half of the failure space. A merchant asking what
the tablet costs gets the Champion Program document at 0.803, and that document
never mentions a price. The model is being handed strong evidence that the topic
is documented, and nothing that answers the question.

**This is the measured case for `type: boundary` documents (§2.6b)** — a document
that says explicitly *"LessPay does not publish a tablet fee here"* turns a
confident invention into a confident, correct decline. It was Phase 5 in the
sequencing; this result argues for pulling it forward, because the gap it covers
is not hypothetical.

### The confusable tier, and where the instrument is at fault

8/12, down from v1's 92.9% — expected, since v2 was written with near-neighbour
pairs on purpose. But the failures split two ways, and honesty about which is
which matters more than the number:

```
'does setting my code verify my business'        -> KYC doc @1, PIN doc not in top 5
'does getting a device make my offers visible'   -> placement @2, Champion not in top 5
"do the shopper's coins come out of my earnings" -> Coins and Credits @1, target @2
'are the texts I get the same as my buyers get'  -> customer-messages @1, target @5
```

The last two retrieved **both** documents, and in both cases the document that
won is arguably the better owner of the question — *"Coins and Credits — Who
Holds What"* exists precisely to answer whether a customer's coins are yours.
Those look like **labelling errors in this evaluation set**, not retrieval
failures.

The first two are genuine: the target never reached the top 5.

There is a pattern worth naming in them. A `## Not this` section (§2.6a) makes a
document match its *neighbour's* queries — `what-kyc-unlocks.md` contains "KYC is
not your PIN", so a PIN-versus-KYC question lands on the KYC document. The
disambiguation works as content and competes as an index entry.

**Nothing was changed in response to any of this.** Relabelling to raise the
number is the same error as adding query vocabulary to a document — the
instrument would have been calibrated against itself either way. The labels and
the content stand until a decision is made deliberately.

### Cost

83 queries at recall@5, 272s over the SSH tunnel. Loading 18 documents was 146
embed calls, 105s.

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
