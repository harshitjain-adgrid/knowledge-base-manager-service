---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: store.holiday.set
domain: store
method: POST
path: /v1/merchant/store/holidays
title: Mark a holiday
mpin_required: false
idempotent: false
version: 1
last_verified: 2026-08-19

fields:
  - name: from_date
    type: date
    required: true
    prompt: "From which date will you be closed?"
  - name: to_date
    type: date
    required: false
    prompt: "Until when?"
  - name: reason
    type: string
    required: false
    prompt: "Should I tell customers why?"

returns:
  success: [holiday_id, from_date, to_date]

utterances:
  - my shop will be closed tomorrow
  - mark holiday for diwali
  - chutti hai kal
  - close my store for three days
  - i am going out of town, shut the shop
  - set a holiday on my store
---

Closes the shop for a day or a range of days. Customers see a note
saying when it reopens.

This is for particular dates. A regular weekly day off belongs in
`store.timings.update`.
