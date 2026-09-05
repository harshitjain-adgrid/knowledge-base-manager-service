---
type: api
status: live
api_id: weather.air_quality
domain: weather
method: GET
path: /v1/air-quality
title: Air quality
base_url: "https://air-quality-api.open-meteo.com"
mpin_required: false
idempotent: true
version: 2
last_verified: 2026-09-04

constants:
  current: pm2_5,pm10,us_aqi

# Same shape as weather.current: the service takes coordinates, the merchant
# gives a place, and weather.geocode bridges the two. See that card for why
# these stay `required` while the prompt asks for a place name.
fields:
  - name: latitude
    type: number
    required: true
    in: query
    prompt: "Kaunsi jagah ki hawa ki quality dekhun?"
    example: 28.61
    derive: >-
      Read from the weather.geocode response for the place the merchant named.
      Taken directly only when the merchant states coordinates themselves.
  - name: longitude
    type: number
    required: true
    in: query
    prompt: "Kaunsi jagah ki hawa ki quality dekhun?"
    example: 77.21
    derive: >-
      Read from the weather.geocode response, alongside latitude. Never asked
      for on its own.

returns:
  success: [current.us_aqi, current.pm2_5, current.pm10]
  errors:
    400: Those coordinates were not valid.

utterances:
  - how is the air quality today
  - aqi kitna hai
  - is the air polluted right now
  - "दिल्ली में प्रदूषण कितना है"
  - pollution level kya hai
  - hawa kaisi hai aaj
---

Current air quality — US AQI, PM2.5 and PM10 — for a place, from Open-Meteo.
No API key.

Ask which place. `weather.geocode` supplies the coordinates.
