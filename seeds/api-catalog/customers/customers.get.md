---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: customers.get
domain: customers
method: GET
path: "/v1/merchant/customers/{customer_id}"
title: See one customer
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: customer_id
    type: string
    required: true
    prompt: "Which customer?"

returns:
  success: [customer]
  errors:
    404: I could not find that customer.

utterances:
  - tell me about this customer
  - "show ramesh's details"
  - customer ka profile dikhao
  - what does this person usually order
  - "open a customer's history"
---

Shows one customer — their contact details, order history and what they
usually buy.
