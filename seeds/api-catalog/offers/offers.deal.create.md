---
type: api
status: live
api_id: offers.deal.create
domain: offers
method: POST
# The QA admin endpoint the backend team handed over, verified against its own
# OpenAPI spec at /v3/api-docs on 2026-08-30. That spec's summary for this route
# reads "Create a deal (admin; no MPIN, supports DRAFT)" — it is an ops seeding
# route, not the merchant path.
#
# The merchant path exists: POST /v1/merchant/{id}/mpin-actions, with
# purpose: DEAL_CREATE, deviceId as a query parameter, and the deal body under
# `payload`. Moving to it changes this card's base_url, path, constants and
# mpin_required, and nothing else — the fields, prompts and utterances below are
# the same either way. That is the point of keeping them here.
base_url: https://open.qa.lesspay.app
# merchantId is a QUERY parameter on this endpoint rather than a path segment,
# but it is written into the path template so placeholder substitution fills it
# from the verified identity. A merchant id must never be collected from a
# conversation; reject_identity_fields refuses one if a model produces it.
path: "/v1/admin/offers/deals?merchantId={merchantId}"
title: Create a deal
# FALSE on purpose, and only while testing. The admin endpoint genuinely does
# not check an MPIN, so claiming otherwise here would be a lie the executor
# acts on. When this card moves to the mpin-actions path this becomes true, and
# ACTION_ALLOW_WRITES has to be switched on before it will run at all.
mpin_required: false
# Every call creates a real offer on a real merchant. Never safe to retry blindly.
idempotent: false
version: 2
last_verified: 2026-08-30

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

  # `config` is one object in the request, but it is asked for as separate
  # questions. Slot extraction types every field as a scalar, so a field of
  # type object comes back as a JSON string that the API rejects — and "give me
  # the config object" is not a question a shopkeeper can answer. The dotted
  # names are rebuilt into { "config": { ... } } at request time.
  #
  # Which of these the API demands depends on offerType, and it says which one
  # is missing in plain words, so the ones that do not apply are simply never
  # sent.
  - name: config.appliesOn
    type: enum
    required: true
    prompt: "Is the free item the same thing they bought, or anything in the shop?"
    values: [SAME_ITEM, ANY_ITEM]
  - name: config.buyItemName
    type: string
    required: true
    prompt: "Which item do they have to buy?"
    example: Coffee
  - name: config.buyQty
    type: integer
    required: true
    prompt: "How many do they buy?"
    example: 1
  - name: config.getQty
    type: integer
    required: true
    prompt: "How many do they get free?"
    example: 1
  - name: config.freeItemName
    type: string
    required: false
    prompt: "Which item is free?"
    example: Gulab Jamun
  - name: config.onBillsAbove
    type: integer
    required: false
    prompt: "Above what bill amount does the free item apply?"
    example: 500
  - name: config.bundleSize
    type: integer
    required: false
    prompt: "How many items are in the bundle?"
    example: 3
  - name: config.bundlePrice
    type: integer
    required: false
    prompt: "What is the price for the whole bundle?"
    example: 150

  # NOT required, and deliberately never asked for. "What is the URL of your
  # banner image?" is not a question a shopkeeper can answer. It is produced
  # instead — see `enrich` below — and a merchant who volunteers a URL of their
  # own still wins, because enrich skips a field that already has a value.
  - name: bannerImageUrl
    type: string
    required: false
    prompt: "Do you already have a banner image for it?"
    example: "https://v3.fal.media/files/example/banner.png"

  # The next three are required by the API and answered by default rather than
  # asked. A merchant who says "harpic pe bogo lagado" has told us what the
  # offer IS; being asked three more questions before anything happens is how a
  # working extraction still feels broken. Each default is the answer almost
  # everyone would give, and a merchant who wants otherwise says so and is
  # heard — the default only fills a gap.
  - name: showOnShopProfile
    type: boolean
    required: true
    default: true
    prompt: "Should it show on your shop profile?"
  # The API rejects a deal with no target even though its spec marks the field
  # optional — it fails parsing an empty enum rather than saying so. Only
  # audience targeting is offered here; targeting one named customer needs a
  # customer id, which is a lookup this card does not do. So there is nothing
  # to choose between, and nothing worth asking.
  - name: target.targetType
    type: enum
    required: true
    default: AUDIENCE
    prompt: "Should this go to a group of customers, or one particular person?"
    values: [AUDIENCE]
    example: AUDIENCE
  # Everyone, unless they say otherwise. It is the broadest and least
  # surprising reading of "make an offer", and narrowing it silently would be
  # the damaging mistake — an offer nobody can see looks like a broken offer.
  - name: target.audience
    type: enum
    required: true
    default: ALL_CUSTOMERS
    prompt: "Everyone, new customers, regulars, or people who stopped coming?"
    values: [ALL_CUSTOMERS, NEW_CUSTOMERS, LOYAL_CUSTOMERS, LAPSED_CUSTOMERS]

  - name: description
    type: string
    required: false
    prompt: "Anything to add about it?"
  # Never asked. Picked up only when the merchant volunteers a look — "Holi
  # theme", "green background" — and carried into the banner alongside the item
  # names. An extra question before a picture appears is a worse trade than a
  # plainer picture.
  - name: merchant_prompt
    type: string
    required: false
    prompt: "Any particular look you want for the picture?"
    example: "Holi theme"
  - name: redeemLimit
    type: integer
    required: false
    prompt: "How many times can one customer use it?"
  - name: totalRedeemLimit
    type: integer
    required: false
    prompt: "How many customers in total?"
  - name: validity.isLimited
    type: boolean
    required: false
    prompt: "Should it run for a fixed period, or until you switch it off?"

# The banner is generated once the deal is otherwise complete, and never
# before. Generating one costs money and takes about thirty seconds, so it is
# not worth spending on a deal that turns out to be missing its quantities —
# and there is nothing to draw until the offer is actually decided.
#
# Order: collect every required field, then call offers.deal.banner, then send
# the returned image_url as bannerImageUrl on the create call.
#
# The image is REQUIRED. If the banner cannot be produced, the deal is not
# created either — the merchant is told and nothing is written. An offer is
# public the moment it exists, so shipping one with a blank image and leaving
# someone to notice later is the worse failure.
enrich:
  api_id: offers.deal.banner
  provides: bannerImageUrl
  from: image_url
  carry:
    title: title
    offer_type: offerType
    # The banner service takes ONE line of creative direction, while a deal
    # knows the item bought and the item given away as separate fields. Mapping
    # them one-to-one is not possible, so they are composed into that line.
    #
    # Without this the picture is drawn from the title alone, and a title is
    # about the offer's shape rather than its contents: "ek pe do free"
    # produced a banner with no olive oil and no sieve in it, which is the
    # whole reason a merchant wants a picture.
    #
    # Deliberately values only, with no prose around them. Which placeholders
    # resolve depends on the offer — a same-item BOGO has no free item, a
    # bundle has neither — and any literal wording left behind by an empty one
    # reads as an instruction in its own right: "show the products" with
    # nothing after it is worse creative direction than saying nothing. Bare
    # values degrade to an empty string, and an empty carry entry is dropped.
    merchant_prompt: "{merchant_prompt} {config.buyItemName} {config.freeItemName}"

returns:
  success: [id, status, offerType, displaySubtitle, showOnShopProfile]
  errors:
    # The API's own codes: 17004 is a missing required field and names it, 17006
    # is a value it could not accept and says which and why, in readable
    # English — "config.bundlePrice required and > 0".
    400: Something in the deal was not accepted — the message says which field.
    404: That merchant was not found.

utterances:
  - buy one get one free on coffee
  - start a bogo offer
  - ek ke saath ek free
  - "एक के साथ एक फ्री वाला ऑफर बनाओ"
  - make a combo deal on my items
  - bundle two items together at one price
  - give a free item with every order over 300
  - "BOGO offer chalu karo"
  - deal banana hai
  - "डील बनानी है"
---

Creates a deal — an offer where the customer gets extra goods rather than money
off. Buy one get one, a bundle at a set price, or a free item over a bill
amount.

A deal changes what the customer receives. If they are getting money off
instead — a percentage or a flat amount — that is `offers.discount.create`.
Merchants call both of these "offers", so ask which they mean when it is not
clear from the numbers they gave.

The banner picture is `offers.deal.banner`, which returns an image URL, and that
URL is what `bannerImageUrl` wants here. Drawing a banner creates nothing; this
call is the one that puts a real offer on the merchant's shop.
