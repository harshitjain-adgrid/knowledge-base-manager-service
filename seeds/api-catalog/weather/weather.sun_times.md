---
type: api
status: live  # a real public API — this one can actually be called
api_id: weather.sun_times
domain: weather
method: GET
path: /json
title: Sunrise and sunset
base_url: "https://api.sunrise-sunset.org"
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

# Sent on every call, whatever the merchant said. The path alone
# does not identify this action; these values do.
constants:
  formatted: 0

fields:
  - name: lat
    type: number
    required: true
    in: query
    prompt: "Which place? I need its latitude."
    example: 28.61
  - name: lng
    type: number
    required: true
    in: query
    prompt: "And its longitude?"
    example: 77.21
  - name: date
    type: date
    required: false
    in: query
    prompt: "Which date?"
    default: today

returns:
  success: [results.sunrise, results.sunset, results.day_length]

utterances:
  - what time does the sun set today
  - sunrise kab hoga
  - when does it get dark
  - how long is daylight today
  - tell me sunset time
---

Sunrise, sunset, solar noon and day length for a latitude and
longitude. No API key. Times come back in UTC when formatted=0.
