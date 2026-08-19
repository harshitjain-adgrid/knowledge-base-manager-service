---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: catalog.product.update
domain: catalog
method: PATCH
path: "/v1/merchant/catalog/products/{product_id}"
title: Change a product
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: product_id
    type: string
    required: true
    prompt: "Which product should I change?"
    example: prd_8812
  - name: price
    type: number
    required: false
    prompt: "What should the new price be?"
  - name: name
    type: string
    required: false
    prompt: "What should it be called now?"

returns:
  success: [product_id, updated_fields]
  errors:
    404: I could not find that product in your catalogue.

utterances:
  - change the price of amul butter
  - update my product price
  - maggi ka rate badal do
  - make the butter 270 instead
  - i want to rename a product
  - edit an item in my shop
  - increase price of rice to 60
---

Changes the details of a product that is already in the catalogue —
its name, price, unit or category. Only the fields you send are changed.

Use this for a price change. Adding something new is `catalog.product.create`,
and changing only the quantity in stock is `catalog.stock.update`.
