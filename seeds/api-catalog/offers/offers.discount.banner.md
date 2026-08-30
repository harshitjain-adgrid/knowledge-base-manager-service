---
type: api
status: live
api_id: offers.discount.banner
domain: offers
method: POST
# The image generation service, called directly. In production this call goes
# through the merchant BFF and lp-open, which add S3 upload on top; that path
# needs an environment where it can be exercised end to end, which does not
# exist yet. Repointing this card is the only change when it does.
base_url: http://localhost:8001
path: /v1/generate/discount
title: Discount banner image
# Names a credential; the value lives in the orchestrator's ACTION_AUTH_TOKENS.
# A secret must never appear in a document -- knowledge base text is readable
# by anyone with database access and is pasted into model prompts.
auth: imagegen
mpin_required: false
# Every call generates a new image and costs money. Never safe to retry blindly.
idempotent: false
# Said as soon as the request goes out, not after it comes back. This
# call takes about thirty seconds, and in a spoken conversation that
# much silence reads as a failure rather than as work in progress.
# Only delivered on /v1/chat/stream; /v1/chat has nowhere to put it.
working_message: >-
  Theek hai, discount ka banner bana raha hoon — thoda time lagega, around half a minute.
version: 1
last_verified: 2026-08-26

# Facts about the shop, filled from the verified identity. The service requires
# merchant_name, but a merchant must never be asked to dictate their own shop
# name -- we already know it, and asking would read as the assistant not
# knowing who it is talking to.
from_context:
  merchant_name: merchant_name
  category: category

fields:
  - name: discount_type
    type: enum
    required: true
    prompt: "Is it a percentage off, or a flat rupee amount?"
    values: [PERCENTAGE, FLAT_AMOUNT]
    example: PERCENTAGE
  - name: discount_value
    type: number
    required: true
    prompt: "How much off?"
    example: 20
  # Optional on purpose. Picked up when the merchant volunteers a look
  # ("Diwali theme", "show Samsung phones") and never asked for when they do
  # not -- an extra question before an image appears is a worse trade than a
  # plainer image.
  - name: merchant_prompt
    type: string
    required: false
    prompt: "Any particular look you want?"
    example: "Diwali theme"

returns:
  success: [image_url]
  errors:
    401: I could not sign in to the banner service.
    422: That did not pass the content check. Try describing it differently.
    429: The banner service is busy. Try again in a moment.
    502: The banner service could not produce an image just now.
    504: The banner took too long to generate.

# Every one of these carries a picture word -- banner, poster, image, photo,
# banao. That is deliberate. `offers.discount.create` already owns the plain
# phrasings ("discount lagana hai"), and without a picture word retrieval
# prefers it, which is correct: a merchant who says "give 20% off" wants the
# offer created, not a picture of one.
utterances:
  - "20% off ka banner banado"
  - make a poster for my discount
  - discount wali image banao
  - "मुझे 10% छूट का बैनर चाहिए"
  - flat 200 off ka poster bana do
  - design a banner for money off
  - offer ki photo banao jisme percent off likha ho
  - create a discount banner for my shop
---

Generates a promotional banner image for a discount -- an offer that takes money
off the bill, either a percentage or a flat rupee amount. The shop's name and
category come from the merchant's own account, so they are never asked for. The
finished image comes back as a link for the app to show.

This only draws a picture. It does not create the offer: nothing here changes
what a customer is actually charged. Creating the real discount is
`offers.discount.create`.

If the customer is getting extra goods rather than money off -- buy one get one,
a combo, a bundle -- the banner for that is `offers.deal.banner`. Merchants call
both "offer", so ask which they mean when it is not clear.
