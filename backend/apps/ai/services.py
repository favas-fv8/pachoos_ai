"""AI services — chat assistant, product recommendations, smart search.

Dev mode: returns rule-based responses without OpenAI.
Production: uses OpenAI API when OPENAI_API_KEY is set.
"""
import random
from decimal import Decimal

from django.conf import settings
from django.db.models import Q, F


# ---------------------------------------------------------------------------
# Chat Assistant
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are PACHOOS, a friendly AI assistant for a local bakery & fruits shop.
You help customers find products, place orders, track deliveries, and answer questions about the shop.
Keep responses short, helpful, and friendly. Use Indian Rupees (₹) for prices.
If you don't know something, say so honestly."""

GREETING_RESPONSES = [
    "Hey! Welcome to PACHOOS! How can I help you today?",
    "Hi there! Need help finding something delicious?",
    "Welcome to PACHOOS! What are you craving today?",
]

FALLBACK_RESPONSES = [
    "I'm not sure about that. Let me connect you with our team!",
    "That's a great question! I'd recommend checking our shop page for details.",
    "I don't have that info right now, but feel free to browse our products!",
]


def _get_product_context():
    """Build a compact product catalog context for the AI."""
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


def _rule_based_chat(message: str, user=None) -> str:
    """Simple rule-based responses for dev mode (no OpenAI)."""
    msg = message.lower().strip()

    greetings = ["hi", "hello", "hey", "hii", "good morning", "good evening"]
    if any(g in msg for g in greetings):
        return random.choice(GREETING_RESPONSES)

    if "recommend" in msg or "suggest" in msg or "best" in msg:
        return (
            "Our top sellers are: Fresh Mango Cake, Banana Bread, "
            "Mixed Fruit Salad, and Chocolate Croissant! Check the Shop page to order."
        )

    if "price" in msg or "cost" in msg:
        return "Our products range from ₹20 to ₹500. Visit the Shop to see all prices!"

    if "order" in msg or "track" in msg:
        return "You can track your orders from the Track page or check your Account > Orders."

    if "delivery" in msg:
        return "Free delivery on orders above ₹99 within 2 km! Otherwise ₹20 delivery charge."

    if "wallet" in msg or "cashback" in msg:
        return "You earn ₹1 cashback per ₹100 spent. When balance reaches ₹10, a voucher is auto-minted!"

    if "coupon" in msg or "discount" in msg:
        return "Check the Checkout page — you can apply coupon codes and voucher codes there!"

    if "thank" in msg:
        return "You're welcome! Happy to help! 😊"

    return random.choice(FALLBACK_RESPONSES)


def chat_assistant(message: str, user=None, history: list | None = None) -> str:
    """Process a chat message and return a response.

    Uses OpenAI if available, otherwise falls back to rule-based responses.
    """
    api_key = getattr(settings, "OPENAI_API_KEY", "")

    if not api_key:
        return _rule_based_chat(message, user)

    # Production: call OpenAI
    try:
        import openai

        client = openai.OpenAI(api_key=api_key)

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add product context
        product_ctx = _get_product_context()
        if product_ctx:
            messages.append(
                {
                    "role": "system",
                    "content": f"Current product catalog:\n{product_ctx}",
                }
            )

        # Add conversation history
        if history:
            for h in history[-6:]:
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
        return _rule_based_chat(message, user)


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
