---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: payments.transaction.list
domain: payments
method: GET
path: /v1/merchant/payments/transactions
title: See customer payments
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: status
    type: enum
    required: false
    prompt: "All of them, or only the failed ones?"
    values: [success, failed, pending]
  - name: from_date
    type: date
    required: false
    prompt: "From which date?"

returns:
  success: [transactions, total]

utterances:
  - show me all payments received
  - which payments failed
  - how much did customers pay today
  - payment history dikhao
  - list transactions from this week
  - kitna online payment aaya
---

Lists individual payments customers have made, with the mode and whether
each one succeeded.

These are payments coming in. Money reaching the bank account is
`payments.settlement.list`.
