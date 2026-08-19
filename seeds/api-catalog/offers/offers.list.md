---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: offers.list
domain: offers
method: GET
path: /v1/merchant/offers
title: See my offers
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: status
    type: enum
    required: false
    prompt: "Running ones, upcoming ones, or all of them?"
    values: [live, scheduled, ended]

returns:
  success: [offers, total]

utterances:
  - what offers do i have running
  - show my discounts
  - kaun se offer chal rahe hain
  - list all my sales
  - do i have any offer on right now
  - show me my past offers
---

Lists the shop's discounts — running, scheduled and finished — with
how much each one has been used.

For coupon codes specifically, this returns them too, marked as coupons.
