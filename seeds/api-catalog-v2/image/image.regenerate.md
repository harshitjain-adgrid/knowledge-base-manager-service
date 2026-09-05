---
type: api
status: live
api_id: image.regenerate
domain: image
method: POST
# Verified against /openapi.json on 2026-09-04, Image Generation Microservice
# 2.3.0. This is the endpoint behind the app's "Regenerate banner" button.
base_url: https://lp-image-generation.qa.lesspay.app
path: /v1/generate/regenerate
title: Try a different banner
auth: imagegen
mpin_required: false
# A new image every time, by design -- that is the point of the button.
idempotent: false
working_message: >-
  Doosra banner bana raha hoon, ek minute.
version: 1
last_verified: 2026-09-04

fields:
  # Not a question. This value comes off the previous generate response and
  # nothing a merchant says can produce it, which is why the prompt below would
  # be a dead end if it were ever reached -- and why the card carries the value
  # forward from session state instead.
  #
  # It is also the whole reason this endpoint is cheap: sending the already
  # refined prompt skips the language model entirely, so a regeneration costs
  # only the image and none of the refinement.
  - name: previousRefinedPrompt
    type: string
    required: true
    prompt: "Which banner should I vary?"
    derive: >-
      The refined_prompt field from the image.deal.banner or
      image.discount.banner response that produced the picture the merchant is
      looking at. Never asked for and never invented.

  - name: imageSize
    type: enum
    required: false
    default: "16:9"
    prompt: "What shape should it be?"
    values: ["1:1", "4:3", "3:4", "16:9", "9:16", "4:5", "3:5", "9:18", "18:9", "20:9"]

  # Omit it to get a genuinely different variation. Supplying one reproduces a
  # picture that was seen before, which is what makes "go back to the second
  # one" answerable -- the seed actually used comes back on every response.
  - name: seed
    type: integer
    required: false
    prompt: "Should I reproduce a particular one?"
    derive: >-
      Left empty for a new variation, which is the normal case. Set only to
      reproduce an image the merchant already saw, using the seed recorded on
      that response.

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
  - make another banner
  - dusra banner dikhao
  - "यह बैनर पसंद नहीं आया, दूसरा बनाओ"
  - regenerate the image
  - try a different picture
  - ye wala nahi, koi aur banao
  - show me another option
  - change the banner
---

Produces a different banner for an offer whose banner has already been drawn.

It reuses the refined prompt from the first call, so the language model does
not run again: the result is a visually distinct variation of the same idea, at
a fraction of the cost and time of generating from scratch. This is what should
run when a merchant does not like what they were shown -- not another full
generate.

The merchant is never asked for the previous prompt. If it is not in session
state there is nothing to vary, and the honest move is a fresh generate rather
than a question no one can answer.
