---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: payments.link.create
domain: payments
method: POST
path: /v1/merchant/payments/links
title: Create a payment link
mpin_required: false
idempotent: false
version: 1
last_verified: 2026-08-19

fields:
  - name: amount
    type: number
    required: true
    prompt: "How much should the link be for?"
  - name: description
    type: string
    required: false
    prompt: "What is the payment for?"
  - name: expires_in_hours
    type: integer
    required: false
    prompt: "How long should the link stay valid?"
    default: 24

returns:
  success: [link_id, url, expires_at]
  errors:
    422: The amount has to be at least ₹1.

utterances:
  - create a payment link for 500
  - send a link so the customer can pay
  - payment link banao
  - i need a link to collect money
  - make a upi payment link
  - generate a link for 1200 rupees
---

Creates a link the merchant can send to a customer to collect money.
Works for any amount and is not tied to an order.

For collecting against a khata balance, `khata.reminder.send` includes a link
already.
