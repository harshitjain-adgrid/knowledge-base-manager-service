---
title: Your UPI QR Code
type: concept
tags: [qr, upi, vpa, payments]
audience: merchant
status: published
owner: product-team
last_reviewed: 2026-08-27
review_by: 2027-02-27
answers:
  - what your QR code and UPI ID are
  - why paying through the LessPay QR gets the customer an offer
  - why a UPI ID was not accepted
not_covered:
  - how to add, switch or delete more than one QR
  - what each payment status means
related: [managing-your-qr-codes, how-you-get-paid, how-a-customer-pays-you]
aliases: [qr code, upi id, vpa, scanner, qr kya hai]
entities: [UPI, VPA, UPI ID, PhonePe, Google Pay, Paytm, BHIM]
---

# Your UPI QR Code

Your QR code is how customers pay you and how they find your shop in the app.
Behind it is your **UPI ID** — the address money is sent to, for example
`yourshop@ybl`. It is sometimes called a VPA.

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

## Not this — your UPI address is not your shop's address

Your **UPI ID** is an address only in the sense that money is sent to it —
`yourshop@ybl`. It says nothing about where your shop is.

Your shop's **address** is the street location customers see on your page
and use to find you. Changing one never touches the other.

If the app is refusing something you typed, the two are refused for
different reasons. A UPI ID is refused when the part after the `@` is wrong
or the provider is not supported. A shop address is a separate field on
your shop details. For that one, see "Your Shop Name, Category and
Address".

## Hinglish mein

Aapka QR code wahi hai jisse customer paisa deta hai aur app mein aapki dukaan
pehchanta hai. QR ke peeche aapki UPI ID hoti hai, jaise `yourshop@ybl` — isko
VPA bhi kehte hain. Jab customer LessPay ka QR scan karta hai to do kaam ek
saath hote hain: uske app ko pata chalta hai ki paisa kahan bhejna hai, aur
yeh bhi ki dukaan aapki hai, isliye aapke offer dikh jaate hain. Agar koi
seedhe aapki UPI ID kisi doosre app mein type karke paisa bhejta hai to offer
nahi lagta. UPI provider apne aap `@` ke baad wale hisse se pehchana jata hai.
Dhyan rahe: UPI ID ko bhi 'address' kehte hain, lekin ye aapki
dukaan ke pate se alag cheez hai — ek mein paisa aata hai,
doosre se customer aapko dhoondhta hai.

## Frequently asked as

- "what is my qr code"
- "qr code kya hai"
- "क्यूआर कोड क्या है"
- "what is a vpa"
- "upi id kaise add karein"
- "यूपीआई आईडी कैसे जोड़ें"
- "why is my upi id not accepted"
- "which upi apps work"
- "where does the money from the qr go"
