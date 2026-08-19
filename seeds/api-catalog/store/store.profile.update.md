---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: store.profile.update
domain: store
method: PATCH
path: /v1/merchant/store/profile
title: Change shop details
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: store_name
    type: string
    required: false
    prompt: "What should the shop be called?"
  - name: phone
    type: string
    required: false
    prompt: "Which number should customers call?"
  - name: address
    type: string
    required: false
    prompt: "What is the shop's address?"

returns:
  success: [updated_fields]

utterances:
  - change my shop name
  - update my store details
  - dukaan ka naam badalna hai
  - change the phone number customers see
  - edit my shop address
  - update my store profile picture
---

Changes what customers see about the shop — its name, description,
address, phone number or photo.

For opening hours use `store.timings.update`; for the delivery area use
`store.delivery.update`.
