---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: store.delivery.update
domain: store
method: PUT
path: /v1/merchant/store/delivery
title: Set delivery settings
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: radius_km
    type: number
    required: true
    prompt: "How far do you deliver, in kilometres?"
  - name: delivery_fee
    type: number
    required: false
    prompt: "What do you charge for delivery?"
  - name: free_above
    type: number
    required: false
    prompt: "Free delivery above what order value?"

returns:
  success: [delivery]

utterances:
  - change my delivery charges
  - i deliver up to 5 km
  - delivery ka charge set karna hai
  - free delivery above 500
  - set my delivery radius
  - update delivery settings for my shop
---

Sets how far the shop delivers, the delivery charge, and any minimum
order for free delivery.
