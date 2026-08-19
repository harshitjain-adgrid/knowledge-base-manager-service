---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: khata.balance.get
domain: khata
method: GET
path: "/v1/merchant/khata/customers/{customer_id}/balance"
title: Check what a customer owes
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: customer_id
    type: string
    required: true
    prompt: "Whose balance do you want to see?"

returns:
  success: [customer_id, balance, entries]
  errors:
    404: I do not have a khata for that customer.

utterances:
  - how much does ramesh owe me
  - "check a customer's khata balance"
  - ramesh ka kitna baaki hai
  - what is pending from this customer
  - show me his account
  - how much udhaar is left on suresh
---

Shows how much one customer currently owes, with the entries that make
up the total.

For everyone at once, use `khata.customer.list`.
