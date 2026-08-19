---
title: Sending Payment Reminders
type: guide
tags: [khata, reminders]
audience: merchant
status: example  # synthetic seed data — replace with real content
owner: khata-team
last_reviewed: 2026-08-19
---
# Sending Payment Reminders

## Sending one

Ask Chotu to "remind ramesh to pay". It sends a WhatsApp message with the amount
outstanding and a payment link, so the customer can settle without coming to the
shop.

If they are not on WhatsApp it falls back to SMS.

## What the message says

The message is polite and short. It names your shop, the amount, and how long it
has been outstanding. It does not threaten and does not mention other customers.

You cannot change the wording. This is deliberate — an angry reminder sent from
a shop's account damages the shop, not the customer.

## How often

One reminder per customer per day. A second request on the same day is refused,
with a note saying when the last one went.

## Reminding several people at once

**Khata → Send Reminders** selects everyone overdue past a number of days you
choose. Review the list before sending; a customer who paid in cash this morning
and has not been recorded yet should be taken off it.

## When they pay

The reminder includes a payment link. Money paid through it is recorded against
the khata automatically. Cash paid in the shop still has to be recorded by you.
