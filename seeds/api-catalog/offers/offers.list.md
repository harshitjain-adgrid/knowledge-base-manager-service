---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: offers.list
domain: offers
method: GET
path: "/v1/merchant/{merchantId}/offers"
title: See my offers
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: offerKind
    type: enum
    required: false
    in: query
    prompt: "Deals, discounts, or both?"
    values: [DEAL, DISCOUNT]
  - name: status
    type: enum
    required: false
    in: query
    prompt: "Running ones, upcoming ones, or all of them?"
    values: [DRAFT, SCHEDULED, ACTIVE, INACTIVE, EXPIRED]

returns:
  success: [offers, total]

utterances:
  - what offers do i have running
  - show my discounts and deals
  - kaun se offer chal rahe hain
  - list all my sales
  - do i have any offer on right now
  - show me my past offers
---

Lists the shop's offers — deals and discounts together — with their
status and how much each has been used. `offerKind` narrows it to one or the
other.

This reads them. Making one is `offers.deal.create` or
`offers.discount.create`.
