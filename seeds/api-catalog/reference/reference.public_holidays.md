---
type: api
status: live  # a real public API — this one can actually be called
api_id: reference.public_holidays
domain: reference
method: GET
path: "/api/v3/PublicHolidays/{year}/{countryCode}"
title: Public holidays
base_url: "https://date.nager.at"
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: year
    type: integer
    required: true
    in: path
    prompt: "Which year?"
    example: 2026
  - name: countryCode
    type: string
    required: true
    in: path
    prompt: "Which country? I need the two-letter code."
    example: US

returns:
  success: ["[].date", "[].localName", "[].name"]
  errors:
    204: That country and year are not covered.

utterances:
  - when is the next public holiday
  - list the holidays this year
  - chutti kab kab hai
  - what are the bank holidays
  - show me the holiday calendar
---

Public holidays for a country and year, from Nager.Date. No API key.

Coverage is uneven — some countries return 204 with no body rather than a list.
Treat an empty response as "not covered", not as "no holidays".
