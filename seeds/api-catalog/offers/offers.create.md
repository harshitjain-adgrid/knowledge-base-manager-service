---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: offers.create
domain: offers
method: POST
path: /v1/merchant/offers
title: Create an offer
mpin_required: false
idempotent: false
version: 1
last_verified: 2026-08-19

fields:
  - name: offer_name
    type: string
    required: true
    prompt: "What should this offer be called?"
    example: Sunday Special
    max_length: 40
  - name: discount_type
    type: enum
    required: true
    prompt: "Percentage off, or a flat amount off?"
    values: [percentage, flat]
  - name: discount_value
    type: number
    required: true
    prompt: "How much off?"
    example: 20
  - name: applies_to
    type: enum
    required: false
    prompt: "On everything, or only on some products?"
    default: all
    values: [all, selected]
  - name: valid_until
    type: date
    required: false
    prompt: "Until when should it run?"
    default: +30d
  - name: min_order_value
    type: number
    required: false
    prompt: "Any minimum order amount for it to apply?"

returns:
  success: [offer_id, status, live_from]
  errors:
    409: An offer with that name is already running.
    422: That discount is larger than your plan allows.

utterances:
  - "start a 20% off sale"
  - create an offer for diwali
  - give 100 rupees off on orders above 500
  - "मुझे 20% का ऑफर बनाना है"
  - put my shop on discount this weekend
  - i want to run a sale
  - discount lagana hai
  - make everything 15 percent cheaper till sunday
---

Creates a discount on the shop — either a percentage off or a flat
amount off — and puts it live. It can cover the whole shop or selected products.

This makes a new offer. Changing one that already runs is `offers.update`, and a
code the customer has to type is `offers.coupon.create`.
