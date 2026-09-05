---
type: api
status: live
api_id: image.batch
domain: image
method: POST
# Verified against /openapi.json on 2026-09-04, Image Generation Microservice
# 2.3.0.
#
# This is the ONLY endpoint on the service that returns image URLs. The single
# generate endpoints hand back bytes in image_base64; this one hands back
# BatchImageItem entries carrying image_url. Anything that needs a link rather
# than a blob -- bannerImageUrl on an offer, for instance -- comes from here.
base_url: https://lp-image-generation.qa.lesspay.app
path: /v1/generate/batch
title: Render the approved banner at every size
auth: imagegen
mpin_required: false
idempotent: false
working_message: >-
  Banner ko sabhi sizes mein save kar raha hoon.
version: 1
last_verified: 2026-09-04

fields:
  - name: approvedRefinedPrompt
    type: string
    required: true
    prompt: "Which banner was approved?"
    derive: >-
      The refined_prompt from the generate or regenerate response for the image
      the merchant actually chose. Never asked for and never invented.

  # Defaults to all six standard sizes, which is what the app wants after an
  # offer is approved. Overriding it is for retrying the ones that failed.
  - name: sizes
    type: array
    required: false
    prompt: "Which sizes are needed?"
    derive: >-
      Left empty for the standard set. On a retry, exactly the sizes listed
      under `failures` on the previous response and no others.

returns:
  # Partial success is NORMAL here and still returns 200: `images` holds every
  # size that worked and `failures` holds the rest, to be retried by calling
  # again with only those sizes. A 502 means every size failed. Treating a 200
  # as complete success is how a missing size goes unnoticed.
  success: [images, failures, requested_sizes, refined_prompt]
  errors:
    401: I could not sign in to the banner service.
    422: That request was not valid.
    429: The banner service is busy. Try again in a moment.
    502: None of the sizes could be generated.
    503: The banner service is unavailable.
    504: The batch took too long.

utterances:
  - save this banner in all sizes
  - is banner ko sab jagah ke liye taiyar karo
  - "इसी बैनर को सारे साइज़ में बनाओ"
  - render the approved banner everywhere
  - prepare this image for stories too
---

Renders an already-approved banner at every size the app needs, in parallel.

It skips the language model entirely -- the approved prompt is reused as-is --
so there is no refinement cost and the only work is the images themselves. This
normally runs on its own when a merchant confirms an offer rather than because
anyone asked for it, which is why the phrasings above are the only ones that
should ever reach it directly.

Partial success is ordinary. A response with entries under `failures` is still
a 200, and the fix is to call again with just those sizes.
