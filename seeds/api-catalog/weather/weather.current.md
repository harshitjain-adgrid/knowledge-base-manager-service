---
type: api
status: live  # a real public API — this one can actually be called
api_id: weather.current
domain: weather
method: GET
path: /v1/forecast
title: Current weather
base_url: "https://api.open-meteo.com"
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

# Sent on every call, whatever the merchant said. The path alone
# does not identify this action; these values do.
constants:
  current: temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m

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
  - name: timezone
    type: string
    required: false
    in: query
    prompt: "Which timezone should times be in?"
    example: Asia/Kolkata

returns:
  success: [current.temperature_2m, current.weather_code, current.wind_speed_10m]
  errors:
    400: Those coordinates were not valid.

utterances:
  - "what's the weather like"
  - aaj mausam kaisa hai
  - is it raining right now
  - how hot is it outside
  - temperature kya hai abhi
  - tell me the current weather
  - kitni garmi hai aaj
---

Current temperature, humidity, wind and conditions for a latitude and
longitude, from Open-Meteo. No API key.

It needs coordinates, not a place name. Turn a name into coordinates with
`weather.geocode` first.
