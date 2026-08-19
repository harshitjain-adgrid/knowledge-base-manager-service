# Writing knowledge base content

This is the format for every document that goes into the assistant's knowledge
base. Please follow it exactly — the shape of the file decides how well the
assistant can answer, not just how tidy the file looks.

**Write markdown (`.md`).** Other formats are accepted, but markdown is the only
one where you control where the content is split.

---

## Why the format matters

Documents are cut into **chunks**, and each chunk is stored separately. When a
merchant asks a question, the assistant retrieves **one or two chunks — alone**,
with no surrounding document.

So the test for every section you write is:

> If someone read only this section, with no title, no page around it and no way
> to scroll up — would it still make sense and answer something?

Everything below follows from that one question.

---

## File structure

```markdown
---
title: Creating an Offer
type: guide
tags: [offers, merchant-action]
audience: merchant
status: published
owner: growth-team
last_reviewed: 2026-08-18
---

# Creating an Offer

A merchant can create a percentage or flat-amount offer from the Offers tab.
Offers appear on the shop profile once approved.

## When to use this

Use an offer when you want a discount applied automatically at checkout.
For a code the customer types in manually, create a coupon instead.

## How to create an offer

1. Open **Offers** from the main menu.
2. Tap **Create Offer**.
3. Choose the offer type — percentage, flat amount, or buy-one-get-one.
4. Set the validity dates.
5. Confirm with your MPIN.

The offer goes live within five minutes of approval.

## Required fields

| Field | Required | Notes |
|---|---|---|
| Offer name | Yes | Shown to customers |
| Discount type | Yes | Percentage or flat |
| Discount value | Yes | Max 50% without approval |
| Valid until | No | Defaults to no expiry |

## What if the offer does not appear?

Offers above 50% need approval and stay pending until reviewed. Check the
status on the Offers tab. If it says *Approved* but customers still cannot see
it, confirm the shop profile is public.

## Frequently asked as

- "how do I make an offer"
- "offer kaise banaye"
- "create a discount for my shop"
- "why is my offer not showing"
```

---

## Front matter

The block between `---` lines at the very top. It is read by the service, not
shown to anyone.

| Key | Required | What it does |
|---|---|---|
| `title` | **Yes** | Becomes the document title, and the first part of every chunk's breadcrumb |
| `type` | **Yes** | `guide`, `concept`, `policy`, `capability`, `troubleshooting` |
| `tags` | Recommended | Free-form list, used for filtering later |
| `audience` | Recommended | `merchant` or `internal` — internal notes must never reach a merchant |
| `status` | **Yes** | `draft` or `published`. Anything not `published` is not ready to be answered from |
| `owner` | Recommended | Team or person who maintains it |
| `last_reviewed` | Recommended | `YYYY-MM-DD`. Stale content is worse than missing content, because it is confidently wrong |

`title` and `type` become real fields on the document. Everything else is stored
as metadata you can filter on.

### Choosing `type`

| Type | Use it for | Question it answers |
|---|---|---|
| `concept` | What something means | "What is khata?" |
| `guide` | How to do something | "How do I create an offer?" |
| `troubleshooting` | When something goes wrong | "Why didn't my offer apply?" |
| `policy` | Rules and limits | "What is the refund window?" |
| `capability` | What an API/action does, for the assistant's tool selection | "Can you create an offer for me?" |

---

## The rules

### 1. One topic per file

If a file needs "and" in its title, it is two files. `Creating and Editing
Offers` should be `Creating an Offer` and `Editing an Offer`.

### 2. Every section must stand alone

This is the important one. A section is split off and read by itself.

**Bad** — meaningless alone:

```markdown
## Validity

Same shape and rules as the deal validity above.
```

**Good** — complete on its own:

```markdown
## Discount validity fields

A discount's validity uses the same fields as a deal: `startDate` and
`endDate`, both ISO-8601, with `endDate` required when `isLimited` is true.
```

### 3. Never write "above", "below", "as mentioned earlier", "see the previous section"

There is no above or below. The reader sees one section. If you need to point at
something, name it: *"see the Refund Timing document"*, not *"see below"*.

### 4. Use headings for every real section

Headings are where the document gets cut. A wall of text with no headings gets
cut at arbitrary points, mid-sentence.

Use `#` once for the document title, `##` for sections, `###` for subsections.
Don't skip levels.

### 5. Keep sections between roughly 100 and 1,200 characters

Under ~100 characters usually means the section should be merged into its
neighbour. Over ~1,200 means it will be split automatically — better that you
choose the split point by adding a heading.

### 6. Write in the merchant's words, not ours

The assistant matches the merchant's question against your text. If they say
"scheme" and you only ever write "campaign", the match is weaker.

Include the words real merchants use, including Hinglish. Where an internal term
is unavoidable, gloss it once: *"An offer (internally: a campaign) is …"*

### 7. Add a "Frequently asked as" section

List real phrasings, one per line, including misspellings and Hinglish. This is
the single cheapest way to improve retrieval, because it matches question to
question instead of question to prose.

### 8. Cover the "what if"

Most knowledge bases only document the happy path, and merchants mostly ask
about the unhappy one. For every guide, add at least one *what if it goes wrong*
section. Mine real support tickets for these.

### 9. Tables need headers that explain themselves

Column headers are repeated on every piece when a long table is split, so make
them meaningful. `Field | Required | Notes` is good; `A | B | C` is not.

### 10. Never put merchant data in the knowledge base

No coupon lists, khata balances, transaction exports, phone numbers or customer
names. Ever. That data belongs in the application database and is fetched live.
Anything written here is embedded, cannot be selectively deleted, and is visible
to every merchant.

Write **rules and explanations**, never **records**.

---

## Naming and folders

Use lowercase, hyphenated file names matching the title:

```
creating-an-offer.md
what-is-khata.md
refund-policy.md
```

Group by product area, not by team:

```
/offers/
  creating-an-offer.md
  editing-an-offer.md
  offer-not-showing.md
/khata/
  what-is-khata.md
  adding-a-khata-entry.md
/payments/
  refund-policy.md
  settlement-schedule.md
```

---

## Before you submit — checklist

- [ ] Front matter has `title`, `type` and `status`
- [ ] One topic, and the title says exactly what it is
- [ ] Every `##` section makes sense read on its own
- [ ] No "above", "below", "as mentioned earlier"
- [ ] Merchant vocabulary, plus Hinglish phrasings where they exist
- [ ] A "Frequently asked as" section with at least three real phrasings
- [ ] At least one "what if it goes wrong" section
- [ ] Tables have meaningful column headers
- [ ] **No merchant data of any kind**
- [ ] `status: published` only when it is genuinely ready to be answered from

---

## How to check your work

Upload the file, then open **Search Simulator** and ask the questions from your
"Frequently asked as" list. Your document should come back first.

If it doesn't, the usual cause is vocabulary — the merchant's words aren't in
your text.

Then open the document and read the **Chunks** tab. That is exactly what the
assistant sees. If a chunk doesn't make sense to you on its own, it won't to the
assistant either — add a heading or rewrite the section so it does.
