---
type: api
status: live
api_id: offers.discount.create
domain: offers
method: POST
# Verified against the QA OpenAPI spec at /v3/api-docs on 2026-09-04. That
# spec's summary for this route reads "Create a discount (admin; no MPIN,
# supports DRAFT)" — the same admin family as offers.deal.create.
#
# The merchant path exists and is declared in the same spec:
# POST /v1/merchant/{id}/mpin-actions with purpose: DISCOUNT_CREATE. Moving to
# it changes this card's base_url, path, constants and mpin_required, and
# nothing else — the fields, prompts and utterances below are the same either
# way. MPIN stays a manual step in the app; nothing here ever collects a PIN.
base_url: https://open.qa.lesspay.app
# merchantId is a QUERY parameter on this endpoint rather than a path segment,
# but it is written into the path template so placeholder substitution fills it
# from the verified identity. A merchant id must never be collected from a
# conversation.
path: "/v1/admin/offers/discounts?merchantId={merchantId}"
title: Create a discount
# FALSE while the admin route is in use: it genuinely does not check an MPIN,
# and claiming otherwise here would be a lie the executor acts on.
mpin_required: false
# Every call creates a real discount on a real merchant. Never safe to retry.
idempotent: false
version: 1
last_verified: 2026-09-04

# Sent on every call, whatever the merchant said.
#
# `source` marks where the offer came from. The backend declares AI_GENERATED
# as a value, and an offer Chotu built should say so — it costs nothing, it is
# never a question anyone would be asked, and it makes assistant-created offers
# countable later without a migration.
constants:
  source: AI_GENERATED

fields:
  - name: name
    type: string
    required: true
    prompt: "Is discount ka naam kya rakhein?"
    example: "Flat 20% Off"

  # The discriminator, and the one place where getting it wrong costs the
  # merchant money rather than merely reading badly.
  #
  # "50 rupaye off" and "50% off" are one word apart in speech and four hundred
  # rupees apart on a two thousand rupee bill. The `means` lines exist so the
  # constant is judged on what it DOES rather than on what it is called: a
  # label alone cannot say that discountValue is read as a percentage under one
  # and as rupees under the other.
  - name: discountType
    type: enum
    required: true
    prompt: "Percentage off, ya flat rupaye off?"
    values:
      - value: PERCENTAGE
        means: >-
          A share of the bill. discountValue is a percentage between 0 and 100,
          never a rupee amount — "20% off" is 20 here. Use this when the
          merchant says percent, pratishat, or "%".
      - value: FLAT
        means: >-
          A fixed number of rupees off the bill. discountValue is that rupee
          amount — "50 rupaye off" is 50 here. Use this when the merchant names
          money rather than a share.

  - name: discountValue
    type: number
    required: true
    prompt: "Kitna discount dena hai?"
    example: 20

  # Only meaningful for a percentage. A flat discount is already a fixed
  # amount, so capping it says nothing, and asking about it reads as the
  # assistant not following what was just agreed.
  - name: maxAmount
    type: number
    required: false
    required_when: { discountType: PERCENTAGE }
    prompt: "Saving ko kisi amount pe cap karna hai?"
    example: 500

  # The second discriminator. The app puts these behind one toggle — "When
  # discount applies: Payment Count | Payment Amount" — and each choice reveals
  # a different question underneath it. Declaring them with required_when is
  # what stops the merchant being asked for a bill threshold when they said
  # "every third visit".
  - name: rules.appliesOn
    type: enum
    required: true
    prompt: "Ye bill amount pe milega, ya customer ki nth visit pe?"
    values:
      - value: PAYMENT_AMOUNT
        means: >-
          Unlocked when the bill crosses an amount. Pairs with
          rules.minBillAmount.
      - value: PAYMENT_COUNT
        means: >-
          Unlocked on the customer's Nth payment, whatever they spend. Pairs
          with rules.paymentCount.

  - name: rules.minBillAmount
    type: number
    required: true
    required_when: { rules.appliesOn: PAYMENT_AMOUNT }
    prompt: "Bill kitne rupaye se upar hona chahiye?"
    example: 500

  - name: rules.paymentCount
    type: integer
    required: true
    required_when: { rules.appliesOn: PAYMENT_COUNT }
    prompt: "Kaunsi payment pe milega — doosri, teesri?"
    example: 3

  - name: rules.applyOnMyCustomersOnly
    type: boolean
    required: false
    prompt: "Sirf aapke apne customers ke liye?"

  # HAPPY HOURS. The app makes this a required yes/no toggle and only shows the
  # time pickers when it is on, which is exactly required_when.
  - name: happyHoursEnabled
    type: boolean
    required: false
    prompt: "Kya ye sirf kuch ghanton ke liye hai — happy hours?"
    derive: >-
      True when the merchant names a time window for the discount. Not a field
      the API takes; it decides whether happyHours.startTime and endTime are
      asked for.

  - name: happyHours.startTime
    type: string
    required: true
    required_when: { happyHoursEnabled: [true] }
    prompt: "Kitne baje se?"
    example: "16:00"
    derive: "24-hour HH:mm. 4 pm is 16:00."

  - name: happyHours.endTime
    type: string
    required: true
    required_when: { happyHoursEnabled: [true] }
    prompt: "Aur kitne baje tak?"
    example: "19:00"
    derive: "24-hour HH:mm. 7 pm is 19:00."

  - name: appliesOnWeekends
    type: boolean
    required: false
    prompt: "Weekend pe bhi chalega?"

  # VALIDITY. The app asks it as "Ends: Forever | Schedule", so isLimited is
  # the answer to that and endDate only exists on one side of it. "Starts" is
  # Immediate by default and there is nothing to send for that, which is why
  # startDate is not a field here.
  - name: validity.isLimited
    type: boolean
    required: false
    default: false
    prompt: "Kab tak chalana hai — ya jab tak aap band na karein?"
    derive: >-
      True when the merchant names an end date. False means it runs until they
      switch it off, which is the app's "Forever".

  - name: validity.endDate
    type: string
    required: true
    required_when: { validity.isLimited: [true] }
    prompt: "Kis tareekh tak chalega?"
    example: "2026-11-30T23:59:59Z"
    derive: >-
      Full ISO-8601 with time and zone, not a bare date. A date the merchant
      gives without a time ends at 23:59:59Z on that day.

  - name: showOnShopProfile
    type: boolean
    required: false
    prompt: "Shop profile pe dikhana hai?"

  # REDEEM LIMITS. The API carries two pairs that look interchangeable —
  # redeemLimit/totalRedeemLimit at the top level and rules.maxUsesPerUser /
  # rules.maxTotalUses inside rules. The app drives the TOP-LEVEL pair, so
  # those are the two declared here and the rules pair is deliberately absent.
  # Filling both would leave the backend to decide which one the merchant
  # meant, which is not a decision to hand away.
  - name: redeemLimit
    type: integer
    required: false
    prompt: "Ek customer kitni baar use kar sakta hai?"
    example: 2

  - name: totalRedeemLimit
    type: integer
    required: false
    default: -1
    prompt: "Total kitne customers tak?"
    example: 500
    derive: >-
      -1 means uncapped, which is the app's default and what to send when the
      merchant does not limit it. A number means the first N customers only.

  # AUDIENCE. The app offers four choices and "All customers" is the default —
  # and the default is expressed by sending no target at all, so there is
  # nothing to collect unless the merchant narrows it themselves.
  - name: target.audience
    type: enum
    required: false
    prompt: "Sabhi customers ke liye, ya kisi khaas group ke liye?"
    values:
      - value: NEW_CUSTOMERS
        means: First-time LessPay visitors to this shop.
      - value: LOYAL_CUSTOMERS
        means: Customers with three or more visits in the last 30 days.
      - value: LAPSED_CUSTOMERS
        means: >-
          Customers who have not visited in over 30 days. The app calls these
          "inactive customers".
    derive: >-
      Left empty for "everyone", and that is how "everyone" is expressed --
      the whole `target` object is omitted rather than filled with a
      constant meaning "all". Verified: the working discount that set no
      audience sent no target at all. There may well be an ALL_CUSTOMERS
      value, but it has not been seen in a request that succeeded, and a
      guessed enum is a 400 at best and a mis-targeted offer at worst.

  - name: target.targetType
    type: enum
    required: true
    required_when:
      - {target.audience: [NEW_CUSTOMERS]}
      - {target.audience: [LOYAL_CUSTOMERS]}
      - {target.audience: [LAPSED_CUSTOMERS]}
    prompt: "Kis tarah ke customers ke liye?"
    values: [AUDIENCE]
    derive: >-
      Always AUDIENCE when the merchant names a customer group. The API
      requires it inside `target`, and there is no other kind of target to
      choose, so it is never a real question.

examples:
  - says: "har bill pe 20 percent off, 500 se upar"
    fields:
      discountType: PERCENTAGE
      discountValue: 20
      rules.appliesOn: PAYMENT_AMOUNT
      rules.minBillAmount: 500
  - says: "teesri visit pe 50 rupaye ki chhoot"
    fields:
      discountType: FLAT
      discountValue: 50
      rules.appliesOn: PAYMENT_COUNT
      rules.paymentCount: 3
  - says: "शाम चार से सात बजे तक दस परसेंट छूट"
    fields:
      discountType: PERCENTAGE
      discountValue: 10
      happyHoursEnabled: true
      happyHours.startTime: "16:00"
      happyHours.endTime: "19:00"
  - says: "purane customers ko wapas laane ke liye flat 100 rupaye off"
    fields:
      discountType: FLAT
      discountValue: 100
      target.targetType: AUDIENCE
      target.audience: LAPSED_CUSTOMERS

returns:
  success: [id, status, discountType, discountValue, showOnShopProfile]
  errors:
    400: Something in the discount was not accepted — the message says which field.
    404: That merchant was not found.

utterances:
  - create a discount for my shop
  - "10% off chalu karo"
  - flat 50 rupees off on every bill
  - "discount lagana hai"
  - start a percentage discount
  - "छूट वाला ऑफर बनाओ"
  - happy hours discount set karo
  - give 20 percent off above 500
  - naya discount banana hai
---

Creates a discount on the merchant's LessPay account.

A discount takes a share off the bill, or a fixed number of rupees off it.
That is the whole difference from a deal, which gives away an item — and it is
the distinction to settle before anything else is collected.

Two questions decide the shape of everything that follows. Whether the saving
is a percentage or a flat amount decides how `discountValue` is read. Whether
it unlocks on a bill amount or on a visit count decides which single rule
question is worth asking. Everything else has a sensible default and should
only be raised if the merchant raises it.
