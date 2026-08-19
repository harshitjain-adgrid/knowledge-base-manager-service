---
type: api
status: live  # a real public API — this one can actually be called
api_id: reference.define_word
domain: reference
method: GET
path: "/api/v2/entries/en/{word}"
title: Define a word
base_url: "https://api.dictionaryapi.dev"
mpin_required: false
idempotent: true
version: 1
last_verified: 2026-08-19

fields:
  - name: word
    type: string
    required: true
    in: path
    prompt: "Which word?"
    example: discount

returns:
  success: ["[].meanings[].definitions[].definition", "[].phonetic"]
  errors:
    404: No definition found for that word.

utterances:
  - what does this word mean
  - define invoice for me
  - iska matlab kya hai
  - look up the meaning of a word
  - spelling and meaning of a word
---

English dictionary definition, pronunciation and examples for a word.
No API key.
