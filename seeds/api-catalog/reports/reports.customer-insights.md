---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: reports.customer-insights
domain: reports
method: GET
path: /v1/merchant/reports/customers
title: Customer insights
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: period
    type: enum
    required: false
    prompt: "Over what period?"
    default: month
    values: [month, quarter, year]

returns:
  success: [new_customers, returning_customers, top_spenders, lapsed]

utterances:
  - how many new customers did i get
  - which customers spend the most
  - who has stopped buying from me
  - customer insights dikhao
  - am i getting repeat customers
  - show me customer trends
---

Shows patterns across customers — new against returning, who spends most,
and who has stopped coming back.

This is the analysis. The plain list of customers is `customers.list`.
