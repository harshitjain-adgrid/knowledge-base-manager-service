---
type: api
status: live
api_id: image.discount.banner
domain: image
method: POST
# Verified against /openapi.json on 2026-09-04, Image Generation Microservice
# 2.3.0. Same service and same credential as image.deal.banner, different
# endpoint and a different discriminator.
base_url: https://lp-image-generation.qa.lesspay.app
path: /v1/generate/discount
title: Discount banner image
auth: imagegen
mpin_required: false
idempotent: false
working_message: >-
  Theek hai, discount ka banner bana raha hoon — thoda time lagega, around half a minute.
version: 1
last_verified: 2026-09-04

from_context:
  shopName: merchant_name
  shopCategory: category
  subCategory: sub_category

fields:
  # Spelled the same as offers.discount.create's discountType, and carrying the
  # same two values -- unlike the deal side, where the two services disagree on
  # every constant. Worth stating plainly because the deal card's mapping note
  # invites the assumption that a mapping is needed here too. It is not.
  - name: valueType
    type: enum
    required: true
    prompt: "Percentage off, or a flat rupee amount?"
    values:
      - value: PERCENTAGE
        means: >-
          A share of the bill. discountValue is a percentage, 0 to 100. Matches
          offers.discount.create's PERCENTAGE exactly.
      - value: FLAT
        means: >-
          A fixed rupee amount off. discountValue is that amount. Matches
          offers.discount.create's FLAT exactly.
    derive: "The discount's own discountType, copied unchanged."

  # `name`, not `title`. The discount API calls its headline `name` and so does
  # this endpoint, while the deal endpoint calls the same thing `title`.
  - name: name
    type: string
    required: true
    prompt: "What should the banner say?"
    example: "Every 3rd Payment 10% Off"
    derive: "The discount's own name, rendered close to verbatim on the image."

  - name: discountValue
    type: number
    required: true
    prompt: "How much off?"
    example: 20
    derive: >-
      The discount's own discountValue. The service caps this at 100 for
      PERCENTAGE, because a banner promising more than the whole bill cannot be
      honoured.

  - name: merchantPrompt
    type: string
    required: false
    prompt: "Any particular look you want?"
    example: "Diwali theme"

  - name: imageSize
    type: enum
    required: false
    default: "16:9"
    prompt: "What shape should the banner be?"
    values: ["1:1", "4:3", "3:4", "16:9", "9:16", "4:5", "3:5", "9:18", "18:9", "20:9"]

returns:
  success: [image_base64, content_type, refined_prompt, image_source, seed]
  errors:
    401: I could not sign in to the banner service.
    422: That did not pass the content check. The reason field says why, in words meant for the merchant.
    429: The banner service is busy. Try again in a moment.
    502: The banner service could not produce an image just now.
    503: The banner service is unavailable.
    504: The banner took too long to generate.

utterances:
  - make a banner for my discount
  - discount ka poster banao
  - "छूट का बैनर बनाओ"
  - generate an image for this discount
  - "discount ki photo bana do"
  - create a picture for my percentage off
---

Draws a promotional banner for a discount.

Same service as `image.deal.banner` and the same thirty-second shape, but it
takes a discount rather than a deal: a value and how that value is read, with
no items involved. The picture comes back as bytes, and the refined prompt it
returns is what `image.regenerate` and `image.batch` are called with.
