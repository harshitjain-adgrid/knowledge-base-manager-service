---
type: api
status: live
api_id: purchases.list
domain: purchases
method: GET
# Verified against the merchant BFF OpenAPI document at /v3/api-docs on
# 2026-09-04. Tagged "Purchases" in that spec.
base_url: https://lp-merchant-app-bff.qa.lesspay.app
path: "/v1/merchant/{merchantId}/purchases"
title: Purchase history
# The merchant-scoped BFF routes require a bearer token -- verified: calling
# one without it returns 401 UNAUTHORIZED with code "Authorization token is
# required". Naming the credential here means the executor refuses the call
# cleanly when it is not configured, instead of sending an unauthenticated
# request and reporting the 401 as though the merchant had done something
# wrong.
auth: lesspay_merchant
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-09-04

fields:
  # Paging, not conversation. A merchant asks "what did I buy" and means the
  # recent ones; nobody says a cursor out loud.
  - name: limit
    type: integer
    required: false
    in: query
    default: 20
    prompt: "How many should I show?"
    example: 20
  - name: cursor
    type: string
    required: false
    in: query
    prompt: "Continue from where?"
    derive: >-
      The nextCursor from the previous response, and only when the merchant
      asks for more. Never invented and never asked for.
  - name: from
    type: string
    required: false
    in: query
    prompt: "From which date?"
    example: "2026-08-01"
  - name: to
    type: string
    required: false
    in: query
    prompt: "Up to which date?"
    example: "2026-08-31"

returns:
  success: [data.purchases, data.hasMore, data.nextCursor]
  errors:
    401: I could not sign in to your account.
    404: That merchant was not found.

# Every one of these is about money the merchant SPENT. That is the whole point
# of the wording: none of them could be read as asking about money coming in,
# because that is a different card entirely and the two are easy to confuse.
utterances:
  - what have I bought from lesspay
  - maine kya kya liya hai
  - show my purchase history
  - "मैंने क्या खरीदा है"
  - kaunse packages liye hain maine
  - list my orders from lesspay
  - purchase history dikhao
  - what did I pay lesspay for
---

Everything the merchant has bought from LessPay, newest first — programs,
packages, deposits and promotions, each with what it was, what it cost and when
it happened.

This is money going OUT of the shop to LessPay. It is not the money customers
pay the shop, and it is not settlements arriving in the bank. A merchant asking
"mera paisa kab aayega" is asking about the other direction entirely and this
card has nothing to say about it.
