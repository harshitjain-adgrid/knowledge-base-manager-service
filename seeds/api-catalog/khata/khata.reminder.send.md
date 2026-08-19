---
type: api
status: example  # synthetic seed data — replace with the real contract
api_id: khata.reminder.send
domain: khata
method: POST
path: /v1/merchant/khata/reminders
title: Send a payment reminder
mpin_required: false
idempotent: false
version: 1
last_verified: 2026-08-19

fields:
  - name: customer_id
    type: string
    required: true
    prompt: "Who should I remind?"
  - name: channel
    type: enum
    required: false
    prompt: "On WhatsApp or by SMS?"
    default: whatsapp
    values: [whatsapp, sms]

returns:
  success: [reminder_id, sent_at, channel]
  errors:
    404: I do not have a khata for that customer.
    429: A reminder already went out to them today.

utterances:
  - remind ramesh to pay
  - send a payment reminder
  - yaad dila do udhaar ka
  - message my customers who owe money
  - send whatsapp reminder for pending payment
  - ask him for the money politely
---

Sends a customer a polite reminder about what they owe, over WhatsApp
or SMS, with the amount and a payment link.

This asks them to pay. Recording that they did is `khata.entry.settle`.
