---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: offers.deactivate
domain: offers
method: POST
path: "/v1/merchant/{merchantId}/offers/{offerId}/deactivate"
title: Stop an offer
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: offerId
    type: string
    required: true
    in: path
    prompt: "Which offer should I stop?"

returns:
  success: [id, status]
  errors:
    404: I could not find that offer.

utterances:
  - stop my offer
  - end the sale now
  - offer band kar do
  - cancel the discount i started
  - turn off my diwali deal
  - "i don't want the offer anymore"
---

Ends a running offer straight away, deal or discount. It stays in the
history with everything it earned, it simply stops applying to new orders.

This stops it. To change it rather than stop it, use `offers.update`.
