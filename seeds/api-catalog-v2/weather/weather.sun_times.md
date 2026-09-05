---
type: api
status: live
api_id: weather.sun_times
domain: weather
method: GET
path: /json
title: Sunrise and sunset
base_url: "https://api.sunrise-sunset.org"
mpin_required: false
idempotent: true
version: 2
last_verified: 2026-09-04

constants:
  formatted: 0

# This service names its coordinate fields `lat` and `lng` rather than
# `latitude` and `longitude`. The geocode response uses the long names, so the
# derive lines below say which value goes where — without them the extractor
# has to guess that `lng` and `longitude` are the same thing.
fields:
  - name: lat
    type: number
    required: true
    in: query
    prompt: "Kaunsi jagah ka sunrise-sunset chahiye?"
    example: 28.61
    derive: >-
      The `latitude` value from the weather.geocode response for the place the
      merchant named.
  - name: lng
    type: number
    required: true
    in: query
    prompt: "Kaunsi jagah ka sunrise-sunset chahiye?"
    example: 77.21
    derive: >-
      The `longitude` value from the weather.geocode response. Never asked for
      on its own.
  - name: date
    type: string
    required: false
    in: query
    prompt: "Which date?"
    example: "2026-09-04"

returns:
  success: [results.sunrise, results.sunset, results.day_length]
  errors:
    400: Those coordinates were not valid.

utterances:
  - what time is sunset today
  - sunrise kab hoga
  - suraj kab doobega
  - "सूरज कब निकलेगा"
  - when does the sun set in mumbai
  - kitne baje sunset hai
---

Sunrise, sunset and day length for a place, from sunrise-sunset.org. No API
key.

Ask which place. `weather.geocode` supplies the coordinates, and note that this
service calls them `lat` and `lng`.
