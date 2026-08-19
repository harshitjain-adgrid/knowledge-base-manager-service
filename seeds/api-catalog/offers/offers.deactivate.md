---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: offers.deactivate
domain: offers
method: POST
path: "/v1/merchant/offers/{offer_id}/deactivate"
title: Stop an offer
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: offer_id
    type: string
    required: true
    prompt: "Which offer should I stop?"

returns:
  success: [offer_id, ended_at]
  errors:
    404: I could not find that offer.

utterances:
  - stop my offer
  - end the sale now
  - offer band kar do
  - cancel the discount i started
  - turn off my diwali offer
  - "i don't want the discount anymore"
---

Ends a running discount straight away. The offer stays in the history
with everything it earned, it simply stops applying to new orders.

This stops it. To change it rather than stop it, use `offers.update`.
