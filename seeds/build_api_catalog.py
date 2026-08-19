"""
Builds the API catalogue seed: one markdown file per API, grouped by domain.

Everything here is SYNTHETIC. The paths, fields and error codes are plausible
but invented — they exist so retrieval and action selection can be measured
before the real catalogue arrives, and so the format the backend team fills in
is unambiguous. Every card carries `status: example` for exactly that reason.

Run:  python seeds/build_api_catalog.py
"""

import io
import pathlib

OUT = pathlib.Path(__file__).parent / "api-catalog"

# ── Domains ─────────────────────────────────────────────────────────────────
#
# Shaped the way a merchant thinks about their day, not the way the backend is
# factored. A merchant does not know that offers and coupons are one service;
# they know "my discounts" and "my prices" are different things.

DOMAINS = {
    "catalog":   "Products, prices and stock — what the shop sells.",
    "offers":    "Discounts, deals and coupon codes.",
    "khata":     "Credit ledger — udhaar given, payments received, balances owed.",
    "orders":    "Incoming orders and their progress.",
    "payments":  "Money in and out — settlements, refunds, payment links.",
    "customers": "The people who buy from the shop.",
    "store":     "The shop itself — profile, timings, delivery area.",
    "reports":   "Summaries and insights about how the shop is doing.",
    # Real, key-free public APIs. Everything else here is synthetic and cannot
    # be called; these can, so an orchestrator can be tested end to end before
    # the merchant APIs exist.
    "weather":   "Weather, air quality and daylight for a place.",
    "reference": "Look-ups — exchange rates, crypto prices, words, holidays.",
}

# ── The catalogue ───────────────────────────────────────────────────────────

APIS = [

# ═══════════════════════════ catalog ═══════════════════════════

dict(
    api_id="catalog.product.create", domain="catalog", title="Add a product",
    method="POST", path="/v1/merchant/catalog/products",
    mpin_required=False, idempotent=False,
    body="""Adds a new product to the shop's catalogue so customers can see and
order it. The product goes live immediately unless it is saved as a draft.

Not for changing something that already exists — that is `catalog.product.update`
— and not for restocking, which is `catalog.stock.update`.""",
    fields=[
        dict(name="name", type="string", required=True, max_length=80,
             prompt="What is the product called?", example="Amul Butter 500g"),
        dict(name="price", type="number", required=True,
             prompt="What price should I put on it?", example=265),
        dict(name="unit", type="enum", required=False, values=["piece", "kg", "litre", "packet", "dozen"],
             prompt="Is that per piece, per kilo, or something else?", default="piece"),
        dict(name="stock_quantity", type="integer", required=False,
             prompt="How many do you have in stock?", default=0),
        dict(name="category", type="string", required=False,
             prompt="Which category does it belong in?", example="Dairy"),
    ],
    returns=dict(success=["product_id", "status"], errors={
        409: "A product with that name already exists in your catalogue.",
        422: "The price has to be greater than zero."}),
    utterances=[
        "add a new product",
        "मुझे नया प्रोडक्ट जोड़ना है",
        "put amul butter in my shop for 265",
        "i want to list a new item",
        "add maggi 12 rupees to my catalogue",
        "naya item add karna hai",
        "create a product listing",
        "i started selling a new thing, add it",
    ]),

dict(
    api_id="catalog.product.update", domain="catalog", title="Change a product",
    method="PATCH", path="/v1/merchant/catalog/products/{product_id}",
    mpin_required=False, idempotent=True,
    body="""Changes the details of a product that is already in the catalogue —
its name, price, unit or category. Only the fields you send are changed.

Use this for a price change. Adding something new is `catalog.product.create`,
and changing only the quantity in stock is `catalog.stock.update`.""",
    fields=[
        dict(name="product_id", type="string", required=True,
             prompt="Which product should I change?", example="prd_8812"),
        dict(name="price", type="number", required=False,
             prompt="What should the new price be?"),
        dict(name="name", type="string", required=False,
             prompt="What should it be called now?"),
    ],
    returns=dict(success=["product_id", "updated_fields"], errors={
        404: "I could not find that product in your catalogue."}),
    utterances=[
        "change the price of amul butter",
        "update my product price",
        "maggi ka rate badal do",
        "make the butter 270 instead",
        "i want to rename a product",
        "edit an item in my shop",
        "increase price of rice to 60",
    ]),

dict(
    api_id="catalog.product.list", domain="catalog", title="See my products",
    method="GET", path="/v1/merchant/catalog/products",
    mpin_required=False, idempotent=True,
    body="""Lists what is in the shop's catalogue, newest first, with prices and
stock levels. Can be narrowed to one category or to items that are out of stock.

This is about products. To see what customers have ordered, use `orders.list`.""",
    fields=[
        dict(name="category", type="string", required=False,
             prompt="Any particular category, or everything?"),
        dict(name="in_stock_only", type="boolean", required=False, default=False,
             prompt="Only the items you still have in stock?"),
    ],
    returns=dict(success=["products", "total"], errors={}),
    utterances=[
        "what products do i have",
        "show me my catalogue",
        "list everything in my shop",
        "mere saare products dikhao",
        "what am i selling right now",
        "show my items and prices",
        "which products are out of stock",
    ]),

dict(
    api_id="catalog.product.delete", domain="catalog", title="Remove a product",
    method="DELETE", path="/v1/merchant/catalog/products/{product_id}",
    mpin_required=True, idempotent=True,
    body="""Takes a product off the shop permanently. Past orders that contain it
are not affected.

If the item is only temporarily unavailable, set its stock to zero with
`catalog.stock.update` instead — deleting loses the product's history.""",
    fields=[
        dict(name="product_id", type="string", required=True,
             prompt="Which product should I remove?"),
    ],
    returns=dict(success=["product_id", "deleted"], errors={
        404: "I could not find that product.",
        409: "That product is in an order that is still open."}),
    utterances=[
        "delete a product",
        "remove maggi from my shop",
        "i don't sell this anymore, take it off",
        "product hata do",
        "stop showing this item to customers permanently",
        "delete an item from my catalogue",
    ]),

dict(
    api_id="catalog.stock.update", domain="catalog", title="Update stock",
    method="PUT", path="/v1/merchant/catalog/products/{product_id}/stock",
    mpin_required=False, idempotent=True,
    body="""Sets how many units of a product are left. Setting it to zero marks
the item out of stock, so customers can still see it but cannot order it.

This changes quantity only. To change the price, use `catalog.product.update`.""",
    fields=[
        dict(name="product_id", type="string", required=True,
             prompt="Which product?"),
        dict(name="quantity", type="integer", required=True,
             prompt="How many are left?", example=24),
    ],
    returns=dict(success=["product_id", "stock_quantity"], errors={
        404: "I could not find that product."}),
    utterances=[
        "update my stock",
        "i have 20 packets left",
        "mark this out of stock",
        "stock khatam ho gaya",
        "restock the butter, 50 more came in",
        "set quantity to 12",
        "this item is finished",
    ]),

# ═══════════════════════════ offers ═══════════════════════════
#
# Modelled on the real AdGrid contract, not invented. A merchant says "offer"
# for two different things, and the backend treats them as two different
# payloads behind ONE MPIN-gated endpoint, discriminated by `purpose`:
#
#   POST /v1/merchant/{merchantId}/mpin-actions
#     purpose = DEAL_CREATE      -> CreateDealRequest     -> OfferResponse
#     purpose = DISCOUNT_CREATE  -> CreateDiscountRequest -> DiscountResponse
#
# So the path cannot identify the action. That is what `constants` is for.
#
# This is also the hardest selection problem in the catalogue: one merchant word
# covering two APIs. A deal is structural — buy one get one, a bundle, a free
# item. A discount is monetary — a percentage or an amount off.

dict(
    api_id="offers.deal.create", domain="offers", title="Create a deal",
    method="POST", path="/v1/merchant/{merchantId}/mpin-actions",
    mpin_required=True, idempotent=False,
    constants={"purpose": "DEAL_CREATE"},
    body_root="payload",
    body="""Creates a deal — an offer where the customer gets extra goods rather
than money off. Buy one get one, a bundle at a set price, or a free item over a
bill threshold.

A deal changes what the customer receives. If the customer is getting money off
instead — a percentage or a flat amount — that is `offers.discount.create`.
Merchants call both of these "offers", so ask which they mean when it is not
clear from the numbers they gave.""",
    fields=[
        dict(name="title", type="string", required=True,
             prompt="What should the deal be called?", example="Buy 1 Get 1 Coffee"),
        dict(name="offerType", type="enum", required=True,
             values=["BOGO", "BUNDLE_DEAL", "FREE_ITEM"],
             prompt="Is it buy-one-get-one, a bundle, or a free item?"),
        dict(name="config", type="object", required=True,
             prompt="Which item, and how many?",
             example='{"appliesOn":"SAME_ITEM","buyItemName":"Cappuccino","buyQty":1,"getQty":1}'),
        dict(name="showOnShopProfile", type="boolean", required=True,
             prompt="Should it show on your shop profile?"),
        dict(name="description", type="string", required=False,
             prompt="Anything to add about it?"),
        dict(name="validity", type="object", required=False,
             prompt="Until when should it run?",
             example='{"isLimited":true,"endDate":"2026-08-31T23:59:59Z"}'),
        dict(name="redeemLimit", type="integer", required=False,
             prompt="How many times can one customer use it?"),
        dict(name="totalRedeemLimit", type="integer", required=False,
             prompt="How many customers in total?"),
        dict(name="target", type="object", required=False,
             prompt="Everyone, or particular customers?"),
    ],
    returns=dict(success=["id", "offerKind", "offerType", "status", "validTill"], errors={
        400: "Something in the deal was not valid — check the item name and quantities.",
        401: "That MPIN was not right."}),
    utterances=[
        "buy one get one free on coffee",
        "start a bogo offer",
        "ek ke saath ek free karna hai",
        "free dessert on bills above 500",
        "make a combo deal on my items",
        "bundle two items together at one price",
        "give a free item with every order over 300",
        "BOGO offer chalu karo",
    ]),

dict(
    api_id="offers.discount.create", domain="offers", title="Create a discount",
    method="POST", path="/v1/merchant/{merchantId}/mpin-actions",
    mpin_required=True, idempotent=False,
    constants={"purpose": "DISCOUNT_CREATE"},
    body_root="payload",
    body="""Creates a discount — an offer that takes money off the bill, either a
percentage or a flat amount. Can carry a minimum bill, a happy-hours window, and
caps on how often it is used.

A discount changes the price. If the customer is getting extra goods instead —
buy one get one, a bundle, a free item — that is `offers.deal.create`. Merchants
call both "offers", so ask which they mean when it is not clear.""",
    fields=[
        dict(name="name", type="string", required=True,
             prompt="What should the discount be called?", example="Flat 10% Off"),
        dict(name="discountType", type="enum", required=True,
             values=["PERCENTAGE", "FLAT"],
             prompt="A percentage off, or a flat amount off?"),
        dict(name="discountValue", type="number", required=True,
             prompt="How much off?", example=10),
        dict(name="maxAmount", type="number", required=False,
             prompt="Cap the saving at any amount?"),
        dict(name="rules", type="object", required=False,
             prompt="Any minimum bill for it to apply?",
             example='{"appliesOn":"PAYMENT_AMOUNT","minBillAmount":500}'),
        dict(name="validity", type="object", required=False,
             prompt="Until when should it run?"),
        dict(name="happyHours", type="object", required=False,
             prompt="Only during certain hours?", example='{"startTime":"16:00","endTime":"19:00"}'),
        dict(name="appliesOnWeekends", type="boolean", required=False,
             prompt="Should the happy hours apply at weekends too?"),
        dict(name="showOnShopProfile", type="boolean", required=False,
             prompt="Should it show on your shop profile?"),
        dict(name="redeemLimit", type="integer", required=False,
             prompt="How many times can one customer use it?"),
        dict(name="totalRedeemLimit", type="integer", required=False,
             prompt="How many customers in total?"),
        dict(name="target", type="object", required=False,
             prompt="Everyone, or particular customers?"),
    ],
    returns=dict(success=["id", "offerKind", "discountType", "status", "validTill"], errors={
        400: "A percentage cannot be over 100, and a flat amount cannot exceed the minimum bill.",
        401: "That MPIN was not right."}),
    utterances=[
        "start a 20% off sale",
        "flat 100 rupees off above 500",
        "मुझे 20% की छूट देनी है",
        "discount lagana hai",
        "10 percent off during happy hours",
        "put my whole shop on discount this weekend",
        "give money off on orders above 1000",
        "sabko 15 percent kam kar do",
    ]),

dict(
    api_id="offers.list", domain="offers", title="See my offers",
    method="GET", path="/v1/merchant/{merchantId}/offers",
    mpin_required=False, idempotent=True,
    body="""Lists the shop's offers — deals and discounts together — with their
status and how much each has been used. `offerKind` narrows it to one or the
other.

This reads them. Making one is `offers.deal.create` or
`offers.discount.create`.""",
    fields=[
        dict(name="offerKind", type="enum", required=False, values=["DEAL", "DISCOUNT"],
             prompt="Deals, discounts, or both?", **{"in": "query"}),
        dict(name="status", type="enum", required=False,
             values=["DRAFT", "SCHEDULED", "ACTIVE", "INACTIVE", "EXPIRED"],
             prompt="Running ones, upcoming ones, or all of them?", **{"in": "query"}),
    ],
    returns=dict(success=["offers", "total"], errors={}),
    utterances=[
        "what offers do i have running",
        "show my discounts and deals",
        "kaun se offer chal rahe hain",
        "list all my sales",
        "do i have any offer on right now",
        "show me my past offers",
    ]),

dict(
    api_id="offers.update", domain="offers", title="Change an offer",
    method="PATCH", path="/v1/merchant/{merchantId}/offers/{offerId}",
    mpin_required=False, idempotent=True,
    body="""Changes an offer that already exists — its validity, its caps, or
whether it shows on the shop profile. Works for both deals and discounts.

For a brand new one use `offers.deal.create` or `offers.discount.create`. To end
one early use `offers.deactivate`.""",
    fields=[
        dict(name="offerId", type="string", required=True,
             prompt="Which offer should I change?", **{"in": "path"}),
        dict(name="validity", type="object", required=False,
             prompt="When should it end now?"),
        dict(name="redeemLimit", type="integer", required=False,
             prompt="What should the per-customer limit be?"),
        dict(name="showOnShopProfile", type="boolean", required=False,
             prompt="Show it on your shop profile?"),
    ],
    returns=dict(success=["id", "status", "validTill"], errors={
        404: "I could not find that offer.",
        409: "That offer has already expired and cannot be changed."}),
    utterances=[
        "extend my sale by a week",
        "edit the diwali offer",
        "offer ki date badha do",
        "change the limit on my running offer",
        "modify an offer i already made",
        "my offer should end tomorrow instead",
    ]),

dict(
    api_id="offers.deactivate", domain="offers", title="Stop an offer",
    method="POST", path="/v1/merchant/{merchantId}/offers/{offerId}/deactivate",
    mpin_required=False, idempotent=True,
    body="""Ends a running offer straight away, deal or discount. It stays in the
history with everything it earned, it simply stops applying to new orders.

This stops it. To change it rather than stop it, use `offers.update`.""",
    fields=[
        dict(name="offerId", type="string", required=True,
             prompt="Which offer should I stop?", **{"in": "path"}),
    ],
    returns=dict(success=["id", "status"], errors={
        404: "I could not find that offer."}),
    utterances=[
        "stop my offer",
        "end the sale now",
        "offer band kar do",
        "cancel the discount i started",
        "turn off my diwali deal",
        "i don't want the offer anymore",
    ]),

# ═══════════════════════════ khata ═══════════════════════════

dict(
    api_id="khata.entry.create", domain="khata", title="Record udhaar given",
    method="POST", path="/v1/merchant/khata/entries",
    mpin_required=False, idempotent=False,
    body="""Records credit given to a customer — goods taken now, money to be paid
later. The amount is added to what that customer owes.

This records money the customer now owes. Money coming back in is
`khata.entry.settle`.""",
    fields=[
        dict(name="customer_name", type="string", required=True,
             prompt="Whose khata should I add this to?", example="Ramesh"),
        dict(name="amount", type="number", required=True,
             prompt="How much did they take on credit?", example=450),
        dict(name="note", type="string", required=False,
             prompt="Anything to note about it?", example="2 kg sugar, 1 kg dal"),
        dict(name="entry_date", type="date", required=False, default="today",
             prompt="Was this today, or another day?"),
    ],
    returns=dict(success=["entry_id", "customer_balance"], errors={
        422: "The amount has to be more than zero."}),
    utterances=[
        "ramesh took 500 rupees of goods on credit",
        "add udhaar for a customer",
        "khata mein likh do 450 rupaye",
        "note down that he owes me 200",
        "record credit given today",
        "customer took saman on udhaar",
        "write 300 in ramesh's account",
    ]),

dict(
    api_id="khata.entry.settle", domain="khata", title="Record a payment received",
    method="POST", path="/v1/merchant/khata/entries/settle",
    mpin_required=False, idempotent=False,
    body="""Records money a customer has paid back against their khata. The amount
is subtracted from what they owe; a partial payment is fine.

This is money coming in against credit already given. Recording new credit is
`khata.entry.create`.""",
    fields=[
        dict(name="customer_name", type="string", required=True,
             prompt="Who paid you?"),
        dict(name="amount", type="number", required=True,
             prompt="How much did they pay?"),
        dict(name="payment_mode", type="enum", required=False,
             values=["cash", "upi", "card", "other"], default="cash",
             prompt="Cash, UPI, or something else?"),
    ],
    returns=dict(success=["entry_id", "customer_balance"], errors={
        404: "I do not have a khata for that customer.",
        422: "That is more than they owe."}),
    utterances=[
        "ramesh paid me 300",
        "customer settled his udhaar",
        "paise mil gaye, khata update karo",
        "record a payment against credit",
        "he gave back 500 today",
        "mark the khata as paid",
        "received 200 from suresh by upi",
    ]),

dict(
    api_id="khata.balance.get", domain="khata", title="Check what a customer owes",
    method="GET", path="/v1/merchant/khata/customers/{customer_id}/balance",
    mpin_required=False, idempotent=True,
    body="""Shows how much one customer currently owes, with the entries that make
up the total.

For everyone at once, use `khata.customer.list`.""",
    fields=[
        dict(name="customer_id", type="string", required=True,
             prompt="Whose balance do you want to see?"),
    ],
    returns=dict(success=["customer_id", "balance", "entries"], errors={
        404: "I do not have a khata for that customer."}),
    utterances=[
        "how much does ramesh owe me",
        "check a customer's khata balance",
        "ramesh ka kitna baaki hai",
        "what is pending from this customer",
        "show me his account",
        "how much udhaar is left on suresh",
    ]),

dict(
    api_id="khata.customer.list", domain="khata", title="See all khata balances",
    method="GET", path="/v1/merchant/khata/customers",
    mpin_required=False, idempotent=True,
    body="""Lists every customer with an open khata and what each one owes, largest
first. Optionally only those overdue past a number of days.

This is the whole ledger. For one person, use `khata.balance.get`.""",
    fields=[
        dict(name="overdue_days", type="integer", required=False,
             prompt="Only the ones overdue past a certain number of days?"),
    ],
    returns=dict(success=["customers", "total_outstanding"], errors={}),
    utterances=[
        "how much money is owed to me in total",
        "show all khata accounts",
        "kis kis ka udhaar baaki hai",
        "list everyone who owes me money",
        "total outstanding on my khata",
        "who has not paid me in 30 days",
    ]),

dict(
    api_id="khata.reminder.send", domain="khata", title="Send a payment reminder",
    method="POST", path="/v1/merchant/khata/reminders",
    mpin_required=False, idempotent=False,
    body="""Sends a customer a polite reminder about what they owe, over WhatsApp
or SMS, with the amount and a payment link.

This asks them to pay. Recording that they did is `khata.entry.settle`.""",
    fields=[
        dict(name="customer_id", type="string", required=True,
             prompt="Who should I remind?"),
        dict(name="channel", type="enum", required=False, values=["whatsapp", "sms"],
             default="whatsapp", prompt="On WhatsApp or by SMS?"),
    ],
    returns=dict(success=["reminder_id", "sent_at", "channel"], errors={
        404: "I do not have a khata for that customer.",
        429: "A reminder already went out to them today."}),
    utterances=[
        "remind ramesh to pay",
        "send a payment reminder",
        "yaad dila do udhaar ka",
        "message my customers who owe money",
        "send whatsapp reminder for pending payment",
        "ask him for the money politely",
    ]),

# ═══════════════════════════ orders ═══════════════════════════

dict(
    api_id="orders.list", domain="orders", title="See my orders",
    method="GET", path="/v1/merchant/orders",
    mpin_required=False, idempotent=True,
    body="""Lists orders customers have placed, newest first, with what was ordered
and how much. Can be narrowed to a status or a date range.

This is what customers have bought. What the shop sells is
`catalog.product.list`.""",
    fields=[
        dict(name="status", type="enum", required=False,
             values=["new", "preparing", "ready", "delivered", "cancelled"],
             prompt="Which kind of orders — new ones, or everything?"),
        dict(name="from_date", type="date", required=False,
             prompt="From which date?"),
    ],
    returns=dict(success=["orders", "total"], errors={}),
    utterances=[
        "show me today's orders",
        "how many orders came in",
        "aaj ke orders dikhao",
        "list my pending orders",
        "what orders do i have to deliver",
        "show orders from yesterday",
        "koi naya order aaya kya",
    ]),

dict(
    api_id="orders.get", domain="orders", title="See one order",
    method="GET", path="/v1/merchant/orders/{order_id}",
    mpin_required=False, idempotent=True,
    body="""Shows everything about a single order — the items, the customer, the
amount, the payment status and the delivery address.""",
    fields=[
        dict(name="order_id", type="string", required=True,
             prompt="Which order number?"),
    ],
    returns=dict(success=["order"], errors={404: "I could not find that order."}),
    utterances=[
        "show me order 4471",
        "what was in that order",
        "open this order for me",
        "order ka detail dikhao",
        "who placed this order and what did they buy",
        "check details of a particular order",
    ]),

dict(
    api_id="orders.status.update", domain="orders", title="Update an order's status",
    method="PUT", path="/v1/merchant/orders/{order_id}/status",
    mpin_required=False, idempotent=True,
    body="""Moves an order along — accepted, being prepared, ready, out for
delivery, delivered. The customer is notified at each step.

To stop an order entirely, use `orders.cancel`.""",
    fields=[
        dict(name="order_id", type="string", required=True,
             prompt="Which order?"),
        dict(name="status", type="enum", required=True,
             values=["accepted", "preparing", "ready", "out_for_delivery", "delivered"],
             prompt="What stage is it at now?"),
    ],
    returns=dict(success=["order_id", "status", "customer_notified"], errors={
        404: "I could not find that order.",
        409: "That order was cancelled and cannot be moved on."}),
    utterances=[
        "mark this order as delivered",
        "order ready hai",
        "accept the order",
        "change order status to out for delivery",
        "this one is packed and ready",
        "update the order stage",
        "maine deliver kar diya",
    ]),

dict(
    api_id="orders.cancel", domain="orders", title="Cancel an order",
    method="POST", path="/v1/merchant/orders/{order_id}/cancel",
    mpin_required=True, idempotent=True,
    body="""Cancels an order and tells the customer why. If it was already paid
for, the money goes back automatically.

This cancels the order. Refunding a delivered order without cancelling is
`payments.refund.create`.""",
    fields=[
        dict(name="order_id", type="string", required=True,
             prompt="Which order should I cancel?"),
        dict(name="reason", type="enum", required=True,
             values=["out_of_stock", "customer_request", "shop_closed", "other"],
             prompt="Why is it being cancelled?"),
    ],
    returns=dict(success=["order_id", "cancelled_at", "refund_initiated"], errors={
        404: "I could not find that order.",
        409: "That order is already delivered."}),
    utterances=[
        "cancel this order",
        "i can't fulfil order 4471",
        "order cancel kar do",
        "the customer wants to cancel",
        "stop this order, item is out of stock",
        "cancel an order and refund it",
    ]),

# ═══════════════════════════ payments ═══════════════════════════

dict(
    api_id="payments.link.create", domain="payments", title="Create a payment link",
    method="POST", path="/v1/merchant/payments/links",
    mpin_required=False, idempotent=False,
    body="""Creates a link the merchant can send to a customer to collect money.
Works for any amount and is not tied to an order.

For collecting against a khata balance, `khata.reminder.send` includes a link
already.""",
    fields=[
        dict(name="amount", type="number", required=True,
             prompt="How much should the link be for?"),
        dict(name="description", type="string", required=False,
             prompt="What is the payment for?"),
        dict(name="expires_in_hours", type="integer", required=False, default=24,
             prompt="How long should the link stay valid?"),
    ],
    returns=dict(success=["link_id", "url", "expires_at"], errors={
        422: "The amount has to be at least ₹1."}),
    utterances=[
        "create a payment link for 500",
        "send a link so the customer can pay",
        "payment link banao",
        "i need a link to collect money",
        "make a upi payment link",
        "generate a link for 1200 rupees",
    ]),

dict(
    api_id="payments.settlement.list", domain="payments", title="See my settlements",
    method="GET", path="/v1/merchant/payments/settlements",
    mpin_required=False, idempotent=True,
    body="""Lists the payouts that have landed in the merchant's bank account, with
what each one covers and any fees deducted.

This is money already sent to the bank. Individual customer payments are
`payments.transaction.list`.""",
    fields=[
        dict(name="from_date", type="date", required=False,
             prompt="From which date?"),
    ],
    returns=dict(success=["settlements", "total_settled"], errors={}),
    utterances=[
        "when will i get my money",
        "show my settlements",
        "bank mein paise kab aayenge",
        "how much has been paid out to me",
        "list my payouts",
        "settlement history dikhao",
    ]),

dict(
    api_id="payments.refund.create", domain="payments", title="Refund a payment",
    method="POST", path="/v1/merchant/payments/refunds",
    mpin_required=True, idempotent=False,
    body="""Sends money back to a customer for a payment already taken, in full or
in part. It reaches them in three to five working days.

If the order itself should be stopped, `orders.cancel` refunds automatically —
use this one for a refund without a cancellation.""",
    fields=[
        dict(name="transaction_id", type="string", required=True,
             prompt="Which payment should I refund?"),
        dict(name="amount", type="number", required=False,
             prompt="The full amount, or only part of it?"),
        dict(name="reason", type="string", required=True,
             prompt="What is the reason for the refund?"),
    ],
    returns=dict(success=["refund_id", "amount", "expected_by"], errors={
        404: "I could not find that payment.",
        409: "That payment has already been refunded.",
        422: "The refund is larger than the original payment."}),
    utterances=[
        "refund this customer",
        "give the money back",
        "paise wapas karne hain",
        "process a refund for order 4471",
        "return 200 rupees to the customer",
        "partial refund kar do",
    ]),

dict(
    api_id="payments.transaction.list", domain="payments", title="See customer payments",
    method="GET", path="/v1/merchant/payments/transactions",
    mpin_required=False, idempotent=True,
    body="""Lists individual payments customers have made, with the mode and whether
each one succeeded.

These are payments coming in. Money reaching the bank account is
`payments.settlement.list`.""",
    fields=[
        dict(name="status", type="enum", required=False,
             values=["success", "failed", "pending"],
             prompt="All of them, or only the failed ones?"),
        dict(name="from_date", type="date", required=False,
             prompt="From which date?"),
    ],
    returns=dict(success=["transactions", "total"], errors={}),
    utterances=[
        "show me all payments received",
        "which payments failed",
        "how much did customers pay today",
        "payment history dikhao",
        "list transactions from this week",
        "kitna online payment aaya",
    ]),

# ═══════════════════════════ customers ═══════════════════════════

dict(
    api_id="customers.list", domain="customers", title="See my customers",
    method="GET", path="/v1/merchant/customers",
    mpin_required=False, idempotent=True,
    body="""Lists the people who buy from the shop, with how much each has spent and
when they last ordered.

This is who they are. What they owe on credit is `khata.customer.list`.""",
    fields=[
        dict(name="sort_by", type="enum", required=False,
             values=["recent", "total_spent", "order_count"], default="recent",
             prompt="Sorted by most recent, or by how much they spend?"),
    ],
    returns=dict(success=["customers", "total"], errors={}),
    utterances=[
        "show me my customers",
        "who buys from my shop",
        "mere customers ki list",
        "list all my buyers",
        "who are my regular customers",
        "how many customers do i have",
    ]),

dict(
    api_id="customers.get", domain="customers", title="See one customer",
    method="GET", path="/v1/merchant/customers/{customer_id}",
    mpin_required=False, idempotent=True,
    body="""Shows one customer — their contact details, order history and what they
usually buy.""",
    fields=[
        dict(name="customer_id", type="string", required=True,
             prompt="Which customer?"),
    ],
    returns=dict(success=["customer"], errors={404: "I could not find that customer."}),
    utterances=[
        "tell me about this customer",
        "show ramesh's details",
        "customer ka profile dikhao",
        "what does this person usually order",
        "open a customer's history",
    ]),

dict(
    api_id="customers.create", domain="customers", title="Add a customer",
    method="POST", path="/v1/merchant/customers",
    mpin_required=False, idempotent=False,
    body="""Adds a customer by hand — useful for someone who buys in the shop rather
than through the app, especially before opening a khata for them.""",
    fields=[
        dict(name="name", type="string", required=True,
             prompt="What is the customer's name?"),
        dict(name="phone", type="string", required=True,
             prompt="What is their phone number?"),
    ],
    returns=dict(success=["customer_id"], errors={
        409: "You already have a customer with that phone number."}),
    utterances=[
        "add a new customer",
        "naya customer add karo",
        "save this person's number",
        "create a customer record for ramesh",
        "i want to add someone to my customer list",
    ]),

# ═══════════════════════════ store ═══════════════════════════

dict(
    api_id="store.profile.update", domain="store", title="Change shop details",
    method="PATCH", path="/v1/merchant/store/profile",
    mpin_required=False, idempotent=True,
    body="""Changes what customers see about the shop — its name, description,
address, phone number or photo.

For opening hours use `store.timings.update`; for the delivery area use
`store.delivery.update`.""",
    fields=[
        dict(name="store_name", type="string", required=False,
             prompt="What should the shop be called?"),
        dict(name="phone", type="string", required=False,
             prompt="Which number should customers call?"),
        dict(name="address", type="string", required=False,
             prompt="What is the shop's address?"),
    ],
    returns=dict(success=["updated_fields"], errors={}),
    utterances=[
        "change my shop name",
        "update my store details",
        "dukaan ka naam badalna hai",
        "change the phone number customers see",
        "edit my shop address",
        "update my store profile picture",
    ]),

dict(
    api_id="store.timings.update", domain="store", title="Set opening hours",
    method="PUT", path="/v1/merchant/store/timings",
    mpin_required=False, idempotent=True,
    body="""Sets when the shop is open. Outside these hours customers can browse but
not order.

For a one-off closure like a festival, use `store.holiday.set`.""",
    fields=[
        dict(name="opens_at", type="time", required=True,
             prompt="What time do you open?", example="09:00"),
        dict(name="closes_at", type="time", required=True,
             prompt="What time do you close?", example="21:00"),
        dict(name="closed_days", type="array", required=False,
             prompt="Any weekly day off?"),
    ],
    returns=dict(success=["timings"], errors={
        422: "The closing time has to be after the opening time."}),
    utterances=[
        "change my shop timings",
        "i open at 9 and close at 9",
        "dukaan ka time set karna hai",
        "set my opening hours",
        "my shop is closed on sundays",
        "update store open close time",
    ]),

dict(
    api_id="store.holiday.set", domain="store", title="Mark a holiday",
    method="POST", path="/v1/merchant/store/holidays",
    mpin_required=False, idempotent=False,
    body="""Closes the shop for a day or a range of days. Customers see a note
saying when it reopens.

This is for particular dates. A regular weekly day off belongs in
`store.timings.update`.""",
    fields=[
        dict(name="from_date", type="date", required=True,
             prompt="From which date will you be closed?"),
        dict(name="to_date", type="date", required=False,
             prompt="Until when?"),
        dict(name="reason", type="string", required=False,
             prompt="Should I tell customers why?"),
    ],
    returns=dict(success=["holiday_id", "from_date", "to_date"], errors={}),
    utterances=[
        "my shop will be closed tomorrow",
        "mark holiday for diwali",
        "chutti hai kal",
        "close my store for three days",
        "i am going out of town, shut the shop",
        "set a holiday on my store",
    ]),

dict(
    api_id="store.delivery.update", domain="store", title="Set delivery settings",
    method="PUT", path="/v1/merchant/store/delivery",
    mpin_required=False, idempotent=True,
    body="""Sets how far the shop delivers, the delivery charge, and any minimum
order for free delivery.""",
    fields=[
        dict(name="radius_km", type="number", required=True,
             prompt="How far do you deliver, in kilometres?"),
        dict(name="delivery_fee", type="number", required=False,
             prompt="What do you charge for delivery?"),
        dict(name="free_above", type="number", required=False,
             prompt="Free delivery above what order value?"),
    ],
    returns=dict(success=["delivery"], errors={}),
    utterances=[
        "change my delivery charges",
        "i deliver up to 5 km",
        "delivery ka charge set karna hai",
        "free delivery above 500",
        "set my delivery radius",
        "update delivery settings for my shop",
    ]),

# ═══════════════════════════ reports ═══════════════════════════

dict(
    api_id="reports.sales.summary", domain="reports", title="Sales summary",
    method="GET", path="/v1/merchant/reports/sales",
    mpin_required=False, idempotent=True,
    body="""Totals up sales over a period — how much came in, how many orders, the
average order value, and the change against the period before.

This is the money view. Order-by-order detail is `orders.list`.""",
    fields=[
        dict(name="period", type="enum", required=False,
             values=["today", "week", "month", "custom"], default="today",
             prompt="For today, this week, or this month?"),
    ],
    returns=dict(success=["total_sales", "order_count", "average_order_value", "change_percent"],
                 errors={}),
    utterances=[
        "how much did i sell today",
        "aaj ki sale kitni hui",
        "show me my sales report",
        "what were my earnings this month",
        "give me a summary of this week",
        "how is my business doing",
        "total revenue this month",
    ]),

dict(
    api_id="reports.top-products", domain="reports", title="Best selling products",
    method="GET", path="/v1/merchant/reports/top-products",
    mpin_required=False, idempotent=True,
    body="""Ranks products by how much they sold over a period, so the merchant can
see what moves and what does not.""",
    fields=[
        dict(name="period", type="enum", required=False,
             values=["week", "month", "quarter"], default="month",
             prompt="Over what period?"),
        dict(name="limit", type="integer", required=False, default=10,
             prompt="How many should I show?"),
    ],
    returns=dict(success=["products"], errors={}),
    utterances=[
        "what sells the most in my shop",
        "which product is doing well",
        "sabse zyada kya bik raha hai",
        "show me my best sellers",
        "top selling items this month",
        "which items are not selling",
    ]),

dict(
    api_id="reports.customer-insights", domain="reports", title="Customer insights",
    method="GET", path="/v1/merchant/reports/customers",
    mpin_required=False, idempotent=True,
    body="""Shows patterns across customers — new against returning, who spends most,
and who has stopped coming back.

This is the analysis. The plain list of customers is `customers.list`.""",
    fields=[
        dict(name="period", type="enum", required=False,
             values=["month", "quarter", "year"], default="month",
             prompt="Over what period?"),
    ],
    returns=dict(success=["new_customers", "returning_customers", "top_spenders", "lapsed"],
                 errors={}),
    utterances=[
        "how many new customers did i get",
        "which customers spend the most",
        "who has stopped buying from me",
        "customer insights dikhao",
        "am i getting repeat customers",
        "show me customer trends",
    ]),

# ═══════════════════════════ weather ═══════════════════════════
#
# Real, public, key-free APIs. Everything above is synthetic and cannot be
# called; these can. They exist so an orchestrator can be tested end to end —
# resolve a message, build the request, actually hit it, and answer from a real
# response — before the merchant APIs exist to call.
#
# All verified responding on 19 August 2026. They need a User-Agent header;
# several of them return 403 to a bare urllib default.

dict(
    api_id="weather.current", domain="weather", title="Current weather",
    method="GET", path="/v1/forecast",
    base_url="https://api.open-meteo.com",
    real=True, mpin_required=False, idempotent=True,
    constants={"current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"},
    body="""Current temperature, humidity, wind and conditions for a latitude and
longitude, from Open-Meteo. No API key.

It needs coordinates, not a place name. Turn a name into coordinates with
`weather.geocode` first.""",
    fields=[
        dict(name="latitude", type="number", required=True,
             prompt="Which place? I need its latitude.", example=28.61, **{"in": "query"}),
        dict(name="longitude", type="number", required=True,
             prompt="And its longitude?", example=77.21, **{"in": "query"}),
        dict(name="timezone", type="string", required=False,
             prompt="Which timezone should times be in?", example="Asia/Kolkata",
             **{"in": "query"}),
    ],
    returns=dict(success=["current.temperature_2m", "current.weather_code",
                          "current.wind_speed_10m"],
                 errors={400: "Those coordinates were not valid."}),
    utterances=[
        "what's the weather like",
        "aaj mausam kaisa hai",
        "is it raining right now",
        "how hot is it outside",
        "temperature kya hai abhi",
        "tell me the current weather",
        "kitni garmi hai aaj",
    ]),

dict(
    api_id="weather.geocode", domain="weather", title="Find a place's coordinates",
    method="GET", path="/v1/search",
    base_url="https://geocoding-api.open-meteo.com",
    real=True, mpin_required=False, idempotent=True,
    body="""Turns a place name into coordinates, country and timezone. From
Open-Meteo. No API key.

Usually the first step before `weather.current` or `weather.air_quality`, both of
which need latitude and longitude rather than a name.""",
    fields=[
        dict(name="name", type="string", required=True,
             prompt="Which town or city?", example="Delhi", **{"in": "query"}),
        dict(name="count", type="integer", required=False, default=1,
             prompt="How many matches should I bring back?", **{"in": "query"}),
    ],
    returns=dict(success=["results[].latitude", "results[].longitude",
                          "results[].country", "results[].timezone"],
                 errors={}),
    utterances=[
        "where is bengaluru exactly",
        "find the coordinates of a city",
        "look up a place",
        "what are the lat long for mumbai",
        "geocode this town for me",
    ]),

dict(
    api_id="weather.air_quality", domain="weather", title="Air quality",
    method="GET", path="/v1/air-quality",
    base_url="https://air-quality-api.open-meteo.com",
    real=True, mpin_required=False, idempotent=True,
    constants={"current": "pm2_5,pm10,us_aqi"},
    body="""Current PM2.5, PM10 and US AQI for a latitude and longitude, from
Open-Meteo. No API key.

Air quality, not weather — for temperature and rain use `weather.current`.""",
    fields=[
        dict(name="latitude", type="number", required=True,
             prompt="Which place? I need its latitude.", example=28.61, **{"in": "query"}),
        dict(name="longitude", type="number", required=True,
             prompt="And its longitude?", example=77.21, **{"in": "query"}),
    ],
    returns=dict(success=["current.pm2_5", "current.pm10", "current.us_aqi"], errors={}),
    utterances=[
        "how bad is the air today",
        "what is the aqi right now",
        "pollution kaisa hai aaj",
        "is the air quality safe outside",
        "check pm2.5 levels",
    ]),

dict(
    api_id="weather.sun_times", domain="weather", title="Sunrise and sunset",
    method="GET", path="/json",
    base_url="https://api.sunrise-sunset.org",
    real=True, mpin_required=False, idempotent=True,
    constants={"formatted": "0"},
    body="""Sunrise, sunset, solar noon and day length for a latitude and
longitude. No API key. Times come back in UTC when formatted=0.""",
    fields=[
        dict(name="lat", type="number", required=True,
             prompt="Which place? I need its latitude.", example=28.61, **{"in": "query"}),
        dict(name="lng", type="number", required=True,
             prompt="And its longitude?", example=77.21, **{"in": "query"}),
        dict(name="date", type="date", required=False, default="today",
             prompt="Which date?", **{"in": "query"}),
    ],
    returns=dict(success=["results.sunrise", "results.sunset", "results.day_length"],
                 errors={}),
    utterances=[
        "what time does the sun set today",
        "sunrise kab hoga",
        "when does it get dark",
        "how long is daylight today",
        "tell me sunset time",
    ]),

# ═══════════════════════════ reference ═══════════════════════════

dict(
    api_id="reference.exchange_rate", domain="reference", title="Currency exchange rate",
    method="GET", path="/latest",
    base_url="https://api.frankfurter.app",
    real=True, mpin_required=False, idempotent=True,
    body="""Reference exchange rates published by the European Central Bank, via
Frankfurter. No API key. Rates update on working days only.""",
    fields=[
        dict(name="from", type="string", required=True,
             prompt="Converting from which currency?", example="USD", **{"in": "query"}),
        dict(name="to", type="string", required=False,
             prompt="Into which currency?", example="INR", **{"in": "query"}),
        dict(name="amount", type="number", required=False, default=1,
             prompt="How much?", **{"in": "query"}),
    ],
    returns=dict(success=["base", "date", "rates"], errors={
        404: "One of those currency codes is not recognised."}),
    utterances=[
        "what is the dollar rate today",
        "convert 100 usd to rupees",
        "dollar ka rate kya hai",
        "exchange rate for euro",
        "how many rupees is one pound",
    ]),

dict(
    api_id="reference.crypto_price", domain="reference", title="Crypto price",
    method="GET", path="/api/v3/simple/price",
    base_url="https://api.coingecko.com",
    real=True, mpin_required=False, idempotent=True,
    body="""Current price of a cryptocurrency in one or more currencies, from
CoinGecko's public tier. No API key, but it is rate limited — expect a 429 under
load.""",
    fields=[
        dict(name="ids", type="string", required=True,
             prompt="Which coin?", example="bitcoin", **{"in": "query"}),
        dict(name="vs_currencies", type="string", required=True,
             prompt="Priced in which currency?", example="inr", **{"in": "query"}),
    ],
    returns=dict(success=["{coin}.{currency}"], errors={
        429: "CoinGecko is rate limiting — try again in a minute."}),
    utterances=[
        "what is bitcoin trading at",
        "bitcoin ka rate batao",
        "price of ethereum in rupees",
        "how much is one bitcoin today",
        "crypto price check",
    ]),

dict(
    api_id="reference.define_word", domain="reference", title="Define a word",
    method="GET", path="/api/v2/entries/en/{word}",
    base_url="https://api.dictionaryapi.dev",
    real=True, mpin_required=False, idempotent=True,
    body="""English dictionary definition, pronunciation and examples for a word.
No API key.""",
    fields=[
        dict(name="word", type="string", required=True,
             prompt="Which word?", example="discount", **{"in": "path"}),
    ],
    returns=dict(success=["[].meanings[].definitions[].definition", "[].phonetic"],
                 errors={404: "No definition found for that word."}),
    utterances=[
        "what does this word mean",
        "define invoice for me",
        "iska matlab kya hai",
        "look up the meaning of a word",
        "spelling and meaning of a word",
    ]),

dict(
    api_id="reference.public_holidays", domain="reference", title="Public holidays",
    method="GET", path="/api/v3/PublicHolidays/{year}/{countryCode}",
    base_url="https://date.nager.at",
    real=True, mpin_required=False, idempotent=True,
    body="""Public holidays for a country and year, from Nager.Date. No API key.

Coverage is uneven — some countries return 204 with no body rather than a list.
Treat an empty response as "not covered", not as "no holidays".""",
    fields=[
        dict(name="year", type="integer", required=True,
             prompt="Which year?", example=2026, **{"in": "path"}),
        dict(name="countryCode", type="string", required=True,
             prompt="Which country? I need the two-letter code.", example="US",
             **{"in": "path"}),
    ],
    returns=dict(success=["[].date", "[].localName", "[].name"], errors={
        204: "That country and year are not covered."}),
    utterances=[
        "when is the next public holiday",
        "list the holidays this year",
        "chutti kab kab hai",
        "what are the bank holidays",
        "show me the holiday calendar",
    ]),

]


# ── Emit ────────────────────────────────────────────────────────────────────

def yaml_scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if any(c in text for c in ':#{}[]&*?|>!%@`"\'') or text.strip() != text or not text:
        return '"%s"' % text.replace('"', '\\"')
    return text


def render(api: dict) -> str:
    lines = ["---", "type: api"]
    if api.get("real"):
        lines.append("status: live  # a real public API — this one can actually be called")
    else:
        lines.append("status: example  # synthetic seed data — replace with the real contract")
    for key in ("api_id", "domain", "method", "path"):
        lines.append(f"{key}: {yaml_scalar(api[key])}")
    lines.append(f"title: {yaml_scalar(api['title'])}")
    if api.get("base_url"):
        lines.append(f"base_url: {yaml_scalar(api['base_url'])}")
    lines.append(f"mpin_required: {yaml_scalar(api['mpin_required'])}")
    lines.append(f"idempotent: {yaml_scalar(api['idempotent'])}")
    lines.append("version: 1")
    lines.append("last_verified: 2026-08-19")

    if api.get("body_root"):
        lines.append(f"body_root: {yaml_scalar(api['body_root'])}")

    if api.get("constants"):
        lines.append("")
        lines.append("# Sent on every call, whatever the merchant said. The path alone")
        lines.append("# does not identify this action; these values do.")
        lines.append("constants:")
        for key, value in api["constants"].items():
            lines.append(f"  {key}: {yaml_scalar(value)}")

    lines.append("")
    lines.append("fields:")
    for field in api["fields"]:
        lines.append(f"  - name: {yaml_scalar(field['name'])}")
        for key in ("type", "required", "in", "prompt", "example", "default", "max_length"):
            if key in field:
                lines.append(f"    {key}: {yaml_scalar(field[key])}")
        if "values" in field:
            lines.append("    values: [%s]" % ", ".join(yaml_scalar(v) for v in field["values"]))

    lines.append("")
    lines.append("returns:")
    # Quoted through yaml_scalar: response paths like `[].date` and
    # `{coin}.{currency}` start a flow sequence or mapping if left bare, and the
    # whole front matter is then discarded as malformed.
    lines.append("  success: [%s]"
                 % ", ".join(yaml_scalar(v) for v in api["returns"]["success"]))
    if api["returns"]["errors"]:
        lines.append("  errors:")
        for code, message in api["returns"]["errors"].items():
            lines.append(f"    {code}: {yaml_scalar(message)}")

    lines.append("")
    lines.append("utterances:")
    for utterance in api["utterances"]:
        lines.append(f"  - {yaml_scalar(utterance)}")

    lines.append("---")
    lines.append("")
    lines.append(api["body"].strip())
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    if OUT.exists():
        for old in OUT.rglob("*.md"):
            old.unlink()

    counts: dict[str, int] = {}
    for api in APIS:
        folder = OUT / api["domain"]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{api['api_id']}.md"
        io.open(path, "w", encoding="utf-8").write(render(api))
        counts[api["domain"]] = counts.get(api["domain"], 0) + 1

    # Written beside the tree, not inside it: it is a note about the folders,
    # not a card, and the loader would rightly refuse it.
    domains_file = OUT.parent / "api-catalog-domains.md"
    io.open(domains_file, "w", encoding="utf-8").write(
        "# Domains\n\n"
        "The folder each API lives in. Domains are shaped the way a merchant\n"
        "thinks about their day, not the way the backend is factored.\n\n"
        + "\n".join(f"- **{slug}** ({counts.get(slug, 0)} APIs) — {desc}"
                    for slug, desc in DOMAINS.items())
        + "\n"
    )

    total_utterances = sum(len(a["utterances"]) for a in APIS)
    print(f"{len(APIS)} API cards across {len(counts)} domains -> {OUT}")
    for slug in DOMAINS:
        print(f"  {slug:<10} {counts.get(slug, 0)}")
    print(f"{total_utterances} example utterances "
          f"({total_utterances / len(APIS):.1f} per API)")


if __name__ == "__main__":
    main()
