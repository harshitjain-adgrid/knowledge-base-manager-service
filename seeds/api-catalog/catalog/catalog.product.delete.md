---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: catalog.product.delete
domain: catalog
method: DELETE
path: "/v1/merchant/catalog/products/{product_id}"
title: Remove a product
mpin_required: true
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: product_id
    type: string
    required: true
    prompt: "Which product should I remove?"

returns:
  success: [product_id, deleted]
  errors:
    404: I could not find that product.
    409: That product is in an order that is still open.

utterances:
  - delete a product
  - remove maggi from my shop
  - "i don't sell this anymore, take it off"
  - product hata do
  - stop showing this item to customers permanently
  - delete an item from my catalogue
---

Takes a product off the shop permanently. Past orders that contain it
are not affected.

If the item is only temporarily unavailable, set its stock to zero with
`catalog.stock.update` instead — deleting loses the product's history.
