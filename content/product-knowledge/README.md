# Product knowledge

What Chotu answers merchant questions from. Every document here is real content
derived from LessPay's own product documentation, written for the shopkeeper —
not for an engineer.

Loaded into the `product-knowledge` knowledge base by
[`seeds/load_seeds.py`](../../seeds/load_seeds.py). Authoring rules are in
[`docs/CONTENT_GUIDE.md`](../../docs/CONTENT_GUIDE.md); everything here follows
them and is checked against them.

---

## The domains

A domain is a folder. The folder is the merchant's mental model of their own
business, not the product's internal structure — a shopkeeper thinks *"my
money", "my offers", "my shop"*, not *"the settlement service"*.

| Domain | What lives here | Documents |
|---|---|---|
| `getting-started/` | What LessPay is, what Chotu can do, signing up, the MPIN | 4 |
| `shop-profile/` | Shop details, how you serve customers, photos | 3 |
| `offers/` | Deals, discounts, who gets them, status, why one is not showing | 6 |
| `payments/` | How customers pay you, payment history, settlements to your bank | 3 |
| `qr/` | Your UPI QR, and running more than one | 2 |
| `promotions/` | Paid reach: the channels, what they cost, running a campaign | 3 |
| `wallet/` | Credits, the two buckets, expiry | 2 |
| `subscriptions/` | Packages and programs, and what you actually pay | 2 |
| `referrals/` | Bringing other shops onto LessPay | 1 |
| `customers/` | How customers find you, and what they see | 2 |

28 documents, 167 sections.

### Why these boundaries

Three of them are easy to confuse, so they are drawn deliberately:

- **`offers/` vs `promotions/`** — an offer is the discount itself and is free
  to run. A promotion is paying to show it to more people. Merchants conflate
  them constantly, so each domain says explicitly what the other one is.
- **`wallet/` vs `payments/`** — the wallet is money going *out* (credits you
  spend on promotions). Payments are money coming *in* from customers. They are
  never mixed in one document.
- **`qr/` vs `payments/`** — the QR is the instrument; payments are what it
  produces. Questions about adding or switching a QR go to `qr/`; questions
  about what arrived go to `payments/`.

### The folder is not the retrieval filter

Retrieval into this knowledge base is plain semantic search over all of it. The
folders organise the writing and give the upload a `folder` path; they do not
narrow the search. That is deliberate — merchant questions cross domains freely
(*"why didn't my customer get the discount"* touches offers, QR and payments),
and narrowing on a guessed domain would lose the answer.

Domain-filtered retrieval belongs to the API catalogue, where a question maps
to one tool. It does not belong here.

---

## Front matter

Every document carries the same block:

```yaml
---
title: Creating a Discount          # becomes the document title; must match the H1
type: guide                         # guide | concept | policy | capability | troubleshooting
tags: [offers, discounts, merchant-action]
audience: merchant
status: published
owner: product-team
derived_from: chotu-handover.md     # which source document this was written from
last_reviewed: 2026-08-20
---
```

`title` and `type` become document columns. Everything else is kept as chunk
metadata, so it can be filtered on later without re-embedding.

`derived_from` is provenance — when a source document is revised, it tells you
which files need reviewing. `source` is deliberately not used: the upload path
overwrites it with `file_upload`.

---

## What is deliberately not here

- **Anything API-shaped.** No endpoints, no field names, no wire formats, no
  status codes. Those belong to the API catalogue, and mixing them in makes
  conversational retrieval worse.
- **Merchant data.** No coupon lists, no balances, no transaction exports, no
  names or numbers. The knowledge base explains how things work; a merchant's
  own figures come from the live system at answer time.
- **Anything the sources only mention in passing.** Khata is named once in the
  source material and is not written up. Inventing detail to fill a gap is
  worse than the gap, because it retrieves confidently and is wrong.
- **Internal architecture.** Which service owns what, what is live and what is
  stubbed, how things are stored. None of it answers a shopkeeper's question.

---

## Adding to it

1. Read [`docs/CONTENT_GUIDE.md`](../../docs/CONTENT_GUIDE.md) first.
2. One topic per file. Put it in the domain a merchant would look in.
3. Give every document a **Frequently asked as** section with at least five
   phrasings, including how it is asked in Hinglish. Those lines are what most
   real questions actually match against.
4. Cover the **what if it goes wrong** case. Half of all questions arrive as a
   complaint, not a query.
5. Re-run the loader with `--purge` so the knowledge base matches this folder.
6. Add queries to [`seeds/eval/product_queries.yaml`](../../seeds/eval/product_queries.yaml)
   and re-run the evaluation before considering it done.
