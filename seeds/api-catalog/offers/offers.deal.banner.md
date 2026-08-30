---
type: api
status: live
api_id: offers.deal.banner
domain: offers
method: POST
# The image generation service, called directly. In production this call goes
# through the merchant BFF and lp-open, which add S3 upload on top; that path
# needs an environment where it can be exercised end to end, which does not
# exist yet. Repointing this card is the only change when it does.
base_url: http://localhost:8001
path: /v1/generate/deal
title: Deal banner image
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
  Theek hai, deal ka banner bana raha hoon — thoda time lagega, around half a minute.
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
  - name: title
    type: string
    required: true
    prompt: "What should the banner say?"
    example: "Buy 1 Get 1 Free"
  - name: offer_type
    type: enum
    required: false
    prompt: "Is it buy-one-get-one, a combo, or a bundle?"
    values: [BOGO, COMBO, BUNDLE]
    example: BOGO
  # Optional on purpose. Picked up when the merchant volunteers a look ("Holi
  # theme", "show the lime soda") and never asked for when they do not -- an
  # extra question before an image appears is a worse trade than a plainer
  # image.
  - name: merchant_prompt
    type: string
    required: false
    prompt: "Any particular look you want?"
    example: "Holi theme"

returns:
  success: [image_url]
  errors:
    401: I could not sign in to the banner service.
    422: That did not pass the content check. Try describing it differently.
    429: The banner service is busy. Try again in a moment.
    502: The banner service could not produce an image just now.
    504: The banner took too long to generate.

# Every one of these carries a picture word -- banner, poster, image, photo,
# banao. That is deliberate. `offers.deal.create` already owns the plain
# phrasings, and without a picture word retrieval prefers it, which is correct:
# a merchant who says "start a BOGO" wants the offer created, not a picture.
utterances:
  - "BOGO ka banner banado"
  - make a poster for buy one get one
  - combo offer ki image banao
  - "एक पर एक फ्री का बैनर बनाओ"
  - design a banner for my bundle deal
  - free item wala poster bana do
  - create a deal banner for my shop
  - buy 2 get 1 ka photo banao
---

Generates a promotional banner image for a deal -- an offer where the customer
gets extra goods rather than money off: buy one get one, a combo, a bundle, a
free item. The shop's name and category come from the merchant's own account, so
they are never asked for. The finished image comes back as a link for the app to
show.

This only draws a picture. It does not create the offer: nothing here changes
what a customer actually receives. Creating the real deal is
`offers.deal.create`.

If the customer is getting money off the bill rather than extra goods -- a
percentage, a flat amount -- the banner for that is `offers.discount.banner`.
Merchants call both "offer", so ask which they mean when it is not clear.
