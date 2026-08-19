---
type: api
status: live  # a real public API — this one can actually be called
api_id: reference.crypto_price
domain: reference
method: GET
path: /api/v3/simple/price
title: Crypto price
base_url: "https://api.coingecko.com"
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: ids
    type: string
    required: true
    in: query
    prompt: "Which coin?"
    example: bitcoin
  - name: vs_currencies
    type: string
    required: true
    in: query
    prompt: "Priced in which currency?"
    example: inr

returns:
  success: ["{coin}.{currency}"]
  errors:
    429: CoinGecko is rate limiting — try again in a minute.

utterances:
  - what is bitcoin trading at
  - bitcoin ka rate batao
  - price of ethereum in rupees
  - how much is one bitcoin today
  - crypto price check
---

Current price of a cryptocurrency in one or more currencies, from
CoinGecko's public tier. No API key, but it is rate limited — expect a 429 under
load.
