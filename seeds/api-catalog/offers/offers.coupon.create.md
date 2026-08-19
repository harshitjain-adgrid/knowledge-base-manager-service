---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: offers.coupon.create
domain: offers
method: POST
path: /v1/merchant/offers/coupons
title: Create a coupon code
mpin_required: false
idempotent: false
version: 1
last_verified: 2026-08-19

fields:
  - name: code
    type: string
    required: true
    prompt: "What should the coupon code be?"
    example: DIWALI20
    max_length: 16
  - name: discount_type
    type: enum
    required: true
    prompt: "Percentage off, or a flat amount off?"
    values: [percentage, flat]
  - name: discount_value
    type: number
    required: true
    prompt: "How much off?"
  - name: usage_limit
    type: integer
    required: false
    prompt: "How many times can it be used in total?"

returns:
  success: [coupon_id, code, status]
  errors:
    409: That code is already in use.

utterances:
  - create a coupon code
  - make a promo code for my customers
  - i want a code like DIWALI20
  - coupon banana hai
  - "give customers a code for 10% off"
  - set up a discount code with a usage limit
---

Creates a code the customer types at checkout to get a discount, with
an optional limit on how many times it can be used.

A coupon needs the customer to enter something. For a discount that applies by
itself with no code, use `offers.create`.
