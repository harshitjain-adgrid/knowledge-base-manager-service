---
type: api
status: live
api_id: image.deal.banner
domain: image
method: POST
# Verified against the service's own OpenAPI document at /openapi.json on
# 2026-09-04. Image Generation Microservice, version 2.3.0.
#
# v1 of this card pointed at http://localhost:8001 and read `image_url` off the
# response. Both were wrong, and both were silent: 8001 is the orchestrator's
# own port now, so the call went to us and 404ed, and `image_url` is null in
# normal operation because the image comes back as bytes. A deal whose banner
# is mandatory then refuses the deal.
base_url: https://lp-image-generation.qa.lesspay.app
path: /v1/generate/deal
title: Deal banner image
# Names a credential; the value lives in the orchestrator's ACTION_AUTH_TOKENS
# under the header X-API-Key. A secret must never appear in a document --
# knowledge base text is readable by anyone with database access and is pasted
# into model prompts.
auth: imagegen
mpin_required: false
# Every call generates a new image and costs money. Never safe to retry blindly.
idempotent: false
# Said as soon as the request goes out, not after it comes back. This call takes
# about thirty seconds, and in a spoken conversation that much silence reads as
# a failure rather than as work in progress.
working_message: >-
  Theek hai, deal ka banner bana raha hoon — thoda time lagega, around half a minute.
version: 2
last_verified: 2026-09-04

# Facts about the shop, filled from the verified identity. The service requires
# shopName, and a merchant must never be asked to dictate their own shop name.
#
# subCategory earns its place: the service's own documentation says it "carries
# far more visual signal than shopCategory, and is the fallback subject when the
# offer names no product of its own". A bundle deal with no items listed is
# drawn from this and nothing else.
from_context:
  shopName: merchant_name
  shopCategory: category
  subCategory: sub_category

fields:
  # The discriminator. The service selects which body shape it is validating
  # from this one value, so a wrong value is a 422 rather than a poor picture.
  #
  # These constants are NOT the ones the offers API uses. offers.deal.create
  # writes BOGO, BUNDLE_DEAL and FREE_ITEM; this service writes BUY_X_GET_Y,
  # BUNDLE_COMBO and FREE_ITEM. Only the last one is spelled the same. The
  # mapping is stated in `derive` because the two vocabularies describe the same
  # three offers and nothing in either document says so on its own.
  - name: dealType
    type: enum
    required: true
    prompt: "Is it buy-one-get-one, a bundle, or a free item on a minimum bill?"
    values:
      - value: BUY_X_GET_Y
        means: >-
          Buy a quantity of something, get a quantity free or discounted. This
          is what offers.deal.create calls BOGO.
      - value: BUNDLE_COMBO
        means: >-
          A fixed number of items at one fixed price. This is what
          offers.deal.create calls BUNDLE_DEAL.
      - value: FREE_ITEM
        means: >-
          A free item unlocked by a minimum bill value. Spelled the same in
          offers.deal.create.
    derive: >-
      From the deal's offerType: BOGO becomes BUY_X_GET_Y, BUNDLE_DEAL becomes
      BUNDLE_COMBO, FREE_ITEM stays FREE_ITEM.

  - name: title
    type: string
    required: true
    prompt: "What should the banner say?"
    example: "Buy 1 Get 1 Free"
    derive: "The deal's own title, rendered close to verbatim on the image."

  # BUY_X_GET_Y only.
  - name: buyQty
    type: integer
    required: true
    required_when: {dealType: [BUY_X_GET_Y]}
    prompt: "How many does the customer buy?"
    example: 1
  - name: getQty
    type: integer
    required: true
    required_when: {dealType: [BUY_X_GET_Y]}
    prompt: "And how many do they get free?"
    example: 1
  - name: buyItemName
    type: string
    required: true
    required_when: {dealType: [BUY_X_GET_Y]}
    prompt: "Which product do they have to buy?"
    example: Coffee
  - name: bogoFreeItemName
    type: string
    required: true
    required_when: {dealType: [BUY_X_GET_Y]}
    prompt: "And which product is free?"
    example: Croissant
    derive: >-
      Equals buyItemName when the free product is the same one that was bought,
      which is the SAME_ITEM case.
  - name: applyOn
    type: enum
    required: false
    required_when: {dealType: [BUY_X_GET_Y]}
    prompt: "Same item, or any item?"
    values:
      - value: SAME_ITEM
        means: The free product is the one that was bought.
      - value: ANY_ITEM
        means: The free product is a different one.

  # BUNDLE_COMBO only.
  - name: bundleSize
    type: integer
    required: true
    required_when: {dealType: [BUNDLE_COMBO]}
    prompt: "How many items in the bundle?"
    example: 3
  - name: bundlePrice
    type: number
    required: true
    required_when: {dealType: [BUNDLE_COMBO]}
    prompt: "What is the bundle price?"
    example: 150
  - name: bundleItems
    type: string
    required: false
    required_when: {dealType: [BUNDLE_COMBO]}
    prompt: "What is in the bundle?"
    example: "Burger, Fries, Coke"
    derive: >-
      Comma-separated. When absent the service falls back to the shop's
      subCategory for the subject of the picture.

  # FREE_ITEM only.
  - name: freeItemName
    type: string
    required: true
    required_when: {dealType: [FREE_ITEM]}
    prompt: "Which item is free?"
    example: Gulab jamun
  - name: onBillsAbove
    type: number
    required: true
    required_when: {dealType: [FREE_ITEM]}
    prompt: "Above what bill amount?"
    example: 500

  # Optional on purpose. Picked up when the merchant volunteers a look ("Holi
  # theme", "show the lime soda") and never asked for when they do not -- an
  # extra question before an image appears is a worse trade than a plainer
  # image.
  - name: merchantPrompt
    type: string
    required: false
    prompt: "Any particular look you want?"
    example: "Holi theme"

  - name: imageSize
    type: enum
    required: false
    default: "16:9"
    prompt: "What shape should the banner be?"
    values: ["1:1", "4:3", "3:4", "16:9", "9:16", "4:5", "3:5", "9:18", "18:9", "20:9"]

returns:
  # The image arrives as BYTES in image_base64, with content_type naming the
  # media type. image_url is null in normal operation and populated only when
  # the provider hands back a link instead -- exactly one of the two is set.
  #
  # refined_prompt is the other thing worth keeping. It is what image.regenerate
  # and image.batch are called with, so a response thrown away after the picture
  # is shown cannot be varied or re-rendered at other sizes later.
  #
  # image_source says whether this is real artwork or the locally drawn fallback
  # banner used when generation failed. A fallback is still a usable picture and
  # still a 200, so it is worth recording rather than treating as success.
  success: [image_base64, content_type, refined_prompt, image_source, seed]
  errors:
    401: I could not sign in to the banner service.
    # 422 carries TWO different shapes and they are told apart by `code`, never
    # by the status. content_rejected is a decision, not a failure: the service
    # worked and declined. Never retry it; the `reason` field is written to be
    # shown to the merchant as-is.
    422: That did not pass the content check. The reason field says why, in words meant for the merchant.
    429: The banner service is busy. Try again in a moment.
    502: The banner service could not produce an image just now.
    503: The banner service is unavailable.
    504: The banner took too long to generate.

# Every one of these carries a picture word -- banner, poster, image, photo,
# banao. That is deliberate: offers.deal.create already owns the plain "make me
# a deal" phrasings, and a card that competed with it for those would take
# turns that were never about a picture at all.
utterances:
  - make a banner for my deal
  - deal ka poster banao
  - "बैनर बनाओ"
  - generate an image for this offer
  - offer ki photo bana do
  - create a picture for my bogo
  - banner chahiye is deal ka
---

Draws a promotional banner for a deal, from the offer's own details.

The service refines the description with a language model first and then
generates the image, which is why one call takes around thirty seconds and why
the refined prompt it returns is worth keeping: `image.regenerate` reuses it to
produce a variation without paying for refinement again, and `image.batch`
reuses it to render the approved picture at every size the app needs.

The picture comes back as bytes, not as a link.
