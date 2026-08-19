---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: offers.deal.create
domain: offers
method: POST
path: "/v1/merchant/{merchantId}/mpin-actions"
title: Create a deal
mpin_required: true
idempotent: false
version: 1
last_verified: 2026-08-19
body_root: payload

# Sent on every call, whatever the merchant said. The path alone
# does not identify this action; these values do.
constants:
  purpose: DEAL_CREATE

fields:
  - name: title
    type: string
    required: true
    prompt: "What should the deal be called?"
    example: Buy 1 Get 1 Coffee
  - name: offerType
    type: enum
    required: true
    prompt: "Is it buy-one-get-one, a bundle, or a free item?"
    values: [BOGO, BUNDLE_DEAL, FREE_ITEM]
  - name: config
    type: object
    required: true
    prompt: "Which item, and how many?"
    example: "{\"appliesOn\":\"SAME_ITEM\",\"buyItemName\":\"Cappuccino\",\"buyQty\":1,\"getQty\":1}"
  - name: showOnShopProfile
    type: boolean
    required: true
    prompt: "Should it show on your shop profile?"
  - name: description
    type: string
    required: false
    prompt: "Anything to add about it?"
  - name: validity
    type: object
    required: false
    prompt: "Until when should it run?"
    example: "{\"isLimited\":true,\"endDate\":\"2026-08-31T23:59:59Z\"}"
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
  success: [id, offerKind, offerType, status, validTill]
  errors:
    400: Something in the deal was not valid — check the item name and quantities.
    401: That MPIN was not right.

utterances:
  - buy one get one free on coffee
  - start a bogo offer
  - ek ke saath ek free karna hai
  - free dessert on bills above 500
  - make a combo deal on my items
  - bundle two items together at one price
  - give a free item with every order over 300
  - BOGO offer chalu karo
---

Creates a deal — an offer where the customer gets extra goods rather
than money off. Buy one get one, a bundle at a set price, or a free item over a
bill threshold.

A deal changes what the customer receives. If the customer is getting money off
instead — a percentage or a flat amount — that is `offers.discount.create`.
Merchants call both of these "offers", so ask which they mean when it is not
clear from the numbers they gave.
