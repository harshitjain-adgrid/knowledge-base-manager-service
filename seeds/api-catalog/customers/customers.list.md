---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: customers.list
domain: customers
method: GET
path: /v1/merchant/customers
title: See my customers
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: sort_by
    type: enum
    required: false
    prompt: "Sorted by most recent, or by how much they spend?"
    default: recent
    values: [recent, total_spent, order_count]

returns:
  success: [customers, total]

utterances:
  - show me my customers
  - who buys from my shop
  - mere customers ki list
  - list all my buyers
  - who are my regular customers
  - how many customers do i have
---

Lists the people who buy from the shop, with how much each has spent and
when they last ordered.

This is who they are. What they owe on credit is `khata.customer.list`.
