---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: customers.create
domain: customers
method: POST
path: /v1/merchant/customers
title: Add a customer
mpin_required: false
idempotent: false
version: 1
last_verified: 2026-08-19

fields:
  - name: name
    type: string
    required: true
    prompt: "What is the customer's name?"
  - name: phone
    type: string
    required: true
    prompt: "What is their phone number?"

returns:
  success: [customer_id]
  errors:
    409: You already have a customer with that phone number.

utterances:
  - add a new customer
  - naya customer add karo
  - "save this person's number"
  - create a customer record for ramesh
  - i want to add someone to my customer list
---

Adds a customer by hand — useful for someone who buys in the shop rather
than through the app, especially before opening a khata for them.
