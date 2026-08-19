---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: reports.top-products
domain: reports
method: GET
path: /v1/merchant/reports/top-products
title: Best selling products
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: period
    type: enum
    required: false
    prompt: "Over what period?"
    default: month
    values: [week, month, quarter]
  - name: limit
    type: integer
    required: false
    prompt: "How many should I show?"
    default: 10

returns:
  success: [products]

utterances:
  - what sells the most in my shop
  - which product is doing well
  - sabse zyada kya bik raha hai
  - show me my best sellers
  - top selling items this month
  - which items are not selling
---

Ranks products by how much they sold over a period, so the merchant can
see what moves and what does not.
