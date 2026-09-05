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
version: 2
last_verified: 2026-09-04

# Sent on every call, whatever the merchant said. The path alone
# does not identify this action; these values do.
constants:
  current: temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m

# A NOTE ON THE COORDINATES, because this card reads oddly without it.
#
# Open-Meteo takes a latitude and a longitude and nothing else. No shop owner
# says those out loud, so the merchant is never asked for them: the prompts
# below ask for a PLACE, and `weather.geocode` turns the name into numbers
# before this card is called. The lookup is chosen at selection time and its
# response is handed to the extractor, which reads the coordinates out of it.
#
# The fields stay `required` even so, and that is deliberate rather than
# sloppy. `missing()` is what triggers the lookup at all — a card whose
# coordinates are optional is a card the geocode step never runs for, and the
# request goes out with no location and comes back 400. So they are required,
# and the prompt is the thing that changed: in the worst case, where the lookup
# could not run, the merchant is asked which place they meant. They are never
# asked for a number they do not have.
fields:
  - name: latitude
    type: number
    required: true
    in: query
    prompt: "Kaunsi jagah ka mausam bataun?"
    example: 28.61
    derive: >-
      Read from the weather.geocode response for the place the merchant named.
      Taken directly only when the merchant states coordinates themselves,
      which is rare and always fine.
  - name: longitude
    type: number
    required: true
    in: query
    prompt: "Kaunsi jagah ka mausam bataun?"
    example: 77.21
    derive: >-
      Read from the weather.geocode response for the place the merchant named,
      alongside latitude. Never asked for on its own.
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
  - "दिल्ली में मौसम कैसा है"
  - jaipur ka mausam batao
---

Current temperature, humidity, wind and conditions for a place, from
Open-Meteo. No API key.

The service itself works in coordinates. A merchant works in place names, so
`weather.geocode` runs first and turns one into the other. Ask which place;
never ask for a latitude.
