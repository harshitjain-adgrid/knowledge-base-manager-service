---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: payments.refund.create
domain: payments
method: POST
path: /v1/merchant/payments/refunds
title: Refund a payment
mpin_required: true
idempotent: false
version: 1
last_verified: 2026-08-19

fields:
  - name: transaction_id
    type: string
    required: true
    prompt: "Which payment should I refund?"
  - name: amount
    type: number
    required: false
    prompt: "The full amount, or only part of it?"
  - name: reason
    type: string
    required: true
    prompt: "What is the reason for the refund?"

returns:
  success: [refund_id, amount, expected_by]
  errors:
    404: I could not find that payment.
    409: That payment has already been refunded.
    422: The refund is larger than the original payment.

utterances:
  - refund this customer
  - give the money back
  - paise wapas karne hain
  - process a refund for order 4471
  - return 200 rupees to the customer
  - partial refund kar do
---

Sends money back to a customer for a payment already taken, in full or
in part. It reaches them in three to five working days.

If the order itself should be stopped, `orders.cancel` refunds automatically —
use this one for a refund without a cancellation.
