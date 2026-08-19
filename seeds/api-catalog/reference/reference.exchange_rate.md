---
type: api
status: live  # a real public API — this one can actually be called
api_id: reference.exchange_rate
domain: reference
method: GET
path: /latest
title: Currency exchange rate
base_url: "https://api.frankfurter.app"
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: from
    type: string
    required: true
    in: query
    prompt: "Converting from which currency?"
    example: USD
  - name: to
    type: string
    required: false
    in: query
    prompt: "Into which currency?"
    example: INR
  - name: amount
    type: number
    required: false
    in: query
    prompt: "How much?"
    default: 1

returns:
  success: [base, date, rates]
  errors:
    404: One of those currency codes is not recognised.

utterances:
  - what is the dollar rate today
  - convert 100 usd to rupees
  - dollar ka rate kya hai
  - exchange rate for euro
  - how many rupees is one pound
---

Reference exchange rates published by the European Central Bank, via
Frankfurter. No API key. Rates update on working days only.
