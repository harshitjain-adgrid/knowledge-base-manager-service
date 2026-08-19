---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: catalog.product.list
domain: catalog
method: GET
path: /v1/merchant/catalog/products
title: See my products
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: category
    type: string
    required: false
    prompt: "Any particular category, or everything?"
  - name: in_stock_only
    type: boolean
    required: false
    prompt: "Only the items you still have in stock?"
    default: false

returns:
  success: [products, total]

utterances:
  - what products do i have
  - show me my catalogue
  - list everything in my shop
  - mere saare products dikhao
  - what am i selling right now
  - show my items and prices
  - which products are out of stock
---

Lists what is in the shop's catalogue, newest first, with prices and
stock levels. Can be narrowed to one category or to items that are out of stock.

This is about products. To see what customers have ordered, use `orders.list`.
