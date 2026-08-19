---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: khata.customer.list
domain: khata
method: GET
path: /v1/merchant/khata/customers
title: See all khata balances
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: overdue_days
    type: integer
    required: false
    prompt: "Only the ones overdue past a certain number of days?"

returns:
  success: [customers, total_outstanding]

utterances:
  - how much money is owed to me in total
  - show all khata accounts
  - kis kis ka udhaar baaki hai
  - list everyone who owes me money
  - total outstanding on my khata
  - who has not paid me in 30 days
---

Lists every customer with an open khata and what each one owes, largest
first. Optionally only those overdue past a number of days.

This is the whole ledger. For one person, use `khata.balance.get`.
