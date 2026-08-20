---
title: How You Get Paid
type: concept
tags: [payments, upi, qr]
audience: merchant
status: published
owner: product-team
derived_from: product-overview-merchant-customer-apps.md, chotu-handover.md
last_reviewed: 2026-08-20
---

# How You Get Paid

Customers pay you by UPI, by scanning a QR code at your counter. The money goes
to your bank account — LessPay does not hold it in between.

## The payment, step by step

1. The customer scans your QR.
2. Their app recognises your shop and shows every offer they qualify for.
3. They pick one, and the app works out what they owe after the discount.
4. They pay by UPI from their own bank or UPI app.
5. The payment appears in your payments list.

You do not apply the discount by hand. The app has already checked the customer
against the rules you set.

## Two kinds of QR, both counted

Your payments are split by where they came from:

- **LessPay QR** — the QR code LessPay gave you. Offers apply on these payments.
- **Other QR** — payments taken on a QR from another provider.

Both show in your payments, so your day's total is the whole picture rather than
just the LessPay part.

## Payment status

| Status | What it means |
|---|---|
| Success | The money is yours, awaiting settlement |
| Pending | Started and not yet confirmed |
| Failed | It did not go through; nothing was taken |
| Refunded | It was returned to the customer |

## A receipt for every payment

Opening a payment shows what came in and what you actually keep: the amount the
customer paid, the amount after fees, how they paid, and the payer's name.

It also carries the **UTR** — the bank's reference number for the transfer. The
UTR is empty until the payment is settled to your bank, which is normal and not
a sign of a problem.

## What if a payment is missing

- **The customer paid on another provider's QR.** Switch the source filter — it
  will be under other QR, not LessPay QR.
- **It is still pending.** Pending payments have not confirmed yet. Give it a
  few minutes.
- **You are looking at the wrong day.** The day boundary is Indian time. A
  payment taken close to midnight belongs to the day the app says, not the day
  it felt like.

## Frequently asked as

- "how do customers pay me"
- "paisa kaise aata hai"
- "how does the qr payment work"
- "customer ne paisa diya lekin dikh nahi raha"
- "what is utr"
- "payment nahi aaya"
- "where do I see today's payments"
