---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: store.timings.update
domain: store
method: PUT
path: /v1/merchant/store/timings
title: Set opening hours
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: opens_at
    type: time
    required: true
    prompt: "What time do you open?"
    example: "09:00"
  - name: closes_at
    type: time
    required: true
    prompt: "What time do you close?"
    example: "21:00"
  - name: closed_days
    type: array
    required: false
    prompt: "Any weekly day off?"

returns:
  success: [timings]
  errors:
    422: The closing time has to be after the opening time.

utterances:
  - change my shop timings
  - i open at 9 and close at 9
  - dukaan ka time set karna hai
  - set my opening hours
  - my shop is closed on sundays
  - update store open close time
---

Sets when the shop is open. Outside these hours customers can browse but
not order.

For a one-off closure like a festival, use `store.holiday.set`.
