---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: orders.get
domain: orders
method: GET
path: "/v1/merchant/orders/{order_id}"
title: See one order
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: order_id
    type: string
    required: true
    prompt: "Which order number?"

returns:
  success: [order]
  errors:
    404: I could not find that order.

utterances:
  - show me order 4471
  - what was in that order
  - open this order for me
  - order ka detail dikhao
  - who placed this order and what did they buy
  - check details of a particular order
---

Shows everything about a single order — the items, the customer, the
amount, the payment status and the delivery address.
