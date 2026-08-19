---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: reports.sales.summary
domain: reports
method: GET
path: /v1/merchant/reports/sales
title: Sales summary
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: period
    type: enum
    required: false
    prompt: "For today, this week, or this month?"
    default: today
    values: [today, week, month, custom]

returns:
  success: [total_sales, order_count, average_order_value, change_percent]

utterances:
  - how much did i sell today
  - aaj ki sale kitni hui
  - show me my sales report
  - what were my earnings this month
  - give me a summary of this week
  - how is my business doing
  - total revenue this month
---

Totals up sales over a period — how much came in, how many orders, the
average order value, and the change against the period before.

This is the money view. Order-by-order detail is `orders.list`.
