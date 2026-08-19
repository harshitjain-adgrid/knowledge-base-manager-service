---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: offers.update
domain: offers
method: PATCH
path: "/v1/merchant/offers/{offer_id}"
title: Change an offer
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: offer_id
    type: string
    required: true
    prompt: "Which offer should I change?"
  - name: discount_value
    type: number
    required: false
    prompt: "What should the new discount be?"
  - name: valid_until
    type: date
    required: false
    prompt: "When should it end now?"

returns:
  success: [offer_id, updated_fields]
  errors:
    404: I could not find that offer.
    409: That offer has already ended and cannot be changed.

utterances:
  - change my offer to 30 percent
  - extend my sale by a week
  - edit the diwali offer
  - offer ki date badha do
  - make the discount bigger
  - modify a running offer
  - my sale should end tomorrow instead
---

Changes a discount that is already running — its value, its end date,
or what it applies to. The change takes effect immediately.

For a brand new discount use `offers.create`. To end one early use
`offers.deactivate`.
