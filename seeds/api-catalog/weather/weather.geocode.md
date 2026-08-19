---
type: api
status: live  # a real public API — this one can actually be called
api_id: weather.geocode
domain: weather
method: GET
path: /v1/search
title: "Find a place's coordinates"
base_url: "https://geocoding-api.open-meteo.com"
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: name
    type: string
    required: true
    in: query
    prompt: "Which town or city?"
    example: Delhi
  - name: count
    type: integer
    required: false
    in: query
    prompt: "How many matches should I bring back?"
    default: 1

returns:
  success: ["results[].latitude", "results[].longitude", "results[].country", "results[].timezone"]

utterances:
  - where is bengaluru exactly
  - find the coordinates of a city
  - look up a place
  - what are the lat long for mumbai
  - geocode this town for me
---

Turns a place name into coordinates, country and timezone. From
Open-Meteo. No API key.

Usually the first step before `weather.current` or `weather.air_quality`, both of
which need latitude and longitude rather than a name.
