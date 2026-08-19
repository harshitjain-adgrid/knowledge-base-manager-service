---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: catalog.product.create
domain: catalog
method: POST
path: /v1/merchant/catalog/products
title: Add a product
mpin_required: false
idempotent: false
version: 1
last_verified: 2026-08-19

fields:
  - name: name
    type: string
    required: true
    prompt: "What is the product called?"
    example: Amul Butter 500g
    max_length: 80
  - name: price
    type: number
    required: true
    prompt: "What price should I put on it?"
    example: 265
  - name: unit
    type: enum
    required: false
    prompt: "Is that per piece, per kilo, or something else?"
    default: piece
    values: [piece, kg, litre, packet, dozen]
  - name: stock_quantity
    type: integer
    required: false
    prompt: "How many do you have in stock?"
    default: 0
  - name: category
    type: string
    required: false
    prompt: "Which category does it belong in?"
    example: Dairy

returns:
  success: [product_id, status]
  errors:
    409: A product with that name already exists in your catalogue.
    422: The price has to be greater than zero.

utterances:
  - add a new product
  - मुझे नया प्रोडक्ट जोड़ना है
  - put amul butter in my shop for 265
  - i want to list a new item
  - add maggi 12 rupees to my catalogue
  - naya item add karna hai
  - create a product listing
  - i started selling a new thing, add it
---

Adds a new product to the shop's catalogue so customers can see and
order it. The product goes live immediately unless it is saved as a draft.

Not for changing something that already exists — that is `catalog.product.update`
— and not for restocking, which is `catalog.stock.update`.
