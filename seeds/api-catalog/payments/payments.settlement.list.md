---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: payments.settlement.list
domain: payments
method: GET
path: /v1/merchant/payments/settlements
title: See my settlements
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: from_date
    type: date
    required: false
    prompt: "From which date?"

returns:
  success: [settlements, total_settled]

utterances:
  - when will i get my money
  - show my settlements
  - bank mein paise kab aayenge
  - how much has been paid out to me
  - list my payouts
  - settlement history dikhao
---

Lists the payouts that have landed in the merchant's bank account, with
what each one covers and any fees deducted.

This is money already sent to the bank. Individual customer payments are
`payments.transaction.list`.
