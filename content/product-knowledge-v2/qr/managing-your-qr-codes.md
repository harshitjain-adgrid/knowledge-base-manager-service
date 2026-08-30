---
title: Managing More Than One QR Code
type: guide
tags: [qr, upi, merchant-action]
audience: merchant
status: published
owner: product-team
last_reviewed: 2026-08-27
review_by: 2027-02-27
answers:
  - how to add another QR or UPI ID
  - how to switch which QR is taking payments
  - why the live QR cannot be deleted
not_covered:
  - what a UPI ID is and why an offer needs the LessPay QR
  - where settled money arrives
related: [your-upi-qr, how-you-get-paid, settlements]
aliases: [doosra qr, qr badalna, backup qr, upi account badalna, qr delete]
entities: [Live, Backup, MPIN, UPI ID]
---

# Managing More Than One QR Code

You can keep several UPI IDs on your account, but only one is in use at a time.
Adding, switching and removing them are all confirmed with your MPIN.

## The steps to add and switch a QR

1. Open the **QR** section of LessPay Business.
2. Choose to add a UPI ID and type it exactly as it appears in your own UPI app.
3. Confirm with your **MPIN**. The new QR is added as a **backup** unless it is
   your first, in which case it becomes live automatically.
4. To start taking payments on it, promote that backup to **live**. The one that
   was live becomes a backup in the same moment.
5. To remove an old QR, promote a different one to live first, then delete the
   old one.

## Live and backup

Every QR you add is either:

- **Live** — the one customers are actually paying into. There is exactly one.
- **Backup** — kept on your account, ready to be switched to, but not in use.

Your first QR becomes live automatically. Every one after that is added as a
backup until you promote it.

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

## Hinglish mein

Aap apne account par ek se zyada UPI ID rakh sakte hain, lekin ek waqt par sirf
ek hi chalti hai. QR section mein jaakar UPI ID daalein aur MPIN se confirm
karein — pehli QR apne aap live ho jati hai, baaki backup ke roop mein judti
hain. Kisi backup ko live banane par purani wali usi waqt backup ban jati hai,
isliye kabhi do live ya zero live nahi hote. Sabse zaroori niyam: jo QR abhi
live hai use delete nahi kar sakte. Pehle doosri ko live karein, phir purani
delete karein. Delete karne se purane payment ka record nahi jata.

## Frequently asked as

- "how do I add another qr"
- "doosra qr kaise add karein"
- "दूसरा क्यूआर कैसे जोड़ें"
- "how do I change which qr is being used"
- "qr delete nahi ho raha"
- "क्यूआर डिलीट नहीं हो रहा"
- "why can't I delete my qr"
- "what is a backup qr"
- "how do I switch my upi account"
