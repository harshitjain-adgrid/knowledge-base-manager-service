---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: orders.cancel
domain: orders
method: POST
path: "/v1/merchant/orders/{order_id}/cancel"
title: Cancel an order
mpin_required: true
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: order_id
    type: string
    required: true
    prompt: "Which order should I cancel?"
  - name: reason
    type: enum
    required: true
    prompt: "Why is it being cancelled?"
    values: [out_of_stock, customer_request, shop_closed, other]

returns:
  success: [order_id, cancelled_at, refund_initiated]
  errors:
    404: I could not find that order.
    409: That order is already delivered.

utterances:
  - cancel this order
  - "i can't fulfil order 4471"
  - order cancel kar do
  - the customer wants to cancel
  - stop this order, item is out of stock
  - cancel an order and refund it
---

Cancels an order and tells the customer why. If it was already paid
for, the money goes back automatically.

This cancels the order. Refunding a delivered order without cancelling is
`payments.refund.create`.
