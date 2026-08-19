---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: orders.status.update
domain: orders
method: PUT
path: "/v1/merchant/orders/{order_id}/status"
title: "Update an order's status"
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: order_id
    type: string
    required: true
    prompt: "Which order?"
  - name: status
    type: enum
    required: true
    prompt: "What stage is it at now?"
    values: [accepted, preparing, ready, out_for_delivery, delivered]

returns:
  success: [order_id, status, customer_notified]
  errors:
    404: I could not find that order.
    409: That order was cancelled and cannot be moved on.

utterances:
  - mark this order as delivered
  - order ready hai
  - accept the order
  - change order status to out for delivery
  - this one is packed and ready
  - update the order stage
  - maine deliver kar diya
---

Moves an order along — accepted, being prepared, ready, out for
delivery, delivered. The customer is notified at each step.

To stop an order entirely, use `orders.cancel`.
