---
type: api
status: live  # a real public API — this one can actually be called
api_id: weather.air_quality
domain: weather
method: GET
path: /v1/air-quality
title: Air quality
base_url: "https://air-quality-api.open-meteo.com"
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

# Sent on every call, whatever the merchant said. The path alone
# does not identify this action; these values do.
constants:
  current: pm2_5,pm10,us_aqi

fields:
  - name: latitude
    type: number
    required: true
    in: query
    prompt: "Which place? I need its latitude."
    example: 28.61
  - name: longitude
    type: number
    required: true
    in: query
    prompt: "And its longitude?"
    example: 77.21

returns:
  success: [current.pm2_5, current.pm10, current.us_aqi]

utterances:
  - how bad is the air today
  - what is the aqi right now
  - pollution kaisa hai aaj
  - is the air quality safe outside
  - check pm2.5 levels
---

Current PM2.5, PM10 and US AQI for a latitude and longitude, from
Open-Meteo. No API key.

Air quality, not weather — for temperature and rain use `weather.current`.
