---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: offers.discount.create
domain: offers
method: POST
path: "/v1/merchant/{merchantId}/mpin-actions"
title: Create a discount
mpin_required: true
idempotent: false
version: 1
last_verified: 2026-08-19
body_root: payload

# Sent on every call, whatever the merchant said. The path alone
# does not identify this action; these values do.
constants:
  purpose: DISCOUNT_CREATE

fields:
  - name: name
    type: string
    required: true
    prompt: "What should the discount be called?"
    example: "Flat 10% Off"
  - name: discountType
    type: enum
    required: true
    prompt: "A percentage off, or a flat amount off?"
    values: [PERCENTAGE, FLAT]
  - name: discountValue
    type: number
    required: true
    prompt: "How much off?"
    example: 10
  - name: maxAmount
    type: number
    required: false
    prompt: "Cap the saving at any amount?"
  - name: rules
    type: object
    required: false
    prompt: "Any minimum bill for it to apply?"
    example: "{\"appliesOn\":\"PAYMENT_AMOUNT\",\"minBillAmount\":500}"
  - name: validity
    type: object
    required: false
    prompt: "Until when should it run?"
  - name: happyHours
    type: object
    required: false
    prompt: "Only during certain hours?"
    example: "{\"startTime\":\"16:00\",\"endTime\":\"19:00\"}"
  - name: appliesOnWeekends
    type: boolean
    required: false
    prompt: "Should the happy hours apply at weekends too?"
  - name: showOnShopProfile
    type: boolean
    required: false
    prompt: "Should it show on your shop profile?"
  - name: redeemLimit
    type: integer
    required: false
    prompt: "How many times can one customer use it?"
  - name: totalRedeemLimit
    type: integer
    required: false
    prompt: "How many customers in total?"
  - name: target
    type: object
    required: false
    prompt: "Everyone, or particular customers?"

returns:
  success: [id, offerKind, discountType, status, validTill]
  errors:
    400: A percentage cannot be over 100, and a flat amount cannot exceed the minimum bill.
    401: That MPIN was not right.

utterances:
  - "start a 20% off sale"
  - flat 100 rupees off above 500
  - "मुझे 20% की छूट देनी है"
  - discount lagana hai
  - 10 percent off during happy hours
  - put my whole shop on discount this weekend
  - give money off on orders above 1000
  - sabko 15 percent kam kar do
---

Creates a discount — an offer that takes money off the bill, either a
percentage or a flat amount. Can carry a minimum bill, a happy-hours window, and
caps on how often it is used.

A discount changes the price. If the customer is getting extra goods instead —
buy one get one, a bundle, a free item — that is `offers.deal.create`. Merchants
call both "offers", so ask which they mean when it is not clear.
