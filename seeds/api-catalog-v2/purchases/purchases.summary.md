---
type: api
status: live
api_id: purchases.summary
domain: purchases
method: GET
# Verified against the merchant BFF OpenAPI document at /v3/api-docs on
# 2026-09-04. The spec's own summary for this route is "The spend card".
base_url: https://lp-merchant-app-bff.qa.lesspay.app
path: "/v1/merchant/{merchantId}/purchases/summary"
title: Total spend with LessPay
auth: lesspay_merchant
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-09-04

fields:
  # Both optional. Asked for only when the merchant names a period themselves --
  # "how much have I spent" with no period is a complete question and deserves a
  # complete answer, not two clarifying ones.
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
  # totalCash is the headline. The rest break it down by what the money went on,
  # and depositHeld is different in kind from the others -- it is money held
  # rather than money spent, so reporting it inside a total would overstate what
  # the shop has actually paid out.
  success: [data.totalCash, data.currency, data.programs, data.packages, data.promotion, data.depositHeld]
  errors:
    401: I could not sign in to your account.
    404: That merchant was not found.

utterances:
  - how much have I spent on lesspay
  - total kitna kharch hua hai
  - "मैंने कुल कितना खर्च किया"
  - what is my total spend
  - kitna paisa diya hai maine lesspay ko
  - show my spend summary
  - mera total kharcha kitna hai
---

One total for what the merchant has spent with LessPay, broken down into
programs, packages and promotions, with any deposit held shown separately.

Same direction as `purchases.list` and the same caution applies: this is money
the shop paid out, not money it took in. The deposit is held rather than spent,
which is why it sits outside the total rather than inside it.

`purchases.list` answers "what did I buy". This answers "how much did it come
to". A merchant who wants both should get this first — the number is the
answer, and the list is the evidence.
