---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: orders.list
domain: orders
method: GET
path: /v1/merchant/orders
title: See my orders
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: status
    type: enum
    required: false
    prompt: "Which kind of orders — new ones, or everything?"
    values: [new, preparing, ready, delivered, cancelled]
  - name: from_date
    type: date
    required: false
    prompt: "From which date?"

returns:
  success: [orders, total]

utterances:
  - "show me today's orders"
  - how many orders came in
  - aaj ke orders dikhao
  - list my pending orders
  - what orders do i have to deliver
  - show orders from yesterday
  - koi naya order aaya kya
---

Lists orders customers have placed, newest first, with what was ordered
and how much. Can be narrowed to a status or a date range.

This is what customers have bought. What the shop sells is
`catalog.product.list`.
