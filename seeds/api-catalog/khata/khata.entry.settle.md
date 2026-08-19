---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: khata.entry.settle
domain: khata
method: POST
path: /v1/merchant/khata/entries/settle
title: Record a payment received
mpin_required: false
idempotent: false
version: 1
last_verified: 2026-08-19

fields:
  - name: customer_name
    type: string
    required: true
    prompt: "Who paid you?"
  - name: amount
    type: number
    required: true
    prompt: "How much did they pay?"
  - name: payment_mode
    type: enum
    required: false
    prompt: "Cash, UPI, or something else?"
    default: cash
    values: [cash, upi, card, other]

returns:
  success: [entry_id, customer_balance]
  errors:
    404: I do not have a khata for that customer.
    422: That is more than they owe.

utterances:
  - ramesh paid me 300
  - customer settled his udhaar
  - paise mil gaye, khata update karo
  - record a payment against credit
  - he gave back 500 today
  - mark the khata as paid
  - received 200 from suresh by upi
---

Records money a customer has paid back against their khata. The amount
is subtracted from what they owe; a partial payment is fine.

This is money coming in against credit already given. Recording new credit is
`khata.entry.create`.
