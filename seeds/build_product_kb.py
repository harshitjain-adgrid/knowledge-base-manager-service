"""
Builds the product-knowledge seed: the documents the assistant answers
conversational questions from.

Everything here is SYNTHETIC. It is written the way real product documentation
should be written — heading-led, one idea per section, in the merchant's
vocabulary — so retrieval can be measured honestly before the real content
arrives. Every document carries `status: example`.

Deliberately complementary to what is already in the knowledge base: the two
existing documents cover "what is khata" and "creating an offer", so nothing
here repeats them.

Run:  python seeds/build_product_kb.py
"""

import io
import pathlib
import textwrap

OUT = pathlib.Path(__file__).parent / "product"

DOCS = [

# ═════════════════════ getting started ═════════════════════

dict(folder="getting-started", slug="what-is-chotu", title="What Chotu Can Do",
     type="concept", tags=["assistant", "capabilities"], owner="product",
     body="""
# What Chotu Can Do

Chotu is the assistant inside your shop's app. You can ask it questions about how
the app works, and you can ask it to do things for you.

## Asking questions

Chotu can explain anything about running your shop — how offers work, what khata
means, when your money reaches your bank, why an order was cancelled. Ask in
Hindi, English or a mix of both. It understands all three.

## Asking it to do things

Chotu can also act on your behalf:

- Add products, change prices, update stock
- Start and stop discounts
- Record udhaar and payments in your khata
- Update order status, cancel orders
- Change your shop timings and delivery settings
- Send payment reminders to customers

When you ask for something that involves money leaving your shop — a refund, a
cancellation, deleting a product — Chotu asks for your MPIN before doing it.

## What Chotu will not do

It will not do anything it is not sure about. If your request could mean two
different things, it asks which one you meant rather than guessing. If it cannot
find what you are asking about, it tells you plainly instead of inventing an
answer.

It also never shares one merchant's information with another. Your sales, your
customers and your khata are yours alone.
"""),

dict(folder="getting-started", slug="setting-up-your-store", title="Setting Up Your Store",
     type="guide", tags=["onboarding", "store"], owner="product",
     body="""
# Setting Up Your Store

A new shop needs four things before customers can order from it.

## 1. Your shop details

Add your shop name, address and a phone number customers can call. The name is
what appears at the top of your shop page, so use the name people know you by,
not a registered business name.

A photo of the shopfront makes a real difference — shops with a photo get
noticeably more first-time orders than shops without one.

## 2. Your timings

Set when you open and close. Outside those hours customers can still look at
your shop, but they cannot place an order. If you close one day a week, set that
too, so you are not marked as unreliable for missing orders on your day off.

## 3. At least one product

Your shop stays hidden from search until it has at least one product with a
price. Add a few of your best sellers first — you can build out the rest later.

## 4. Your bank account

Money from orders is held until a bank account is verified. Verification usually
takes one working day. Until then customers can order and pay, but nothing is
paid out to you.

## When you go live

Once all four are done your shop appears in search within about fifteen minutes.
You will get a notification when the first customer views it.
"""),

# ═════════════════════ catalog ═════════════════════

dict(folder="catalog", slug="adding-products", title="Adding Products",
     type="guide", tags=["catalog", "products"], owner="catalog-team",
     body="""
# Adding Products

Every product needs a name and a price. Everything else is optional but helps
customers find it.

## The fastest way

Tell Chotu what you want to add — "add amul butter 500g for 265" — and it fills
in the rest. It asks only for what it still needs.

## Doing it by hand

1. Open **Catalog** from the main menu.
2. Tap **Add Product**.
3. Enter the name as a customer would search for it. "Amul Butter 500g" finds
   more customers than "Butter".
4. Set the price and the unit — per piece, per kilo, per litre, per packet.
5. Add a photo if you have one.

## Why the unit matters

The unit is what the customer sees next to the price. A product priced at ₹60
per kilo and one priced at ₹60 per piece look identical without it, and that
mismatch is the single most common cause of order disputes.

## Categories

Putting products in categories helps customers browse a large shop. For a shop
with fewer than about twenty products, categories add little — customers can see
everything at once.

## Drafts

A product saved as a draft is not visible to customers. Use this while you are
still deciding on a price.
"""),

dict(folder="catalog", slug="managing-stock", title="Managing Stock",
     type="guide", tags=["catalog", "stock"], owner="catalog-team",
     body="""
# Managing Stock

Stock decides whether a customer can order something, not whether they can see
it.

## Marking something out of stock

Set the quantity to zero. The product stays on your shop page, greyed out, with
"Out of stock" next to it. Customers can still see it and know you normally
carry it.

Tell Chotu "maggi is finished" and it does this for you.

## Why not just delete it

Deleting removes the product's entire history — how much of it you have sold, at
what price, to whom. For something you will restock next week, that history is
worth keeping. Delete only what you have genuinely stopped selling.

## Stock counts down automatically

Every order reduces the quantity. When it reaches zero the product goes out of
stock on its own, so you do not have to watch it.

## Low stock warnings

You get a notification when a product falls below five units. If that is too
noisy for something you sell in large volumes, turn the warning off for that
product individually.

## Bulk updates

For a delivery of many items at once, use **Catalog → Update Stock** and enter
the new quantities in one screen rather than opening each product.
"""),

dict(folder="catalog", slug="pricing-and-units", title="Pricing and Units",
     type="guide", tags=["catalog", "pricing"], owner="catalog-team",
     body="""
# Pricing and Units

## Changing a price

Prices can be changed at any time. The new price applies to orders placed from
that moment; orders already placed keep the price they were placed at.

Tell Chotu "make rice 60 instead of 55" and it updates it.

## Prices during an offer

If a discount is running, the customer sees the discounted price and the
original crossed out. Changing the base price while an offer runs changes both —
the discount recalculates from the new price.

## Loose goods

For anything sold by weight, price per kilo and set the unit to kilo. Customers
can then order half a kilo or two and a half kilos, and the amount works out
correctly.

## Prices that include delivery

Do not build delivery into your product prices. Set a delivery charge in
**Store → Delivery** instead. Products priced above the market look expensive in
search results, where the delivery charge is not shown.

## Maximum retail price

For packaged goods, your price cannot exceed the printed MRP. The app checks
this for common products and will refuse a price that looks wrong.
"""),

# ═════════════════════ offers ═════════════════════

dict(folder="offers", slug="offer-types", title="Types of Offer",
     type="concept", tags=["offers", "discounts"], owner="growth-team",
     body="""
# Types of Offer

There are three ways to give a customer a lower price, and they behave
differently.

## Percentage off

Takes a percentage off the order — 20% off everything, or 20% off selected
products. Best when you want the discount to feel bigger on larger orders.

## Flat amount off

Takes a fixed rupee amount off — ₹100 off. Usually paired with a minimum order
value, so "₹100 off on orders above ₹500". Best when you want to push order
sizes up to a particular number.

## Coupon code

The customer types a code at checkout, like DIWALI20. Nothing happens unless
they enter it.

Use a coupon when you want to give a discount to some customers and not others —
in a WhatsApp message to your regulars, say, or printed on a flyer. Use a
percentage or flat offer when you want everyone to get it automatically.

## Which applies when several are running

Only one discount applies to an order. If a customer qualifies for more than
one, the app applies whichever gives them the larger saving. Discounts never
stack.

## Limits

The largest discount you can set depends on your plan. If you enter more than
your plan allows, the app tells you the maximum at that moment.
"""),

dict(folder="offers", slug="offer-scheduling", title="Scheduling and Ending Offers",
     type="guide", tags=["offers", "scheduling"], owner="growth-team",
     body="""
# Scheduling and Ending Offers

## Starting later

An offer with a start date in the future is saved as *scheduled*. It goes live
by itself on the morning of that date. Nothing is shown to customers before
then.

This is how to set up a festival sale in advance rather than remembering to
switch it on.

## Ending

Every offer needs an end date. If you do not set one, it ends thirty days after
it starts. An offer that has ended keeps its record — how many orders used it
and what they were worth — so you can compare it against the next one.

## Extending

Change the end date and the offer keeps running. This is different from creating
a new offer with the same name, which the app refuses while the first one is
still live.

## Stopping early

Stopping an offer takes effect immediately. Orders already placed keep the
discount they were given; new orders pay full price.

## Why an offer might not have started

A scheduled offer does not go live if your shop is closed for a holiday that
covers its start date. It starts on the first day the shop is open again.
"""),

dict(folder="offers", slug="offer-not-applying", title="Why an Offer Is Not Applying",
     type="troubleshooting", tags=["offers", "troubleshooting"], owner="growth-team",
     body="""
# Why an Offer Is Not Applying

A discount you can see in your Offers list is not always a discount the customer
gets. These are the reasons, in the order they are worth checking.

## The order is below the minimum

Most flat-amount offers have a minimum order value. An offer of ₹100 off above
₹500 does nothing on a ₹480 order. The customer sees no discount and no
explanation.

## Another offer gave a bigger saving

Discounts do not stack. If two offers apply, the customer gets the larger one
only — so your new offer may be working correctly and simply losing to an older
one.

## It only covers selected products

An offer set to "selected products" applies to nothing if the order contains
none of them. Check which products it covers.

## It has not started, or has ended

A scheduled offer shows in your list before it is live. An ended offer stays in
the list too. Check the status column rather than assuming anything listed is
running.

## The customer did not enter the code

Coupons do nothing unless typed at checkout. If you meant everyone to get the
discount automatically, you wanted a percentage or flat offer instead.

## Still not working

Ask Chotu to check a specific order — "why did order 4471 not get the discount"
— and it will tell you which of these applied.
"""),

# ═════════════════════ khata ═════════════════════

dict(folder="khata", slug="recording-udhaar", title="Recording Udhaar",
     type="guide", tags=["khata", "credit"], owner="khata-team",
     body="""
# Recording Udhaar

Khata is your record of who owes you money. Every entry either adds to what
somebody owes or takes away from it.

## When a customer takes goods on credit

Tell Chotu who and how much — "ramesh took 450 rupees of goods". The amount is
added to that customer's balance. Add a note about what they took if you want to
be able to check later.

By hand: **Khata → the customer → Add Entry → Credit given**.

## When they pay you back

Tell Chotu "ramesh paid 300". The amount comes off their balance. Part payments
are fine — the rest stays outstanding.

Record which way they paid, cash or UPI, if you want your khata to reconcile
against your bank statement.

## A customer who is not in your list yet

Chotu adds them. It asks for a phone number, which is what reminders are sent
to. A khata without a phone number works, but you cannot send reminders on it.

## Correcting a mistake

Entries cannot be edited, because a ledger you can quietly change is a ledger
nobody can trust. Add a correcting entry in the other direction instead, with a
note saying why. Both entries stay visible.

## Backdating

An entry can be dated up to thirty days in the past, for when you write in a
paper book during the day and enter it in the evening.
"""),

dict(folder="khata", slug="khata-reminders", title="Sending Payment Reminders",
     type="guide", tags=["khata", "reminders"], owner="khata-team",
     body="""
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
"""),

dict(folder="khata", slug="khata-limits", title="Khata Limits and Rules",
     type="policy", tags=["khata", "limits"], owner="khata-team",
     body="""
# Khata Limits and Rules

## Per customer

A single customer's outstanding balance cannot exceed ₹50,000. Beyond that the
app refuses new credit entries for them until some is paid back.

## Per shop

Total outstanding credit across all customers is capped at ₹5,00,000 for a
standard account. Shops that need more can request a higher limit, which is
reviewed against how reliably existing khata is settled.

## Ageing

Balances are grouped by how long they have been outstanding: current, over 30
days, over 60 days, over 90 days. Anything past 90 days is flagged in your
reports, because that is the point at which most of it is never recovered.

## What khata is not

Khata is a record, not a loan. The app does not lend money, charge interest, or
collect on your behalf. What a customer owes is between you and them; the app
only keeps the record and sends the reminders you ask it to.

## Privacy

A customer can see their own khata with you if they use the app. They cannot see
what anybody else owes you, and no other shop can see what they owe you.
"""),

# ═════════════════════ orders ═════════════════════

dict(folder="orders", slug="order-lifecycle", title="How an Order Moves",
     type="concept", tags=["orders", "fulfilment"], owner="orders-team",
     body="""
# How an Order Moves

Every order passes through the same stages, and the customer is told at each
one.

## New

The order has been placed and paid for, or marked cash on delivery. You have
been notified. Nothing is committed until you accept it.

An order not accepted within fifteen minutes is cancelled automatically and the
customer is refunded. This protects customers from shops that have gone home
without closing.

## Accepted

You have confirmed you can fulfil it. The customer sees an estimated time.

## Preparing

You are putting it together. Optional — some shops go straight from accepted to
ready.

## Ready

Packed and waiting, either for pickup or for a delivery person.

## Out for delivery

On its way. If you use your own delivery, mark this yourself. If you use the
app's delivery partners, it updates on its own.

## Delivered

Complete. Payment is included in your next settlement.

## Cancelled

Stopped, by you or by the customer. Cancelling needs a reason, and if the order
was paid for, the refund starts automatically.
"""),

dict(folder="orders", slug="cancelling-an-order", title="Cancelling an Order",
     type="guide", tags=["orders", "cancellation"], owner="orders-team",
     body="""
# Cancelling an Order

## When you can

Any order that has not been delivered. Once it is marked delivered, use a refund
instead.

## How

Tell Chotu "cancel order 4471". It asks why, because the reason determines what
the customer is told and whether the cancellation counts against your shop.

By hand: open the order, then **Cancel Order**.

## Reasons

- **Out of stock** — you cannot supply an item. Consider setting its stock to
  zero at the same time so it does not happen again.
- **Customer request** — they asked. Does not count against your shop.
- **Shop closed** — you are not open. Check your timings if this happens often.
- **Other** — needs a note.

## The refund

If the order was paid online, the refund starts immediately and reaches the
customer in three to five working days. Cash on delivery orders need no refund.

## The effect on your shop

Cancellations for "out of stock" and "shop closed" count towards your
reliability score, which affects how high your shop appears in search. Customer
requests do not.

Two or three across a busy month is normal. A run of them in a week is worth
looking at.
"""),

# ═════════════════════ payments ═════════════════════

dict(folder="payments", slug="settlements", title="When Your Money Arrives",
     type="concept", tags=["payments", "settlements"], owner="payments-team",
     body="""
# When Your Money Arrives

## The cycle

Money from online orders is settled to your bank account every day for orders
delivered up to two days earlier. An order delivered on Monday is paid out on
Wednesday.

Cash on delivery orders never pass through the app — you already have the money.

## Why the two day gap

It is the window in which a customer can raise a problem. Settling instantly
would mean recovering money from you afterwards, which is worse for everyone.

## What is deducted

The platform fee, and the payment gateway charge on online payments. Both are
itemised on every settlement, so the total never appears without an explanation.

## Where to see it

**Payments → Settlements** lists every payout with the orders it covers. Ask
Chotu "when will i get my money" and it tells you the next payout and its
amount.

## If a settlement has not arrived

Check that your bank account is still verified. A changed or closed account
holds settlements until a new one is verified — the money is not lost, it is
waiting.

Settlements do not run on bank holidays. A payout due on a holiday arrives the
next working day.
"""),

dict(folder="payments", slug="refund-policy", title="Refund Rules",
     type="policy", tags=["payments", "refunds"], owner="payments-team",
     body="""
# Refund Rules

## The window

A refund can be issued up to seven days after an order is delivered. After that
the payment can no longer be reversed through the app, and anything you settle
with the customer is between you and them.

## Full and partial

A refund can be for the whole order or part of it — one item out of five, say.
Partial refunds cannot exceed what was actually paid.

## How long it takes

Three to five working days to reach the customer, depending on their bank. The
app cannot make this faster; the delay is on the banking side, not ours.

## Where the money comes from

From your next settlement. If your next settlement is smaller than the refund,
the difference is carried to the one after.

## Cancelled orders

Cancelling an unfulfilled order refunds it automatically. You do not need to
issue a separate refund, and doing so would refund the customer twice.

## Cash on delivery

Nothing to refund through the app — the money never passed through it. Record it
in your khata if you want a record of having paid the customer back.

## Confirmation

Refunds need your MPIN, because they move money out of your account.
"""),

dict(folder="payments", slug="payment-links", title="Payment Links",
     type="guide", tags=["payments", "collection"], owner="payments-team",
     body="""
# Payment Links

A payment link collects money from someone without them placing an order. Useful
for a customer standing in your shop, for an advance, or for settling an old
balance.

## Creating one

Tell Chotu "create a payment link for 500". You get a link to send over WhatsApp
or read out as a UPI request.

## How long it lasts

Twenty-four hours by default. You can set a different validity when you create
it. An expired link cannot be paid; create a new one.

## When it is paid

You are notified immediately, and the money joins your normal settlement cycle —
it is not paid out instantly.

## Against a khata balance

A payment link created from a customer's khata is recorded against their balance
automatically when it is paid. A general link is not, so if you use one for
udhaar, record the payment in the khata yourself.

## Refunding one

A link payment can be refunded like any other, within the same seven day window.
"""),

# ═════════════════════ store ═════════════════════

dict(folder="store", slug="store-timings", title="Shop Timings and Holidays",
     type="guide", tags=["store", "timings"], owner="product",
     body="""
# Shop Timings and Holidays

## Daily hours

Set when you open and close. Customers can browse at any hour but can only order
inside them. Orders placed near closing time still have to be fulfilled, so set
your closing time to when you actually stop, not when you leave.

## A weekly day off

Set it once in your timings and it repeats every week. Your shop is not
penalised for missing orders on that day.

## Holidays

For particular dates — a festival, a wedding, a trip — mark a holiday. Tell
Chotu "shop is closed tomorrow" or set a date range in **Store → Holidays**.
Customers see when you reopen.

## What happens to scheduled offers

An offer scheduled to start during a holiday starts on the first day you are
open again, not while you are closed.

## Closing at short notice

Marking a holiday for today closes the shop immediately. Orders already accepted
still need fulfilling — a holiday stops new orders, it does not cancel existing
ones.

## Reliability

Being closed when you say you are closed does not hurt your shop. Being open on
paper and not accepting orders does.
"""),

dict(folder="store", slug="delivery-settings", title="Delivery Settings",
     type="guide", tags=["store", "delivery"], owner="product",
     body="""
# Delivery Settings

## How far you deliver

Set a radius in kilometres. Customers outside it do not see your shop when they
search, so a radius wider than you can actually serve creates cancellations
rather than orders.

## What you charge

A flat delivery charge, shown to the customer before they pay. You can set free
delivery above an order value — a common way to push order sizes up.

## Free delivery

Setting free delivery above a threshold is usually more effective than a
discount of the same amount. Customers respond more to "free delivery above
₹300" than to "₹30 off above ₹300", even though they are the same money.

## Your own delivery, or the app's

If you deliver yourself, you mark orders out for delivery and delivered. If you
use the app's partners, that happens automatically and the partner's fee is
deducted at settlement.

## Pickup only

Set the radius to zero. Your shop shows as pickup only, and customers collect
from you.
"""),

# ═════════════════════ reports ═════════════════════

dict(folder="reports", slug="reading-your-sales-report", title="Reading Your Sales Report",
     type="guide", tags=["reports", "sales"], owner="product",
     body="""
# Reading Your Sales Report

## What the numbers mean

- **Total sales** — what customers paid, before fees are deducted. Not what
  reaches your bank.
- **Orders** — how many were delivered. Cancelled orders are excluded.
- **Average order value** — total sales divided by orders. The number most worth
  moving, because raising it costs nothing extra in delivery or effort.
- **Change** — against the same length of period immediately before.

## Total sales is not your income

Fees come off before settlement. **Payments → Settlements** shows what actually
arrives. The gap between the two is normal and is itemised.

## Best sellers

**Reports → Top Products** ranks by revenue, not by count. A product sold twice
at ₹500 ranks above one sold ten times at ₹50 — which is usually what you want
when deciding what to stock.

## Customers

New against returning tells you whether you are building regulars or churning
through first-time buyers. For most shops, returning customers past the first
few months is the number that predicts whether the shop grows.

## Asking instead of reading

Ask Chotu "how much did i sell today" or "what sold best this month". It reads
the same numbers and answers in a sentence.
"""),
]


def render(doc: dict) -> str:
    front = [
        "---",
        f"title: {doc['title']}",
        f"type: {doc['type']}",
        "tags: [%s]" % ", ".join(doc["tags"]),
        "audience: merchant",
        "status: example  # synthetic seed data — replace with real content",
        f"owner: {doc['owner']}",
        "last_reviewed: 2026-08-19",
        "---",
        "",
    ]
    return "\n".join(front) + textwrap.dedent(doc["body"]).strip() + "\n"


def main() -> None:
    if OUT.exists():
        for old in OUT.rglob("*.md"):
            old.unlink()

    counts: dict[str, int] = {}
    for doc in DOCS:
        folder = OUT / doc["folder"]
        folder.mkdir(parents=True, exist_ok=True)
        io.open(folder / f"{doc['slug']}.md", "w", encoding="utf-8").write(render(doc))
        counts[doc["folder"]] = counts.get(doc["folder"], 0) + 1

    words = sum(len(textwrap.dedent(d["body"]).split()) for d in DOCS)
    print(f"{len(DOCS)} documents across {len(counts)} folders -> {OUT}")
    for folder in sorted(counts):
        print(f"  /{folder}/{' ' * (18 - len(folder))}{counts[folder]}")
    print(f"{words} words, {words // len(DOCS)} per document on average")


if __name__ == "__main__":
    main()
