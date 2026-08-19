---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: catalog.stock.update
domain: catalog
method: PUT
path: "/v1/merchant/catalog/products/{product_id}/stock"
title: Update stock
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: product_id
    type: string
    required: true
    prompt: "Which product?"
  - name: quantity
    type: integer
    required: true
    prompt: "How many are left?"
    example: 24

returns:
  success: [product_id, stock_quantity]
  errors:
    404: I could not find that product.

utterances:
  - update my stock
  - i have 20 packets left
  - mark this out of stock
  - stock khatam ho gaya
  - restock the butter, 50 more came in
  - set quantity to 12
  - this item is finished
---

Sets how many units of a product are left. Setting it to zero marks
the item out of stock, so customers can still see it but cannot order it.

This changes quantity only. To change the price, use `catalog.product.update`.
