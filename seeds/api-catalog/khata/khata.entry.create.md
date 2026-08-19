---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: khata.entry.create
domain: khata
method: POST
path: /v1/merchant/khata/entries
title: Record udhaar given
mpin_required: false
idempotent: false
version: 1
last_verified: 2026-08-19

fields:
  - name: customer_name
    type: string
    required: true
    prompt: "Whose khata should I add this to?"
    example: Ramesh
  - name: amount
    type: number
    required: true
    prompt: "How much did they take on credit?"
    example: 450
  - name: note
    type: string
    required: false
    prompt: "Anything to note about it?"
    example: 2 kg sugar, 1 kg dal
  - name: entry_date
    type: date
    required: false
    prompt: "Was this today, or another day?"
    default: today

returns:
  success: [entry_id, customer_balance]
  errors:
    422: The amount has to be more than zero.

utterances:
  - ramesh took 500 rupees of goods on credit
  - add udhaar for a customer
  - khata mein likh do 450 rupaye
  - note down that he owes me 200
  - record credit given today
  - customer took saman on udhaar
  - "write 300 in ramesh's account"
---

Records credit given to a customer — goods taken now, money to be paid
later. The amount is added to what that customer owes.

This records money the customer now owes. Money coming back in is
`khata.entry.settle`.
