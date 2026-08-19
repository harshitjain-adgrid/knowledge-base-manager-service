# The API catalogue format

This is what the backend team fills in, one file per endpoint. It is the
counterpart to [CONTENT_GUIDE.md](CONTENT_GUIDE.md), which covers product
documentation.

Product documentation answers questions. This catalogue answers a different
question — **"which single action did the merchant just ask for?"** — and that
difference drives every rule below.

---

## The file

One API, one markdown file, in a folder named after its domain.

```
offers/offers.create.md
khata/khata.entry.create.md
catalog/catalog.stock.update.md
```

Front matter is the machine-readable contract. The body is what a merchant's
question is matched against. Both matter, and they are read by completely
different things.

````markdown
---
type: api
api_id: offers.create
domain: offers
method: POST
path: /v1/merchant/offers
title: Create an offer
mpin_required: false
idempotent: false
version: 1
last_verified: 2026-08-19

fields:
  - name: offer_name
    type: string
    required: true
    max_length: 40
    prompt: "What should this offer be called?"
    example: Sunday Special
  - name: discount_type
    type: enum
    required: true
    prompt: "Percentage off, or a flat amount off?"
    values: [percentage, flat]
  - name: valid_until
    type: date
    required: false
    default: +30d
    prompt: "Until when should it run?"

returns:
  success: [offer_id, status, live_from]
  errors:
    409: An offer with that name is already running.
    422: That discount is larger than your plan allows.

utterances:
  - "start a 20% off sale"
  - create an offer for diwali
  - "मुझे 20% का ऑफर बनाना है"
  - discount lagana hai
  - give 100 rupees off on orders above 500
---

Creates a discount on the shop — either a percentage off or a flat amount off —
and puts it live. It can cover the whole shop or selected products.

This makes a new offer. Changing one that already runs is `offers.update`, and a
code the customer has to type is `offers.coupon.create`.
````

---

## Front matter

| Field | Required | What it is for |
|---|---|---|
| `type` | **Yes** | Always `api`. This is what selects the card chunking strategy. |
| `api_id` | **Yes** | Stable identifier, lowercase, dotted, naming both area and action. This is what the orchestrator acts on. |
| `domain` | **Yes** | Must match the folder name. Drives the narrowing described below. |
| `method` | **Yes** | `GET` / `POST` / `PUT` / `PATCH` / `DELETE`. |
| `path` | **Yes** | Starts with `/`. Path parameters in `{braces}`. |
| `title` | **Yes** | A short human name — "Create an offer", not "POST /v1/merchant/offers". |
| `utterances` | **Yes**, 3 minimum | Example merchant phrasings. See below — these matter more than anything else here. |
| `fields` | Recommended | One entry per request field. |
| `returns` | Recommended | What comes back, and what each error code means in plain words. |
| `mpin_required` | Recommended | `true` for anything that moves money or destroys data. |
| `idempotent` | Recommended | Whether calling twice is safe. Decides whether a retry is allowed. |
| `version` | Recommended | Bump when the contract changes. |
| `last_verified` | Recommended | `YYYY-MM-DD`. A stale contract makes every call fail, so this is not decoration. |

Anything invalid is **refused at upload** with every problem listed at once. A
broken contract stored is a runtime failure deferred to the worst possible
moment.

### Fields

```yaml
- name: discount_value
  type: number          # string | number | integer | boolean | date | time | enum | array
  required: true
  prompt: "How much off?"           # required whenever `required: true`
  example: 20
  values: [percentage, flat]        # for enums
  default: +30d
  max_length: 40
```

**`prompt` is not optional on a required field.** It is the sentence the
assistant says when the merchant has not supplied that field yet. Without it
there is literally nothing to ask, and the upload is rejected.

Write prompts as a person would speak. "How much off?" — not "Enter
discount_value".

---

## Utterances: the part that decides whether any of this works

Everything else here is bookkeeping. The utterances are what retrieval actually
matches against.

Each one is indexed as its own entry. When a merchant types *"give 20% off this
weekend"*, that phrase is compared against other short phrases a person wrote —
which is a far stronger signal than comparing it against a paragraph of
description.

### Rules

**Write what a merchant types, not what the API is called.** The endpoint is
"Create Deal / Create Discount". No merchant has ever typed that. They type
"start a sale".

**Cover the languages your merchants use.** Hindi, Hinglish and English all
appear in real messages, often in the same sentence. Include all three.

**Five to ten per API.** Fewer and the coverage is thin. Many more and they
begin to overlap with a sibling API's phrasings, which makes both harder to tell
apart.

**Vary the shape, not just the words.** A command ("add a product"), a statement
of intent ("i want to list something new"), a situation ("i started selling a
new thing"). Merchants use all three and they embed differently.

**Do not pad with near-duplicates.** "create an offer" and "create offer" add
nothing. Duplicates are stripped at ingest anyway.

---

## The body

Two or three sentences of description, then — and this is the part people skip —
**what the API is not for**, naming the sibling it gets confused with.

```markdown
This makes a new offer. Changing one that already runs is `offers.update`, and a
code the customer has to type is `offers.coupon.create`.
```

That sentence does not help retrieval much. It helps the model that picks one
from the shortlist, which is exactly where create-versus-update mistakes happen.

The body must fit in one chunk. A card is **never split**, because half a card
is a description with no `api_id`, or an `api_id` with no description. If it is
too long, the upload is refused and says so.

---

## Domains

The folder an API lives in. Eight to fifteen across a catalogue.

**Shape them the way a merchant thinks about their day, not the way the backend
is factored.** A merchant does not know that offers and coupons come from one
service; they know "my discounts" and "my prices" are different things. If the
domains mirror your service topology instead of the merchant's mental model,
narrowing accuracy drops and no amount of tuning recovers it.

Domains are not used as a hard filter. Selection searches the whole catalogue
first and infers the domain from where the evidence lands, so a badly chosen
domain costs precision but never makes an API unreachable.

---

## How selection uses all this

Roughly, so the format makes sense:

1. The merchant's message is embedded once.
2. Every chunk in the catalogue is searched — cards and utterances together.
3. Hits are collapsed to one candidate per `api_id`, scored by its best chunk.
4. Domains are ranked by their strongest API; those close to the best stay in
   play, and the rest drop out.
5. If narrowing leaves too little, the unfiltered ranking is used instead. It
   was computed in step 2, so this costs nothing.
6. The result carries a confidence: **high** means act, **ambiguous** means ask
   which of the top two was meant, **low** means treat the message as a question
   rather than an instruction.

Everything after step 1 is deterministic. The same message against the same
catalogue always resolves the same way, which is what makes a regression
visible.

Full endpoint documentation: [API_GUIDE.md](API_GUIDE.md#post-apiv1actionsresolve).

---

## Checklist before handing a card over

- [ ] `api_id` names both the area and the action, and will not change
- [ ] `domain` matches the folder
- [ ] `method` and `path` are copied from the real spec, not from memory
- [ ] Every required field has a `prompt` a person would actually say
- [ ] `returns.errors` explains each code in words a merchant can act on
- [ ] `mpin_required` is set for anything that moves money or deletes data
- [ ] Five or more utterances, in every language your merchants use
- [ ] The body names the sibling API this one gets confused with
- [ ] `last_verified` is today

---

## Generating rather than writing

Hand-writing three hundred of these is months of work, and most of it is
mechanical.

If the backend team has an **OpenAPI spec or a Postman collection**, generate the
front matter from it — `method`, `path`, `fields`, `returns` all come straight
across. Humans then write only the body and the utterances.

That is the right split. The generated half is what a machine can produce; the
written half is what decides whether retrieval works at all.

---

## Keeping it true

A stale product document gives a slightly wrong answer. **A stale contract makes
every call fail.**

- Bump `version` and `last_verified` on every change.
- Treat a contract older than a quarter as suspect.
- If the backend publishes a spec, diff it against the catalogue in CI and raise
  a ticket on drift. This is the single highest-value piece of automation around
  the catalogue.
