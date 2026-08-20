---
title: Your UPI QR Code
type: concept
tags: [qr, upi, vpa, payments]
audience: merchant
status: published
owner: product-team
derived_from: chotu-handover.md, product-overview-merchant-customer-apps.md
last_reviewed: 2026-08-20
---

# Your UPI QR Code

Your QR code is how customers pay you and how they find your shop in the app.
Behind it is your **UPI ID** — the address money is sent to, for example
`yourshop@ybl`.

## What the QR does

When a customer scans it, two things happen at once: their app resolves your UPI
ID so it knows where to send the money, and it recognises the shop as yours so
it can show your offers.

That is why paying through your LessPay QR gets the customer your discount, and
paying by typing your UPI ID into another app does not.

## The provider is recognised automatically

LessPay works out which UPI provider your ID belongs to from the ID itself —
the part after the `@`. Common ones include PhonePe, Google Pay, Paytm and BHIM.

You do not choose your provider anywhere. It is read from the UPI ID you enter,
and it is used to brand the QR so customers see a familiar logo.

## The money goes to your UPI account

The QR points at your own UPI ID, so payments land in the bank account attached
to it. LessPay does not sit in the middle holding the money.

## What if your UPI ID is not accepted

LessPay checks a UPI ID when you add it, and rejects one it does not recognise.
This usually means a typo in the part after the `@`, or a provider that is not
supported. Check the ID in your own UPI app and copy it exactly.

## Frequently asked as

- "what is my qr code"
- "qr code kya hai"
- "what is a vpa"
- "upi id kaise add karein"
- "why is my upi id not accepted"
- "which upi apps work"
- "where does the money from the qr go"
