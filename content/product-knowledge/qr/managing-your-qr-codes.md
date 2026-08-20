---
title: Managing More Than One QR Code
type: guide
tags: [qr, upi, merchant-action]
audience: merchant
status: published
owner: product-team
derived_from: chotu-handover.md
last_reviewed: 2026-08-20
---

# Managing More Than One QR Code

You can keep several UPI IDs on your account, but only one is in use at a time.
Adding, switching and removing them are all confirmed with your MPIN.

## Live and backup

Every QR you add is either:

- **Live** — the one customers are actually paying into. There is exactly one.
- **Backup** — kept on your account, ready to be switched to, but not in use.

Your first QR becomes live automatically. Every one after that is added as a
backup until you promote it.

## Switching which one is live

Promoting a backup QR makes it live, and the one that was live becomes a backup
in the same moment. You never end up with two live QRs or none.

Use this when you want takings to move to a different UPI account — switch the
live QR rather than deleting and re-adding.

## The live QR cannot be deleted

This is the one rule that catches people out. **You cannot delete the QR you are
currently taking payments on.** If you could, your shop would have no way to
accept money.

To remove it, promote another QR to live first, then delete the old one.

Chotu refuses this up front rather than asking for your MPIN and then failing.

## What a deleted QR does

Deleting is not destructive to your records. The QR stops being usable, but
payments already taken on it stay in your history with everything attached to
them.

## What if you have no QR at all

A shop with no QR cannot take LessPay payments and customers cannot get your
offers. Add a UPI ID and it becomes live automatically as the first one.

## Frequently asked as

- "how do I add another qr"
- "doosra qr kaise add karein"
- "how do I change which qr is being used"
- "qr delete nahi ho raha"
- "why can't I delete my qr"
- "what is a backup qr"
- "how do I switch my upi account"
