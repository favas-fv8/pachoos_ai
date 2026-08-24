"""AI services — chat assistants, product recommendations, smart search.

Two strictly separated assistant audiences share this module (one system, two
scopes — never a shared data context):

* **Customer** (``chat_assistant``) — customer-side data only: live product &
  category search (keyword/intent based), the user's own orders/payments/
  wallet/wishlist and shop policies. Admin, dashboard, other customers' or
  internal-only questions are refused.
* **Admin** (``admin_chat_assistant``) — authorized admin data only:
  dashboard stats, revenue, orders, stock, notifications. Reached through an
  IsAdmin-guarded endpoint; never callable by customers.

Dev mode (no OPENAI_API_KEY): rule-based responses grounded in the same real
data. Production: OpenAI with per-audience system prompts + data contexts.
"""
import random
import re
from decimal import Decimal

from django.conf import settings
from django.db.models import Q


# ---------------------------------------------------------------------------
# Prompts & guardrails
# ---------------------------------------------------------------------------

CUSTOMER_SYSTEM_PROMPT = """You are PACHOOS Assistant, a friendly helper for a \
local bakery & fruits shop. You serve CUSTOMERS only.

You may help with: browsing products and prices, recommendations, placing and \
tracking the user's OWN orders, payments for their own orders, delivery \
charges/ETAs, their own wallet/cashback/vouchers, their wishlist and account.

Hard rules:
- Use ONLY the provided shop/user data for facts; never invent numbers or order IDs.
- NEVER access, reveal, summarize or hint at admin/internal data: dashboards, \
revenue/profit figures, other customers, staff information, internal payment \
records or stock ledgers beyond product availability.
- If asked anything admin-related, politely reply that the information is not \
available to customers and steer back to shopping help.
- Keep responses short, helpful and friendly. Prices in Indian Rupees (₹).
- If you don't know something, say so honestly.
- Format for a small chat bubble: **bold** section titles, bullet lists for
  lists of things, and simple pipe tables (| Field | Detail |) when showing
  several related values. Never return raw JSON or database objects."""

ADMIN_SYSTEM_PROMPT = """You are PACHOOS Admin Assistant for the shop's \
management team. You answer ONLY from the provided live admin data.

You may help with: dashboard stats (revenue/orders/customers), monthly revenue \
trends, top products, low-stock alerts, recent orders, payments status and \
customer counts. You already passed authentication and RBAC.

Rules:
- Quote exact numbers from the data block; never invent figures.
- Never reveal other systems' internals beyond this admin scope.
- Keep answers concise; use Indian Rupees (₹).
- Format for a small chat bubble: **bold** section titles, bullet lists for
  lists, and simple pipe tables (| Metric | Value |) when comparing several
  related values. Never return raw JSON or unformatted data.
- If something is not in the data, say so."""

# Customer-facing refusal — returned verbatim whenever an admin-scope question
# is detected, so no LLM call can leak internal data either.
ADMIN_QUERY_REFUSAL = (
    "That information is part of our internal store administration and isn't "
    "available to customers. I can help you with products, your orders, "
    "payments, wallet/cashback, wishlist or delivery — what would you like?"
)

_ADMIN_QUERY_KEYWORDS = (
    # dashboard / revenue / business internals
    "dashboard", "admin", "revenue", "profit", "sales report",
    "total sales", "monthly sales", "monthly revenue", "turnover",
    # other people's data
    "all customers", "other customers", "customer list", "customers list",
    "how many customers", "staff", "employee",
    # internal operations
    "stock report", "inventory report", "low stock", "restock", "debt book",
    "internal", "cashfree dashboard", "business account",
)


def _is_admin_query(message: str) -> bool:
    """True when a customer message asks for admin-scope information."""
    msg = message.lower()
    # Personal debt references belong to the customer's OWN Debt Book (their
    # /account section), not admin scope — exempt them from the refusal.
    if (
        "debt" in msg
        and re.search(r"\b(my|me|mine|i|we|our)\b", msg)
        and "report" not in msg
    ):
        return False
    return any(kw in msg for kw in _ADMIN_QUERY_KEYWORDS)


def refuse_admin_query() -> str:
    """Polite, fixed refusal — no admin data is ever touched."""
    return ADMIN_QUERY_REFUSAL


# ---------------------------------------------------------------------------
# Customer catalog intent — product & category search on live data
# ---------------------------------------------------------------------------

# Dedicated prompt used only when a product/category match was found, so the
# LLM phrases exactly the matched live rows instead of the generic dump.
CATALOG_SYSTEM_PROMPT = """You are PACHOOS Assistant, a friendly helper for a \
local bakery & fruits shop. You serve CUSTOMERS only.

The customer asked about products. The "Live data" block lists the EXACT \
available products currently matching their request from our catalog.

Rules:
- Present ONLY the products listed in the Live data block — never invent \
products, prices or stock numbers.
- List every product as a bullet: **name** (category) — ₹price · stock.
- Keep it short, friendly and scannable; point them to the Shop page to order.
- If you don't know something, say so honestly."""

# Words that never carry catalog meaning on their own. Any intent keyword of
# the other rule-based branches is included so this search can never hijack
# order/wallet/delivery/... questions.
_CATALOG_STOPWORDS = frozenset("""
a about all am an any are available availability best can cost costs did do
does get getting give good got has have hello hey hi how i in is it item
items know list looking me much my need no of on or our please price prices
product products recommend sale see sell selling show some something suggest
tell thank thanks that the their there they thing things top us want we what
which who why will with would you your
cart coupon coupons delivery deliver discount discounts location address
order orders track tracking wallet cashback wishlist voucher vouchers
payment payments status refund returns balance account profile sign login
signin signup register debt debts udhaar owe owed owing bought buy purchases
purchase paid transaction transactions password passwords passcode timing
timings hours opening closing contact phone email about profile
""".split())

# Colloquial category words → canonical keyword resolved against live names.
_CATEGORY_SYNONYMS = {
    "veg": "vegetable",
    "veggie": "vegetable",
    "veggies": "vegetable",
}


def _normalize_message(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    return re.sub(r"[^a-z0-9\s]", " ", text.lower()).strip()


def _name_variants(name: str) -> set[str]:
    """Simple singular/plural variants of a catalog name ("Fruits" ↔ "fruit")."""
    n = name.strip().lower()
    variants = {n}
    if n.endswith("ies"):
        variants.add(n[:-3] + "y")
        variants.add(n[:-3])
    if n.endswith("es"):
        variants.add(n[:-2])
    if n.endswith("s"):
        variants.add(n[:-1])
    else:
        variants.add(n + "s")
        variants.add(n + "es")
    return variants


def _contains_name_variant(normalized_msg: str, name: str) -> bool:
    return any(
        re.search(rf"\b{re.escape(v)}\b", normalized_msg)
        for v in _name_variants(name)
    )


def _match_catalog_category(normalized_msg: str):
    """Match the message against LIVE Category/Subcategory names.

    Returns ``(kind, name)`` where kind is ``category`` or ``subcategory``,
    or ``None`` when nothing matches. Categories win over subcategories so
    broad asks like "fruits" list everything fruit-related.
    """
    from apps.catalog.models import Category, Subcategory

    for kind, model in (("category", Category), ("subcategory", Subcategory)):
        for name in model.objects.values_list("name", flat=True):
            if _contains_name_variant(normalized_msg, name):
                return kind, name

    # Colloquial synonyms ("veggies") resolved against live names.
    for syn, canonical in _CATEGORY_SYNONYMS.items():
        if re.search(rf"\b{syn}\b", normalized_msg):
            for kind, model in (
                ("category", Category), ("subcategory", Subcategory)
            ):
                for name in model.objects.values_list("name", flat=True):
                    if canonical in _name_variants(name):
                        return kind, name
    return None


def _catalog_search_products(message: str) -> list:
    """Detect a product/category request and return matching LIVE products.

    Returns an empty list when the message is catalog-shaped but has no
    matches; callers then fall through to the generic flow unchanged.
    """
    msg = _normalize_message(message)
    if not msg:
        return []

    node = _match_catalog_category(msg)
    if node is not None:
        kind, name = node
        from apps.catalog.models import Product

        qs = Product.objects.filter(is_available=True).select_related("subcategory")
        if kind == "category":
            qs = qs.filter(subcategory__category__name__iexact=name)
        else:
            qs = qs.filter(subcategory__name__iexact=name)
        return list(qs.order_by("-times_sold")[:10])

    words = [w for w in msg.split() if w not in _CATALOG_STOPWORDS and len(w) >= 2]
    if not words:
        return []
    return smart_search(" ".join(words), limit=10)


def _product_line(p) -> str:
    """One consistently formatted live-product list item."""
    if p.stock_quantity <= 0:
        stock = "currently out of stock"
    elif p.stock_unit == "kg":
        stock = f"{p.stock_quantity} kg in stock"
    else:
        stock = f"{p.stock_quantity} left in stock"
    return f"- **{p.name}** ({p.subcategory.name}) — {_fmt_money(p.effective_price)} · {stock}"


def _catalog_reply_text(products: list) -> str:
    """Deterministic catalog answer (dev fallback / LLM unavailable)."""
    lines = "\n".join(_product_line(p) for p in products)
    return (
        "**Here's what I found:**\n"
        f"{lines}\n"
        "Tap any product on the Shop page to add it to your cart!"
    )


# ---------------------------------------------------------------------------
# Customer account intents — Location/Orders/Debt Book/Payments (live data)
# ---------------------------------------------------------------------------

# Answers are rendered from deterministic templates on purpose: every figure
# must match the customer's /account page exactly, so no LLM paraphrasing of
# money/status data happens in this layer.

_ACCOUNT_INTENT_KEYWORDS = {
    "location": ("location", "address", "deliver to", "deliver-to"),
    "orders": ("order", "orders", "ordered", "bought", "purchase",
               "purchases", "purchased"),
    "payments": ("payment", "payments", "paid", "transaction", "transactions"),
    "debt": ("debt", "debts", "outstanding", "udhaar", "owe", "owed",
             "owing", "borrow", "borrowed"),
    "cart": ("cart",),
    "password": ("password", "passcode"),
    "profile": ("profile", "account", "my details", "my info",
                "my information", "personal info"),
}

# Words that mark a delivery-policy question ("how does delivery work?") —
# only treated as the Deliver-To intent when a personal marker is present too.
_DELIVERY_GUARDS = re.compile(r"\b(my|me|mine|where|current|selected|set)\b")

# When the customer asks about THE SHOP's address/location ("what is your
# address?") it belongs to Shop Information, not their Deliver-To location.
_SHOP_MARKER_RE = re.compile(r"\b(shop|store|outlet|your|you|business)\b")

_RECOMMEND_WORDS = ("recommend", "suggest", "best seller", "bestseller")

# Shop-information triggers (checked after product search so "cake shop"
# still lists cakes). The brand name itself ("what is Pachoos?") counts too.
_SHOP_INTENT_RES = (
    re.compile(r"\bpachoos\b"),
    re.compile(r"\b(shop|store|outlet)\b"),
    re.compile(r"\b(you|your)\b.*\b(located|address|location)\b"),
    re.compile(r"\b(timing|timings|hours|opening|closing|open)\b"),
    re.compile(r"\babout\b.*\b(us|shop|store|you|pachoos)\b"),
    re.compile(r"\bdeliver(y|ed|s)?\b.*\b(charge|charges|fee|fees|free|radius|km|area|areas|details)\b"),
)

# Location-focused shop asks ("where is Pachoos?") get a focused answer.
_SHOP_LOCATION_RE = re.compile(
    r"\b(where|located|location|address|directions?|reach|find)\b"
)

_IDENTITY_KEYWORDS = (
    "who are you", "what are you", "whats your name", "what is your name",
    "are you a bot", "are you human", "are you real", "are you ai",
    "am i talking to", "what can you do", "how can you help",
)
_IDENTITY_REPLY = (
    "I'm the PACHOOS customer AI assistant — a bot, not a human! "
    "Here's what I can help you with:\n"
    "- Finding products and categories\n"
    "- Checking your cart and latest order\n"
    "- Payments, wallet cashback and your Debt Book\n"
    "- Your profile and delivery location\n"
    "- Shop information — timings, location and delivery charges\n\n"
    "What can I do for you today?"
)

# Domain nouns that mean an identity question is actually about something
# else ("what are you doing with my order?") — skip the identity reply then.
_IDENTITY_EXCLUDE_RE = re.compile(
    r"\b(order|cart|payment|debt|wallet|location|profile|password|"
    r"product|products|category|categories|stock)\b"
)


def _identity_reply(message: str) -> str | None:
    """Introduce the assistant when the customer asks who/what it is."""
    msg = _normalize_message(message)
    if not any(
        re.search(rf"\b{re.escape(kw)}\b", msg) for kw in _IDENTITY_KEYWORDS
    ):
        return None
    if _IDENTITY_EXCLUDE_RE.search(msg):
        return None
    return _IDENTITY_REPLY

_GENERIC_CATEGORY_RE = re.compile(r"\bcategor(y|ies)\b|\bcatalogue?\b")
_GENERIC_PRODUCT_RE = re.compile(r"\bproducts?\b|\bitems?\b|\bmenu\b|\beverything\b")


def _detect_account_intent(normalized_msg: str) -> str | None:
    """Map an account-section keyword to its intent.

    Priority: password, then location before orders ("Where should my order
    be delivered?" asks for the Deliver-To location), cart, orders, payments
    and finally debt.
    """
    if any(re.search(rf"\b{re.escape(kw)}\b", normalized_msg)
           for kw in _ACCOUNT_INTENT_KEYWORDS["password"]):
        return "password"

    asks_location = any(kw in normalized_msg for kw in _ACCOUNT_INTENT_KEYWORDS["location"])
    has_delivery_word = (
        "deliver" in normalized_msg
        or "delivery" in normalized_msg
        or "delivered" in normalized_msg
    )
    if (asks_location or has_delivery_word) and not _is_shop_question(normalized_msg):
        if asks_location or _DELIVERY_GUARDS.search(normalized_msg):
            return "location"

    if any(re.search(rf"\b{re.escape(kw)}\b", normalized_msg)
           for kw in _ACCOUNT_INTENT_KEYWORDS["cart"]):
        return "cart"

    if not any(w in normalized_msg for w in _RECOMMEND_WORDS):
        if any(re.search(rf"\b{re.escape(kw)}\b", normalized_msg)
               for kw in _ACCOUNT_INTENT_KEYWORDS["orders"]):
            return "orders"
    if any(re.search(rf"\b{re.escape(kw)}\b", normalized_msg)
           for kw in _ACCOUNT_INTENT_KEYWORDS["payments"]):
        return "payments"
    if any(re.search(rf"\b{re.escape(kw)}\b", normalized_msg)
           for kw in _ACCOUNT_INTENT_KEYWORDS["debt"]):
        return "debt"
    if any(re.search(rf"\b{re.escape(kw)}\b", normalized_msg)
           for kw in _ACCOUNT_INTENT_KEYWORDS["profile"]):
        return "profile"
    return None


def _is_shop_question(normalized_msg: str) -> bool:
    """True when the question targets the shop itself, not the customer."""
    if any(rx.search(normalized_msg) for rx in _SHOP_INTENT_RES):
        return True
    return bool(
        _SHOP_MARKER_RE.search(normalized_msg)
        and re.search(r"\b(located|address|location)\b", normalized_msg)
    )


def _clean_client_location(raw) -> dict | None:
    """Sanitize the client-supplied Deliver-To location (Redux uiSlice)."""
    if not isinstance(raw, dict):
        return None
    label = str(raw.get("label") or "").strip()[:200]
    try:
        lat = float(raw.get("lat"))
        lon = float(raw.get("lon"))
    except (TypeError, ValueError):
        lat = lon = None
    if not label or lat is None:
        return None
    return {"label": label, "lat": lat, "lon": lon}


_SIGN_IN_HINTS = {
    "location": "Sign in and set your delivery location from the header "
                "\"Deliver To\" picker — then I can check it for you!",
    "orders": "Please sign in and I can check your orders! You can also use "
              "the Track page.",
    "payments": "Please sign in and I can check your payments!",
    "debt": "Please sign in and I can check your Debt Book balance!",
    "cart": "Please sign in and I can show you what's in your cart!",
    "profile": "Please sign in and I can show your profile details!",
}


def _get_active_shop():
    """The shop all customer-side data is scoped to (single-shop platform)."""
    from apps.shops.models import Shop

    return Shop.objects.filter(is_active=True).order_by("id").first()


def _account_intent_reply(message: str, user=None, raw_location=None) -> str | None:
    """Answer /account-section questions with the requesting customer's LIVE
    data. Returns ``None`` when the message isn't an account question.

    Every query is filtered by ``user`` — guests get a sign-in prompt, staff
    were already reduced to guests by the view, and no other customer's rows
    are ever touchable.
    """
    intent = _detect_account_intent(_normalize_message(message))
    if intent is None:
        return None

    if user is None or not getattr(user, "is_authenticated", False):
        if intent == "password":
            return _PASSWORD_REPLY
        return _SIGN_IN_HINTS[intent]

    if intent == "password":
        return _PASSWORD_REPLY

    if intent == "location":
        loc = _clean_client_location(raw_location)
        if loc is None:
            return (
                "You haven't set a delivery location yet. Tap the \"Deliver To\" "
                "picker in the header to set where your orders should arrive!"
            )
        return f"Your current delivery location is: {loc['label']}."

    if intent == "orders":
        from apps.orders.models import Order

        latest = Order.objects.filter(user=user).order_by("-created_at").first()
        if latest is None:
            return "You haven't placed any orders yet — check out the Shop page!"
        lines = [
            f"**Your latest order #{latest.order_number}**",
            "",
            "| Field | Detail |",
            "| --- | --- |",
            f"| Status | {latest.get_status_display()} |",
            f"| Payment | {latest.get_payment_status_display()} |",
            f"| Total | {_fmt_money(latest.grand_total)} |",
            f"| Placed | {latest.created_at:%d %b %Y} |",
        ]
        if latest.delivery_eta:
            lines.append(f"| Expected delivery | {latest.delivery_eta:%d %b %Y, %I:%M %p} |")
        item_rows = [
            f"- {i.quantity}× {i.product_name}"
            for i in latest.items.all()[:4]
        ]
        if item_rows:
            lines.append("")
            lines.append("**Items**")
            lines.extend(item_rows)
        return "\n".join(lines)

    if intent == "cart":
        from apps.cart.models import Cart

        cart = (
            Cart.objects.filter(user=user, is_active=True)
            .prefetch_related("items__product")
            .first()
        )
        if cart is None or not cart.items.exists():
            return (
                "Your cart is empty right now — add something tasty "
                "from the Shop page!"
            )
        lines = [f"**Your cart ({cart.item_count} item{'s' if cart.item_count != 1 else ''})**", ""]
        for item in cart.items.all()[:8]:
            variant = f" — {item.variant.name}" if item.variant else ""
            lines.append(
                f"- {item.quantity}× {item.product.name}{variant} — "
                f"**{_fmt_money(item.line_total)}**"
            )
        lines.append("")
        lines.append(f"Subtotal: **{_fmt_money(cart.subtotal)}**")
        lines.append("Review it on the Cart page whenever you're ready!")
        return "\n".join(lines)

    if intent == "payments":
        from apps.payments.models import Payment

        payment = (
            Payment.objects.filter(user=user)
            .select_related("order")
            .order_by("-created_at")
            .first()
        )
        if payment is None:
            return (
                "You haven't made any payments yet. Once you place an order, "
                "your payment history will show here!"
            )
        return (
            "**Your latest payment**\n"
            "\n"
            "| Field | Detail |\n"
            "| --- | --- |\n"
            f"| Amount | {_fmt_money(payment.amount)} |\n"
            f"| Method | {payment.get_method_display()} |\n"
            f"| Order | #{payment.order.order_number} |\n"
            f"| Status | {payment.get_status_display()} |\n"
            f"| Date | {payment.created_at:%d %b %Y} |"
        )

    if intent == "profile":
        # Same serializer the /account/profile page uses — zero duplication.
        from apps.accounts.auth_service import serialize_user

        u = serialize_user(user)
        rows = [
            ("Name", u["full_name"] or "—"),
            ("Phone", u["phone"] or "—"),
        ]
        if u.get("email"):
            rows.append(("Email", u["email"]))
        if u.get("referral_code"):
            rows.append(("Referral code", u["referral_code"]))
        rows.append(("Account verified", "Yes" if u.get("is_verified") else "No"))
        lines = [
            "**Your profile**",
            "",
            "| Field | Detail |",
            "| --- | --- |",
            *(f"| {label} | {value} |" for label, value in rows),
            "",
            "You can update your details on the Profile page (/account/profile).",
        ]
        return "\n".join(lines)

    # debt — mirrors CustomerDebtBookView exactly: the customer's own
    # DebtBook row, with totals from its book-anchored entries (never the
    # legacy user anchor, which misses linked offline history).
    from apps.wallet.models import DebtBook
    from apps.wallet.services import get_debt_book_summary

    shop = _get_active_shop()
    books = DebtBook.objects.filter(user=user)
    book = books.filter(shop=shop).first() if shop else books.first()
    summary = get_debt_book_summary(book) if book else {
        "outstanding": "0.00", "total_added": "0.00", "total_paid": "0.00",
    }
    outstanding = Decimal(summary["outstanding"])
    if book is None or outstanding <= 0:
        return "Good news — your Debt Book is clear, nothing outstanding!"

    type_labels = {"bill": "Debt added", "payment": "Payment made", "adjustment": "Adjustment"}
    lines = [
        "**Your Debt Book**",
        "",
        f"Outstanding: **{_fmt_money(outstanding)}** · "
        f"Total added: {_fmt_money(summary['total_added'])} · "
        f"Paid: {_fmt_money(summary['total_paid'])}",
        "",
        "**Recent activity**",
        "",
        "| Date | Type | Amount | Balance after |",
        "| --- | --- | --- | --- |",
    ]
    for entry in book.entries.order_by("-created_at")[:3]:
        label = type_labels.get(entry.entry_type, entry.get_entry_type_display())
        lines.append(
            f"| {entry.created_at:%d %b %Y} | {label} | "
            f"{_fmt_money(abs(entry.delta))} | {_fmt_money(entry.balance_after)} |"
        )
    lines.append("")
    lines.append("You can settle it at the counter or from your Wallet.")
    return "\n".join(lines)


_PASSWORD_REPLY = (
    "**Changing your password**\n"
    "1. Go to Account → Settings (/account/settings).\n"
    "2. Use the change-password option and follow the prompts.\n"
    "\n"
    "**Forgot your password?**\n"
    "1. Open /forgot-password from the login page.\n"
    "2. We'll email you a secure reset link."
)


# ---------------------------------------------------------------------------
# Customer shop-information intent — live Shop row + business rules
# ---------------------------------------------------------------------------

def _shop_info_reply(message: str) -> str | None:
    """Answer shop questions (name, about, location, timings, delivery) from
    the live Shop row. Returns None when the message isn't about the shop."""
    if not _is_shop_question(_normalize_message(message)):
        return None

    shop = _get_active_shop()
    if shop is None:
        return None

    address = ", ".join(
        part for part in (
            shop.address_line1, shop.address_line2,
            shop.city, shop.state, shop.pincode,
        ) if part
    )

    # Location-focused asks ("where is Pachoos?") get a focused answer.
    if _SHOP_LOCATION_RE.search(_normalize_message(message)):
        lines = [f"**{shop.name}** is located at:" if address
                 else f"**{shop.name}** — location not set yet."]
        if address:
            lines.append(f"- {address}")
        lines.append(
            f"- We deliver within {float(shop.delivery_radius_km):g} km of the store"
        )
        return "\n".join(lines)

    lines = [f"**{shop.name}**{' — ' + shop.tagline if shop.tagline else ''}", ""]
    if address:
        lines.append("**Where we are**")
        lines.append(f"- {address}")
    if shop.timing_open and shop.timing_close:
        lines.append("")
        lines.append("**Timings**")
        lines.append(f"- Open daily {shop.timing_open:%I:%M %p} – {shop.timing_close:%I:%M %p}")
    contact = ", ".join(
        part for part in (
            f"phone {shop.phone}" if shop.phone else "",
            f"email {shop.email}" if shop.email else "",
        ) if part
    )
    if contact:
        lines.append("")
        lines.append("**Contact**")
        lines.append(f"- {contact}")

    b = settings.BUSINESS
    from apps.catalog.models import Category

    category_names = list(Category.objects.values_list("name", flat=True)[:6])
    lines.append("")
    lines.append("**Services & offers**")
    if category_names:
        lines.append(f"- What we offer: {', '.join(category_names)} — fresh every day")
    lines.append(
        f"- Delivery: free within {float(shop.delivery_radius_km):g} km "
        f"(minimum order {_fmt_money(shop.free_delivery_min_order)}); beyond "
        f"that a flat {_fmt_money(shop.delivery_charge)} charge applies"
    )
    lines.append(f"- Cashback: earn ₹1 for every ₹{b['CASHBACK_PER_INR']:.0f} spent")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generic catalog browsing — "show products", "what categories exist"
# ---------------------------------------------------------------------------

def _category_tree_reply() -> str:
    """Live Category → Subcategory overview."""
    from apps.catalog.models import Category

    cats = list(
        Category.objects.prefetch_related("subcategories")
        .order_by("name")
    )
    if not cats:
        return "We're still setting up the catalogue — check back soon!"
    lines = ["**Our categories:**"]
    for cat in cats:
        subs = [s.name for s in cat.subcategories.all() if s.is_active]
        lines.append(f"- **{cat.name}**" + (f": {', '.join(subs)}" if subs else ""))
    lines.append("")
    lines.append("Ask me for any category or product — e.g. \"show fruit products\"!")
    return "\n".join(lines)


def _generic_catalog_reply(message: str) -> str | None:
    """Handle broad browse asks ("show products") with live data.

    Runs AFTER specific product/category search so queries like
    "fruit products" keep their targeted answers.
    """
    msg = _normalize_message(message)
    if _GENERIC_CATEGORY_RE.search(msg):
        return _category_tree_reply()
    if _GENERIC_PRODUCT_RE.search(msg):
        from apps.catalog.models import Product

        products = list(
            Product.objects.filter(is_available=True)
            .select_related("subcategory")
            .order_by("-times_sold")[:10]
        )
        if not products:
            return "The shop is being restocked right now — check back soon!"
        lines = "\n".join(_product_line(p) for p in products)
        return (
            "**Available right now:**\n"
            f"{lines}\n"
            "Tap any product on the Shop page to add it to your cart!"
        )
    return None


# ---------------------------------------------------------------------------
# Data contexts (per audience)
# ---------------------------------------------------------------------------

def _get_product_context() -> str:
    """Compact available-product catalog (shared, non-sensitive)."""
    from apps.catalog.models import Product

    products = Product.objects.filter(is_available=True).select_related(
        "subcategory"
    )[:20]

    items = []
    for p in products:
        items.append(
            f"- {p.name} (₹{p.effective_price:.0f}) [{p.subcategory.name}] "
            f"{'★' if p.avg_rating >= 4 else ''} sold:{p.times_sold}"
        )
    return "\n".join(items)


def _fmt_money(value) -> str:
    return f"₹{Decimal(str(value)):.2f}"


def _customer_context(user) -> str:
    """The requesting customer's OWN data only (never other users')."""
    from apps.catalog.models import Wishlist
    from apps.orders.models import Order
    from apps.wallet.services import get_wallet_balance

    parts = []

    if user is None or not getattr(user, "is_authenticated", False):
        parts.append(
            "Customer: guest (not signed in) — personal order/wallet details are "
            "unavailable; suggest signing in for personalized help."
        )
        return "\n".join(parts)

    parts.append(f"Customer: {user.full_name}")

    orders = Order.objects.filter(user=user).order_by("-created_at")[:5]
    if orders:
        lines = [
            f"  #{o.order_number} | {o.status} | payment:{o.payment_status} | "
            f"{_fmt_money(o.grand_total)} | placed {o.created_at:%d %b %Y}"
            for o in orders
        ]
        paid_count = Order.objects.filter(user=user, payment_status="paid").count()
        parts.append(
            f"Recent orders ({paid_count} paid total):\n" + "\n".join(lines)
        )
    else:
        parts.append("Orders: none yet.")

    from apps.shops.models import Shop
    from apps.wallet.services import get_wallet_balance

    shop = Shop.objects.filter(is_active=True).order_by("id").first()
    balance = get_wallet_balance(user, shop)
    parts.append(f"Wallet cashback balance: {_fmt_money(balance)}")

    wishlist_count = Wishlist.objects.filter(user=user).count()
    parts.append(f"Wishlist items: {wishlist_count}")

    b = settings.BUSINESS
    parts.append(
        f"Shop policy: free delivery within {b['FREE_DELIVERY_MAX_KM']} km of the "
        f"store; otherwise flat {_fmt_money(b['DELIVERY_CHARGE'])}. Cashback: "
        f"₹1 per ₹{b['CASHBACK_PER_INR']:.0f} spent."
    )
    return "\n".join(parts)


def _admin_context(shop) -> str:
    """Live admin-side aggregates (authorized admins only). Reuses the same
    services that power the /admin dashboard so answers always agree."""
    from apps.admin_dashboard.services import (
        get_dashboard_stats,
        get_low_stock_products,
        get_recent_orders,
    )

    stats = get_dashboard_stats(shop)
    low_stock = get_low_stock_products(shop)[:5]
    recent = get_recent_orders(shop, limit=5)

    parts = [
        "Dashboard stats:",
        f"  revenue total/monthly/weekly: {_fmt_money(stats['revenue']['total'])} / "
        f"{_fmt_money(stats['revenue']['monthly'])} / {_fmt_money(stats['revenue']['weekly'])}",
        f"  orders total/monthly/pending: {stats['orders']['total']} / "
        f"{stats['orders']['monthly']} / {stats['orders']['pending']}",
        f"  customers total/new-this-month: {stats['customers']['total']} / "
        f"{stats['customers']['new_this_month']}",
        f"  avg order value (30d): {_fmt_money(stats['avg_order_value'])}",
    ]

    if low_stock:
        parts.append(
            "Low stock:\n"
            + "\n".join(
                f"  {p['name']}: {p['stock_quantity']} {'kg' if p['stock_unit'] == 'kg' else 'left'}"
                for p in low_stock
            )
        )
    else:
        parts.append("Low stock: all products well stocked.")

    if recent:
        parts.append(
            "Recent orders:\n"
            + "\n".join(
                f"  #{o['order_number']} | {o['user_name']} | {o['status']} | "
                f"{_fmt_money(o['grand_total'])}"
                for o in recent
            )
        )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Rule-based engines (dev fallback — same scopes, real data)
# ---------------------------------------------------------------------------

GREETING_RESPONSES = [
    "Hey! Welcome to PACHOOS! How can I help you today?",
    "Hi there! Need help finding something delicious?",
    "Welcome to PACHOOS! What are you craving today?",
]

FALLBACK_RESPONSES = [
    "I'm not sure about that one! I can help with products, your orders, wallet "
    "or delivery — just ask!",
    "I don't have that info right now, but feel free to browse our shop page!",
]


def _rule_based_customer_chat(message: str, user=None) -> str:
    """Data-aware rule-based replies for the CUSTOMER audience."""
    msg = message.lower().strip()

    greetings = ["hi", "hello", "hey", "hii", "good morning", "good evening"]
    if any(g in msg for g in greetings):
        return random.choice(GREETING_RESPONSES)

    if _is_admin_query(msg):
        return refuse_admin_query()

    signed_in = bool(user and getattr(user, "is_authenticated", False))

    if any(w in msg for w in ("my order", "track", "where is my")):
        if not signed_in:
            return "Please sign in and I can check your orders! You can also use the Track page."
        from apps.orders.models import Order

        latest = Order.objects.filter(user=user).order_by("-created_at").first()
        if not latest:
            return "You haven't placed any orders yet — check out the Shop page!"
        return (
            f"Your latest order #{latest.order_number} is currently "
            f"'{latest.get_status_display()}' (payment: {latest.payment_status}). "
            f"You can track it on the Track page."
        )

    if "wallet" in msg or "cashback" in msg:
        if not signed_in:
            return (
                "You earn ₹1 cashback per ₹100 spent once you sign in! "
                "Your balance shows on the Wallet page."
            )
        from apps.shops.models import Shop
        from apps.wallet.services import get_wallet_balance

        shop = Shop.objects.filter(is_active=True).order_by("id").first()
        balance = get_wallet_balance(user, shop)
        redeemable = " You can redeem it at checkout!" if balance >= Decimal("10.00") else ""
        return f"Your cashback balance is {_fmt_money(balance)}.{redeemable}"

    if "recommend" in msg or "suggest" in msg or "best" in msg:
        from apps.catalog.models import Product

        top = list(Product.objects.filter(is_available=True).order_by("-times_sold")[:3])
        if not top:
            return (
                "I'd love to recommend something delicious! "
                "Browse the Shop page to see what's available today."
            )
        names = ", ".join(p.name for p in top)
        return f"Our top sellers right now: {names}! Check the Shop page to order."

    if "price" in msg or "cost" in msg:
        return "Our products range from ₹20 to ₹500. Visit the Shop to see all prices!"

    if "delivery" in msg:
        b = settings.BUSINESS
        return (
            f"Free delivery within {b['FREE_DELIVERY_MAX_KM']} km of the store; "
            f"beyond that a flat {_fmt_money(b['DELIVERY_CHARGE'])} charge applies. "
            f"The distance is calculated automatically at checkout from your "
            f"delivery location."
        )

    if "coupon" in msg or "voucher" in msg or "discount" in msg:
        return "Check the Checkout page — you can apply coupon codes and voucher codes there!"

    if "wishlist" in msg:
        if not signed_in:
            return "Sign in to build your wishlist — tap the heart on any product!"
        from apps.catalog.models import Wishlist

        count = Wishlist.objects.filter(user=user).count()
        return (
            f"You have {count} item{'s' if count != 1 else ''} saved in your wishlist."
            if count
            else "Your wishlist is empty — tap the heart on any product to save it!"
        )

    if "thank" in msg:
        return "You're welcome! Happy to help!"

    return random.choice(FALLBACK_RESPONSES)


def _admin_revenue_block(stats) -> str:
    """Formatted revenue overview table (shared by rule engine + intents)."""
    return "\n".join((
        "**Revenue overview**",
        "",
        "| Period | Revenue |",
        "| --- | --- |",
        f"| Total | {_fmt_money(stats['revenue']['total'])} |",
        f"| This month | {_fmt_money(stats['revenue']['monthly'])} |",
        f"| This week | {_fmt_money(stats['revenue']['weekly'])} |",
    ))


def _admin_orders_block(stats) -> str:
    """Formatted orders snapshot table."""
    return "\n".join((
        "**Orders snapshot**",
        "",
        "| Metric | Count |",
        "| --- | --- |",
        f"| Total orders | {stats['orders']['total']} |",
        f"| Pending | {stats['orders']['pending']} |",
        f"| Paid this month | {stats['orders']['monthly']} |",
    ))


def _admin_rule_chat(message: str, shop) -> str:
    """Data-aware rule-based replies for the ADMIN audience."""
    msg = message.lower().strip()

    from apps.admin_dashboard.services import get_dashboard_stats

    stats = get_dashboard_stats(shop)

    if any(g in msg for g in ("hi", "hello", "hey")):
        return (
            "Hi! Ask me about revenue, orders, customers or stock — "
            "all straight from the live dashboard."
        )

    revenue_rows = _admin_revenue_block(stats).split("\n")
    if "monthly revenue" in msg or ("month" in msg and "revenue" in msg):
        return "\n".join((
            *revenue_rows,
            "",
            "This calendar month counts paid orders only.",
        ))
    if "weekly" in msg and "revenue" in msg:
        return _admin_revenue_block(stats)
    if "revenue" in msg or "sales" in msg or "turnover" in msg:
        return _admin_revenue_block(stats)

    if "pending" in msg and "order" in msg:
        return _admin_orders_block(stats)
    if "monthly order" in msg or ("month" in msg and "order" in msg):
        return _admin_orders_block(stats)
    if "order" in msg:
        return _admin_orders_block(stats)

    if "stock" in msg or "inventory" in msg:
        from apps.admin_dashboard.services import get_low_stock_products

        low = get_low_stock_products(shop)
        if not low:
            return "All products are well stocked — nothing at or below the low-stock threshold."
        lines = [
            f"**Low-stock items ({len(low)})**",
            "",
            "| Product | Stock left |",
            "| --- | --- |",
        ]
        for p in low[:6]:
            unit = "kg" if p["stock_unit"] == "kg" else "left"
            lines.append(f"| {p['name']} | {p['stock_quantity']} {unit} |")
        return "\n".join(lines)

    if "customer" in msg:
        return "\n".join((
            "**Customers**",
            "",
            "| Metric | Count |",
            "| --- | --- |",
            f"| Active customers | {stats['customers']['total']} |",
            f"| New this month | {stats['customers']['new_this_month']} |",
        ))

    if "average" in msg and ("value" in msg or "order" in msg):
        return (
            "**Average order value (last 30 days)**\n"
            f"\n"
            f"{_fmt_money(stats['avg_order_value'])}"
        )

    return (
        "I can summarize dashboard stats, revenue, orders, customers and stock. "
        "Try: 'What's the monthly revenue?' or 'Any low stock?'."
    )


# ---------------------------------------------------------------------------
# Admin intents — one per /admin page, answered from the same live services
# ---------------------------------------------------------------------------

_ADMIN_INTENT_KEYWORDS = {
    # Order matters: first match wins, so specific pages come before broad
    # ones ("customer accounts" → customers, not profile).
    "notifications": ("notification", "unread", "alerts", "activity"),
    "shop": ("shop location", "store location", "shop address",
             "shop settings", "settings", "where is the shop",
             "delivery radius", "location", "address"),
    "products": ("product", "catalog", "catalogue", "categor", "stock",
                 "inventory", "top seller", "best seller"),
    "payments": ("payment", "transaction", "refund"),
    "debt": ("debt", "udhaar", "outstanding"),
    "customers": ("customer",),
    "orders": ("order",),
    "profile": ("profile", "account", "my details", "my info"),
    "dashboard": ("dashboard", "revenue", "sales", "turnover", "report",
                  "overview", "chart", "today"),
}


def _detect_admin_intent(normalized_msg: str) -> str | None:
    for intent, keywords in _ADMIN_INTENT_KEYWORDS.items():
        if any(kw in normalized_msg for kw in keywords):
            return intent
    return None


def _admin_dashboard_reply(shop) -> str:
    """Full dashboard overview — same services as GET /admin-dashboard/stats."""
    from apps.admin_dashboard.services import get_dashboard_stats

    stats = get_dashboard_stats(shop)
    return "\n".join((
        "**Dashboard overview**",
        "",
        _admin_revenue_block(stats),
        "",
        _admin_orders_block(stats),
        "",
        "**Customers & catalog**",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Active customers | {stats['customers']['total']} |",
        f"| New this month | {stats['customers']['new_this_month']} |",
        f"| Products | {stats['products']['total']} |",
        f"| Low stock items | {stats['products']['low_stock']} |",
        f"| Avg order value (30d) | {_fmt_money(stats['avg_order_value'])} |",
    ))


def _admin_notifications_reply(user) -> str:
    """Same feed as GET /admin-dashboard/notifications (recipient-scoped)."""
    from datetime import datetime

    from apps.admin_dashboard.activity import get_admin_notifications

    data = get_admin_notifications(user)
    unread = data["unread_count"]
    lines = [f"**Notifications** — {unread} unread"]
    results = data["results"][:5]
    if results:
        lines.append("")
        lines.append("| When | From | What |")
        lines.append("| --- | --- | --- |")
        for n in results:
            when = datetime.fromisoformat(n["created_at"]).strftime("%d %b %Y")
            lines.append(f"| {when} | {n['actor_name']} | {n['description']} |")
    else:
        lines.append("")
        lines.append("Nothing here yet — you're all caught up!")
    return "\n".join(lines)


def _admin_profile_reply(user) -> str:
    """The signed-in admin's own account (same serializer as /account)."""
    from apps.accounts.auth_service import serialize_user

    u = serialize_user(user)
    rows = [
        ("Name", u["full_name"] or "—"),
        ("Phone", u["phone"] or "—"),
        ("Role", u["role"]),
    ]
    if u.get("email"):
        rows.append(("Email", u["email"]))
    lines = [
        "**Your admin profile**",
        "",
        "| Field | Detail |",
        "| --- | --- |",
        *(f"| {label} | {value} |" for label, value in rows),
        "",
        "Manage it on the Account page (/account/profile).",
    ]
    return "\n".join(lines)


def _admin_shop_location_reply() -> str:
    """Live Shop row — the data behind /admin/settings."""
    shop = _get_active_shop()
    if shop is None:
        return "No shop is configured yet. Set it up under Admin → Settings."
    address = ", ".join(
        part for part in (
            shop.address_line1, shop.address_line2,
            shop.city, shop.state, shop.pincode,
        ) if part
    )
    coords = ""
    if shop.lat is not None and shop.lng is not None:
        coords = f"- Coordinates: {float(shop.lat):.5f}, {float(shop.lng):.5f}"
    lines = [
        f"**{shop.name}** — shop location",
        "",
        f"- Address: {address or 'not set'}",
    ]
    if coords:
        lines.append(coords)
    lines.extend((
        f"- Delivery radius: {float(shop.delivery_radius_km):g} km "
        f"(free ≥ {_fmt_money(shop.free_delivery_min_order)} order)",
        f"- Delivery charge beyond radius: {_fmt_money(shop.delivery_charge)}",
    ))
    if shop.timing_open and shop.timing_close:
        lines.append(
            f"- Open daily {shop.timing_open:%I:%M %p} – {shop.timing_close:%I:%M %p}"
        )
    lines.append("")
    lines.append("Edit it under Admin → Settings.")
    return "\n".join(lines)


def _admin_products_reply(shop) -> str:
    """Catalog overview — dashboard product stats + top sellers table."""
    from apps.admin_dashboard.services import (
        get_dashboard_stats,
        get_low_stock_products,
        get_top_products,
    )

    stats = get_dashboard_stats(shop)
    lines = [
        "**Products overview**",
        "",
        f"- Total products: {stats['products']['total']}",
        f"- Low stock: {stats['products']['low_stock']} item(s)",
    ]

    from apps.catalog.models import Category

    cats = Category.objects.prefetch_related("subcategories").order_by("name")
    cat_rows = []
    for cat in cats:
        count = sum(s.products.count() for s in cat.subcategories.all())
        subs = [s.name for s in cat.subcategories.all()]
        label = f"**{cat.name}**: {count} product(s)"
        if subs:
            label += f" ({', '.join(subs)})"
        cat_rows.append(f"- {label}")
    if cat_rows:
        lines.append("- Categories:")
        lines.extend(cat_rows)

    low = get_low_stock_products(shop)
    if low:
        lines.extend((
            "",
            "**Low-stock items**",
            "",
            "| Product | Stock left |",
            "| --- | --- |",
            *(
                f"| {p['name']} | {p['stock_quantity']} "
                f"{'kg' if p['stock_unit'] == 'kg' else 'left'} |"
                for p in low[:6]
            ),
        ))

    top = get_top_products(shop, limit=5)
    if top:
        lines.extend((
            "",
            "**Top sellers**",
            "",
            "| Product | Sold | Revenue | Stock |",
            "| --- | --- | --- | --- |",
            *(
                f"| {p['name']} | {p['total_sold']} | "
                f"{_fmt_money(p['total_revenue'])} | {p['stock_quantity']} |"
                for p in top
            ),
        ))
    return "\n".join(lines)


def _admin_payments_reply(shop) -> str:
    """Payments overview — Payment aggregates + latest paid orders."""
    from django.db.models import Sum

    from apps.orders.models import Order
    from apps.payments.models import Payment

    payments = Payment.objects.all()
    total_count = payments.count()
    captured = payments.filter(status__in=["captured", "paid"]).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")
    failed = payments.filter(status="failed").count()

    lines = [
        "**Payments overview**",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Payments recorded | {total_count} |",
        f"| Collected (captured/paid) | {_fmt_money(captured)} |",
        f"| Failed | {failed} |",
    ]
    recent = (
        Order.objects.select_related("user")
        .exclude(payment_method="")
        .order_by("-created_at")[:5]
    )
    if recent:
        lines.extend((
            "",
            "**Recent orders with payments**",
            "",
            "| Order | Customer | Method | Status | Amount |",
            "| --- | --- | --- | --- | --- |",
            *(
                f"| #{o.order_number} | {o.user.full_name} | {o.payment_method} | "
                f"{o.get_payment_status_display()} | {_fmt_money(o.grand_total)} |"
                for o in recent
            ),
        ))
    return "\n".join(lines)


def _admin_customers_reply(shop) -> str:
    """Customer list summary — same service as GET /admin-dashboard/customers."""
    from apps.admin_dashboard.services import get_customer_list, get_dashboard_stats

    stats = get_dashboard_stats(shop)
    lines = [
        "**Customers**",
        "",
        f"- Active: {stats['customers']['total']} · New this month: "
        f"{stats['customers']['new_this_month']}",
    ]
    top = get_customer_list(shop, limit=5)
    if top:
        lines.extend((
            "",
            "**Top customers by spend**",
            "",
            "| Customer | Orders | Total spent |",
            "| --- | --- | --- |",
            *(
                f"| {c['full_name'] or c['phone']} | {c['order_count']} | "
                f"{_fmt_money(c['total_spent'])} |"
                for c in top
            ),
        ))
    return "\n".join(lines)


def _admin_debt_reply() -> str:
    """Debt Book overview across books — same summaries as /admin/debt-book."""
    from apps.wallet.models import DebtBook
    from apps.wallet.services import get_debt_book_summary

    books = list(DebtBook.objects.select_related("user").all()[:50])
    if not books:
        return "No Debt Books exist yet — nothing outstanding."
    rows = []
    total_outstanding = Decimal("0.00")
    active_books = 0
    for book in books:
        outstanding = Decimal(get_debt_book_summary(book)["outstanding"])
        if outstanding > 0:
            active_books += 1
            total_outstanding += outstanding
            rows.append((book.display_name, outstanding))
    rows.sort(key=lambda r: r[1], reverse=True)
    lines = [
        "**Debt Book overview**",
        "",
        f"- Customers with debt: {active_books}",
        f"- Total outstanding: **{_fmt_money(total_outstanding)}**",
    ]
    if rows:
        lines.extend((
            "",
            "| Customer | Outstanding |",
            "| --- | --- |",
            *(f"| {name} | {_fmt_money(out)} |" for name, out in rows[:5]),
        ))
    lines.append("")
    lines.append("Manage it under Admin → Debt Book.")
    return "\n".join(lines)


def _admin_recent_orders_reply(shop) -> str:
    """Latest orders table — same service as GET /admin-dashboard/recent-orders."""
    from apps.admin_dashboard.services import get_recent_orders
    from apps.orders.models import Order

    recent = get_recent_orders(shop, limit=5)
    if not recent:
        return "No orders have been placed yet."
    status_labels = dict(Order._meta.get_field("status").choices)
    lines = [
        "**Recent orders**",
        "",
        "| Order | Customer | Status | Amount |",
        "| --- | --- | --- | --- |",
        *(
            f"| #{o['order_number']} | {o['user_name']} | "
            f"{status_labels.get(o['status'], o['status'])} | "
            f"{_fmt_money(o['grand_total'])} |"
            for o in recent
        ),
    ]
    return "\n".join(lines)


def _admin_intent_reply(message: str, user, shop) -> str | None:
    """Route an admin message to its page's live data. None = no page match."""
    intent = _detect_admin_intent(_normalize_message(message))
    if intent is None:
        return None

    if intent == "notifications":
        if user is None:
            return "Sign in as an admin to see your notifications."
        return _admin_notifications_reply(user)
    if intent == "shop":
        return _admin_shop_location_reply()
    if intent == "products":
        return _admin_products_reply(shop)
    if intent == "payments":
        return _admin_payments_reply(shop)
    if intent == "debt":
        return _admin_debt_reply()
    if intent == "customers":
        return _admin_customers_reply(shop)
    if intent == "orders":
        return "\n\n".join((_admin_orders_block_from(shop), _admin_recent_orders_reply(shop)))
    if intent == "profile":
        if user is None:
            return "Sign in as an admin to see your profile."
        return _admin_profile_reply(user)

    # dashboard — broad overview
    return _admin_dashboard_reply(shop)


def _admin_orders_block_from(shop) -> str:
    from apps.admin_dashboard.services import get_dashboard_stats

    return _admin_orders_block(get_dashboard_stats(shop))


# ---------------------------------------------------------------------------
# Assistant entry points (strictly separated audiences)
# ---------------------------------------------------------------------------

def _openai_reply(system_prompt: str, data_context: str, message: str, history) -> str | None:
    """Call OpenAI with the given scope; None when unavailable/failed."""
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        return None
    try:
        import openai

        client = openai.OpenAI(api_key=api_key)

        messages = [{"role": "system", "content": system_prompt}]
        if data_context:
            messages.append(
                {"role": "system", "content": f"Live data:\n{data_context}"}
            )
        for h in (history or [])[-6:]:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception:
        return None


def chat_assistant(
    message: str,
    user=None,
    history: list | None = None,
    delivery_location: dict | None = None,
) -> str:
    """CUSTOMER assistant. Customer-side data only; admin questions are
    refused before any LLM processing."""
    # Guardrail runs first — even in production the model never sees a
    # chance to answer admin-scope questions.
    if _is_admin_query(message):
        return refuse_admin_query()

    # Identity — "who are you?" introduces the assistant (never a human).
    identity = _identity_reply(message)
    if identity is not None:
        return identity

    # Account intents — Deliver-To location, latest order, Debt Book and
    # payments, straight from the requesting customer's live data.
    account_reply = _account_intent_reply(message, user, delivery_location)
    if account_reply is not None:
        return account_reply

    # Catalog intent — product/category keyword search on live DB data.
    products = _catalog_search_products(message)
    if products:
        reply = _openai_reply(
            CATALOG_SYSTEM_PROMPT,
            "\n".join(_product_line(p) for p in products),
            message,
            history,
        )
        if reply is not None:
            return reply
        return _catalog_reply_text(products)

    # Generic browse asks ("show products", "what categories exist?") and
    # shop-information questions — both answered from live data.
    generic = _generic_catalog_reply(message)
    if generic is not None:
        return generic

    shop_reply = _shop_info_reply(message)
    if shop_reply is not None:
        return shop_reply

    context = "\n\n".join(
        part
        for part in (_get_product_context(), _customer_context(user))
        if part
    )
    reply = _openai_reply(CUSTOMER_SYSTEM_PROMPT, context, message, history)
    if reply is not None:
        return reply
    return _rule_based_customer_chat(message, user)


def admin_chat_assistant(
    message: str,
    history: list | None = None,
    shop=None,
    user=None,
) -> str:
    """ADMIN assistant. Live admin aggregates only; callers must already be
    authenticated admins (enforced by the view's permissions)."""
    # Page-based intents — route to the same live services that power each
    # /admin page (dashboard, orders, products, payments, customers, debt,
    # notifications, settings, profile).
    intent_reply = _admin_intent_reply(message, user, shop)
    if intent_reply is not None:
        return intent_reply

    context = "\n\n".join(
        part for part in (_get_product_context(), _admin_context(shop)) if part
    )
    reply = _openai_reply(ADMIN_SYSTEM_PROMPT, context, message, history)
    if reply is not None:
        return reply
    return _admin_rule_chat(message, shop)


# ---------------------------------------------------------------------------
# Product Recommendations
# ---------------------------------------------------------------------------

def get_recommendations(user=None, product_id: str | None = None, limit: int = 8) -> list:
    """Get product recommendations.

    Strategy:
    1. If product_id provided: similar products (same subcategory, excluding self)
    2. If user provided: based on order history + trending
    3. Default: trending + featured products
    """
    from apps.catalog.models import Product
    from apps.orders.models import OrderItem

    base_qs = Product.objects.filter(is_available=True).select_related("subcategory")

    if product_id:
        try:
            target = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return list(base_qs.order_by("-times_sold")[:limit])

        # Same subcategory, excluding self
        similar = base_qs.filter(subcategory=target.subcategory).exclude(id=target.id)
        count = similar.count()

        if count >= limit:
            return list(similar.order_by("-avg_rating", "-times_sold")[:limit])

        # Fill remaining with trending from other subcategories
        remaining = limit - count
        trending = base_qs.exclude(
            Q(id=target.id) | Q(subcategory=target.subcategory)
        ).order_by("-times_sold")[:remaining]

        return list(similar) + list(trending)

    if user and user.is_authenticated:
        # Get user's purchased categories
        purchased_subcats = (
            OrderItem.objects.filter(order__user=user)
            .values_list("product__subcategory_id", flat=True)
            .distinct()
        )

        if purchased_subcats:
            # Recommend from same categories they like
            recs = base_qs.filter(
                subcategory_id__in=purchased_subcats
            ).exclude(
                order_items__order__user=user
            ).order_by("-avg_rating", "-times_sold")[:limit]

            if recs:
                return list(recs)

    # Default: trending + featured
    featured = list(base_qs.filter(is_featured=True)[:limit // 2])
    trending = list(base_qs.exclude(id__in=[p.id for p in featured]).order_by("-times_sold")[:limit - len(featured)])

    return featured + trending


# ---------------------------------------------------------------------------
# Smart Search
# ---------------------------------------------------------------------------

def smart_search(query: str, limit: int = 20) -> list:
    """Search products with natural language understanding.

    Handles:
    - Direct name/description matching
    - Category inference (e.g., "something sweet" -> bakery items)
    - Price range extraction
    - Fuzzy matching
    """
    from apps.catalog.models import Product

    if not query or not query.strip():
        return list(Product.objects.filter(is_available=True).order_by("-times_sold")[:limit])

    q = query.strip().lower()
    base_qs = Product.objects.filter(is_available=True).select_related("subcategory")

    # Category inference
    category_hints = {
        "sweet": ["bakery", "cake", "pastry"],
        "fresh": ["fresh", "fruit"],
        "fruit": ["fresh", "fruit"],
        "bread": ["bakery"],
        "cake": ["bakery", "cake"],
        "healthy": ["fresh", "salad"],
        "snack": ["bakery", "dry"],
        "breakfast": ["bakery", "fresh"],
    }

    results = Product.objects.none()
    matched_category = False

    for hint, keywords in category_hints.items():
        if hint in q:
            for kw in keywords:
                results = results | base_qs.filter(
                    Q(subcategory__name__icontains=kw)
                    | Q(name__icontains=kw)
                    | Q(description__icontains=kw)
                )
            matched_category = True
            break

    if not matched_category:
        # Standard text search
        results = base_qs.filter(
            Q(name__icontains=q)
            | Q(description__icontains=q)
            | Q(subcategory__name__icontains=q)
            | Q(brand__icontains=q)
            | Q(ingredients__icontains=q)
        )

    # Also try partial word matches
    words = q.split()
    if len(words) > 1:
        for word in words:
            if len(word) >= 3:
                results = results | base_qs.filter(
                    Q(name__icontains=word) | Q(description__icontains=word)
                )

    # Deduplicate and sort
    return list(results.distinct().order_by("-avg_rating", "-times_sold")[:limit])
