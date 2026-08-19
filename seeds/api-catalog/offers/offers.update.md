---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: offers.update
domain: offers
method: PATCH
path: "/v1/merchant/{merchantId}/offers/{offerId}"
title: Change an offer
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: offerId
    type: string
    required: true
    in: path
    prompt: "Which offer should I change?"
  - name: validity
    type: object
    required: false
    prompt: "When should it end now?"
  - name: redeemLimit
    type: integer
    required: false
    prompt: "What should the per-customer limit be?"
  - name: showOnShopProfile
    type: boolean
    required: false
    prompt: "Show it on your shop profile?"

returns:
  success: [id, status, validTill]
  errors:
    404: I could not find that offer.
    409: That offer has already expired and cannot be changed.

utterances:
  - extend my sale by a week
  - edit the diwali offer
  - offer ki date badha do
  - change the limit on my running offer
  - modify an offer i already made
  - my offer should end tomorrow instead
---

Changes an offer that already exists — its validity, its caps, or
whether it shows on the shop profile. Works for both deals and discounts.

For a brand new one use `offers.deal.create` or `offers.discount.create`. To end
one early use `offers.deactivate`.
