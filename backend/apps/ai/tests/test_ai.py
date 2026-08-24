"""Tests for AI app — chat, recommendations, search, audience separation."""
import pytest
from decimal import Decimal
from rest_framework.test import APIClient

from apps.ai.services import (
    admin_chat_assistant,
    chat_assistant,
    get_recommendations,
    smart_search,
)
from apps.catalog.models import Category, Subcategory, Product


@pytest.fixture(autouse=True)
def no_openai(settings):
    """Force the rule-based engines in every AI test (no network)."""
    settings.OPENAI_API_KEY = ""


@pytest.fixture
def bakery_category(db):
    return Category.objects.create(name="Bakery", slug="bakery")


@pytest.fixture
def cakes_sub(db, bakery_category):
    return Subcategory.objects.create(category=bakery_category, name="Cakes", slug="cakes")


@pytest.fixture
def fruits_category(db):
    return Category.objects.create(name="Fruits", slug="fruits")


@pytest.fixture
def fresh_sub(db, fruits_category):
    return Subcategory.objects.create(category=fruits_category, name="Fresh", slug="fresh-fruits")


@pytest.fixture
def products(db, cakes_sub, fresh_sub):
    items = []
    for name, sub, price, sold, sku in [
        ("Chocolate Cake", cakes_sub, "250.00", 200, "AI-CHOC-001"),
        ("Vanilla Cake", cakes_sub, "200.00", 150, "AI-VAN-001"),
        ("Mango", fresh_sub, "80.00", 300, "AI-MANGO-001"),
        ("Banana", fresh_sub, "40.00", 500, "AI-BANA-001"),
    ]:
        items.append(Product.objects.create(
            subcategory=sub,
            name=name,
            slug=name.lower().replace(" ", "-"),
            base_price=Decimal(price),
            stock_quantity=100,
            is_available=True,
            times_sold=sold,
            sku=sku,
        ))
    return items


@pytest.mark.django_db
class TestChatAssistant:
    def test_greeting(self):
        response = chat_assistant("hello")
        assert response is not None
        assert len(response) > 0

    def test_recommend_request(self):
        response = chat_assistant("what do you recommend?")
        assert "recommend" in response.lower() or "cake" in response.lower() or "mango" in response.lower()

    def test_delivery_question(self):
        response = chat_assistant("how does delivery work?")
        assert "delivery" in response.lower() or "99" in response or "km" in response.lower()

    def test_empty_message(self):
        response = chat_assistant("")
        assert response is not None

    def test_fallback(self):
        response = chat_assistant("xyzzy")
        assert response is not None


@pytest.mark.django_db
class TestRecommendations:
    def test_returns_products(self, products):
        recs = get_recommendations(limit=4)
        assert len(recs) <= 4

    def test_same_category(self, products, cakes_sub):
        # Get chocolate cake recommendations
        chocolate = Product.objects.get(name="Chocolate Cake")
        recs = get_recommendations(product_id=str(chocolate.id), limit=4)
        # Should include vanilla (same category)
        names = [r.name for r in recs]
        assert "Vanilla Cake" in names

    def test_empty_catalog(self, db):
        recs = get_recommendations()
        assert recs == []


@pytest.mark.django_db
class TestSmartSearch:
    def test_search_by_name(self, products):
        results = smart_search("chocolate")
        assert any("Chocolate" in r.name for r in results)

    def test_search_by_category(self, products):
        results = smart_search("cakes")
        assert len(results) > 0

    def test_search_fruit(self, products):
        results = smart_search("mango")
        assert any("Mango" in r.name for r in results)

    def test_empty_query(self, products):
        results = smart_search("")
        # Empty query returns all available products (default behavior)
        assert len(results) <= len(products)

    def test_no_match(self, products):
        results = smart_search("xyznonexistent")
        assert results == []


# ---------------------------------------------------------------------------
# Audience separation — customer vs admin assistants
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCustomerAssistantScope:
    """The customer assistant must never answer admin-scope questions."""

    ADMIN_QUESTIONS = [
        "What is the monthly revenue on the dashboard?",
        "Show me the admin report",
        "How many customers do we have in total?",
        "What's our total sales this month?",
        "Any low stock items I should restock?",
    ]

    def test_admin_questions_refused(self):
        from apps.ai.services import ADMIN_QUERY_REFUSAL

        for q in self.ADMIN_QUESTIONS:
            response = chat_assistant(q)
            assert response == ADMIN_QUERY_REFUSAL

    def test_refusal_even_for_authenticated_customer(self, user):
        from apps.ai.services import ADMIN_QUERY_REFUSAL

        response = chat_assistant("show me the dashboard revenue", user=user)
        assert response == ADMIN_QUERY_REFUSAL

    def test_answers_own_data_questions(self, user):
        # Data-aware (no crash) and customer-scoped.
        response = chat_assistant("where is my order?", user=user)
        assert "haven't placed any orders" in response.lower()

    def test_wallet_answer_uses_real_balance(self, user, shop):
        from apps.wallet.models import WalletLedger

        WalletLedger.objects.create(
            user=user, shop=shop, delta=Decimal("25.00"),
            balance_after=Decimal("25.00"), reason="purchase_cashback",
        )
        response = chat_assistant("what is my cashback balance?", user=user)
        assert "25.00" in response


@pytest.mark.django_db
class TestCatalogIntent:
    """Product/category keywords return live catalog data (customer scope)."""

    def test_bare_product_keyword(self, products):
        response = chat_assistant("mango")
        assert "Mango" in response
        assert "80.00" in response
        assert "Fresh" in response

    def test_show_me_variation(self, products):
        response = chat_assistant("show me mango")
        assert "Mango" in response

    def test_question_form_category(self, products):
        response = chat_assistant("what fruits do you have?")
        assert "Mango" in response and "Banana" in response

    def test_plural_and_singular_category_forms(self, products):
        for q in ("show fruits", "fruit products"):
            assert "Mango" in chat_assistant(q)

    def test_subcategory_keyword(self, products):
        response = chat_assistant("do you have cakes?")
        assert "Chocolate Cake" in response and "Vanilla Cake" in response

    def test_out_of_stock_flagged(self, cakes_sub):
        Product.objects.create(
            subcategory=cakes_sub, name="Sold Out Tart", slug="sold-out-tart",
            base_price=Decimal("99.00"), stock_quantity=0,
            is_available=True, sku="AI-SOLD-001",
        )
        assert "out of stock" in chat_assistant("tart").lower()

    def test_unavailable_products_never_listed(self, db):
        cat = Category.objects.create(name="Snacks", slug="snacks-ai")
        sub = Subcategory.objects.create(category=cat, name="Chips", slug="chips-ai")
        Product.objects.create(
            subcategory=sub, name="Hidden Chips", slug="hidden-chips",
            base_price=Decimal("10.00"), stock_quantity=5,
            is_available=False, sku="AI-HIDE-001",
        )
        assert "Hidden Chips" not in chat_assistant("chips")

    def test_unknown_keyword_still_falls_back(self, products):
        from apps.ai.services import FALLBACK_RESPONSES

        assert chat_assistant("xyzzy") in FALLBACK_RESPONSES

    def test_wallet_intent_not_hijacked(self, products):
        assert "cashback" in chat_assistant("my wallet balance").lower()

    def test_order_intent_not_hijacked(self, user):
        response = chat_assistant("where is my order?", user=user)
        assert "haven't placed any orders" in response.lower()

    def test_endpoint_returns_live_products(self, products):
        res = APIClient().post(
            "/api/v1/ai/chat/", {"message": "mango"}, format="json"
        )
        assert res.status_code == 200
        assert "Mango" in res.data["response"]


@pytest.mark.django_db
class TestAccountIntents:
    """/account-section keywords return the requesting customer's live data."""

    def _order(self, user, shop, number="ORD-AI-1"):
        from apps.orders.models import Order

        return Order.objects.create(
            user=user, shop=shop, order_number=number,
            status="out_for_delivery", payment_status="paid",
            grand_total=Decimal("250.00"),
        )

    # ── Location / Deliver To ─────────────────────────────────────────────

    def test_location_returns_deliver_to(self, user):
        reply = chat_assistant(
            "What is my location?", user=user,
            delivery_location={"label": "MG Road, Bengaluru", "lat": 12.97, "lon": 77.59},
        )
        assert "MG Road, Bengaluru" in reply

    def test_where_should_my_order_be_delivered(self, user):
        reply = chat_assistant(
            "Where should my order be delivered?", user=user,
            delivery_location={"label": "Indiranagar 100ft Rd", "lat": 12.97, "lon": 77.64},
        )
        assert "Indiranagar 100ft Rd" in reply

    def test_location_not_set_guidance(self, user):
        assert "Deliver To" in chat_assistant("what is my address?", user=user)

    def test_location_guest_prompted(self):
        assert "sign in" in chat_assistant("my location").lower()

    def test_endpoint_passes_client_location(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        res = client.post(
            "/api/v1/ai/chat/",
            {"message": "what is my location?",
             "location": {"label": "MG Road", "lat": 12.9, "lon": 77.6}},
            format="json",
        )
        assert res.status_code == 200
        assert "MG Road" in res.data["response"]

    # ── Orders ────────────────────────────────────────────────────────────

    def test_latest_order_live_data(self, user, shop, products):
        order = self._order(user, shop)
        from apps.orders.models import OrderItem

        mango = Product.objects.get(name="Mango")
        OrderItem.objects.create(
            order=order, product=mango,
            product_name="Alphonso Mango", quantity=2,
        )
        reply = chat_assistant("What is my latest order?", user=user)
        assert "#ORD-AI-1" in reply
        assert "Out for Delivery" in reply
        assert "250.00" in reply
        assert "2× Alphonso Mango" in reply

    def test_show_my_order_variation(self, user, shop):
        self._order(user, shop)
        assert "#ORD-AI-1" in chat_assistant("show my order", user=user)

    def test_no_orders_message(self, user):
        response = chat_assistant("where is my order?", user=user)
        assert "haven't placed any orders" in response.lower()

    def test_orders_guest_prompted(self):
        assert "sign in" in chat_assistant("show my order").lower()

    # ── Debt Book ─────────────────────────────────────────────────────────

    def _debt_book(self, user, shop):
        from apps.wallet.models import DebtBook

        return DebtBook.objects.create(user=user, shop=shop)

    def test_debt_balance_from_own_ledger(self, user, shop):
        from apps.wallet.models import DebtLedger

        book = self._debt_book(user, shop)
        DebtLedger.objects.create(
            book=book, user=user, shop=shop, entry_type="bill",
            delta=Decimal("300.00"), balance_after=Decimal("300.00"),
        )
        DebtLedger.objects.create(
            book=book, user=user, shop=shop, entry_type="payment",
            delta=Decimal("-100.00"), balance_after=Decimal("200.00"),
        )
        reply = chat_assistant("Do I have any debt?", user=user)
        assert "200.00" in reply
        assert "outstanding" in reply.lower()

    def test_debt_uses_book_anchor_like_account_page(self, user, shop):
        """/account/debt-book reads book.entries — linked offline history
        keeps ledger rows user-NULL; the AI must still see it."""
        from apps.wallet.models import DebtLedger

        book = self._debt_book(user, shop)
        DebtLedger.objects.create(
            book=book, user=None, shop=shop, entry_type="bill",
            product_name="Chocolate Cake", quantity=1,
            unit_price=Decimal("450.00"),
            delta=Decimal("450.00"), balance_after=Decimal("450.00"),
        )
        reply = chat_assistant("show my outstanding balance", user=user)
        assert "450.00" in reply
        assert "clear" not in reply.lower()

    def test_debt_book_keyword_not_refused_as_admin(self, user, shop):
        from apps.ai.services import ADMIN_QUERY_REFUSAL
        from apps.wallet.models import DebtLedger

        book = self._debt_book(user, shop)
        DebtLedger.objects.create(
            book=book, user=user, shop=shop, entry_type="bill",
            delta=Decimal("150.00"), balance_after=Decimal("150.00"),
        )
        reply = chat_assistant("Show my debt book", user=user)
        assert reply != ADMIN_QUERY_REFUSAL
        assert "150.00" in reply

    def test_debt_isolated_per_customer(self, user, shop, db):
        from django.contrib.auth import get_user_model

        from apps.wallet.models import DebtBook, DebtLedger

        other = get_user_model().objects.create_user(
            phone="+919876543299", email="other@pachoos.com",
            password="x1234567", full_name="Other Customer", role="customer",
        )
        other_book = DebtBook.objects.create(user=other, shop=shop)
        DebtLedger.objects.create(
            book=other_book, user=other, shop=shop, entry_type="bill",
            delta=Decimal("999.00"), balance_after=Decimal("999.00"),
        )
        reply = chat_assistant("do i owe anything on my debt book?", user=user)
        assert "999" not in reply
        assert "clear" in reply.lower()

    def test_outstanding_keyword_triggers_debt(self, user, shop):
        book = self._debt_book(user, shop)
        from apps.wallet.models import DebtLedger

        DebtLedger.objects.create(
            book=book, user=user, shop=shop, entry_type="bill",
            delta=Decimal("75.50"), balance_after=Decimal("75.50"),
        )
        assert "75.50" in chat_assistant("any outstanding?", user=user)

    def test_no_debt_all_clear(self, user):
        assert "clear" in chat_assistant("show my debt", user=user).lower()

    # ── Payments ──────────────────────────────────────────────────────────

    def test_latest_payment_live_data(self, user, shop):
        order = self._order(user, shop)
        from apps.payments.models import Payment

        Payment.objects.create(
            order=order, user=user, method="demo_upi",
            amount=Decimal("250.00"), status="captured",
        )
        reply = chat_assistant("What was my latest payment?", user=user)
        assert "250.00" in reply
        assert "#ORD-AI-1" in reply
        assert "Captured" in reply
        assert "UPI" in reply

    def test_payment_none_message(self, user):
        reply = chat_assistant("show my payments", user=user)
        assert "haven't made any payments" in reply.lower()

    def test_payments_guest_prompted(self):
        assert "sign in" in chat_assistant("my payments").lower()

    # ── Location vs Shop disambiguation ──────────────────────────────────

    def test_your_address_answers_shop_not_customer(self, shop):
        reply = chat_assistant("what is your address?")
        assert "123 Test Street" in reply
        assert "Deliver To" not in reply


@pytest.mark.django_db
class TestCartIntent:
    """Cart questions return the authenticated customer's live cart."""

    def _cart_with_items(self, user, shop, products):
        from apps.cart.models import Cart, CartItem

        cart = Cart.objects.create(user=user, shop=shop)
        CartItem.objects.create(
            cart=cart, product=products[0], quantity=2,
        )
        return cart

    def test_live_cart_products(self, user, shop, products):
        self._cart_with_items(user, shop, products)
        reply = chat_assistant("what's in my cart?", user=user)
        assert "2× Chocolate Cake" in reply
        assert "Subtotal" in reply

    def test_empty_cart_message(self, user, shop):
        assert "empty" in chat_assistant("my cart", user=user).lower()

    def test_cart_guest_prompted(self):
        assert "sign in" in chat_assistant("show my cart products").lower()


@pytest.mark.django_db
class TestShopInfoIntent:
    """Shop questions answer from the live Shop row."""

    def test_shop_location_and_name(self, shop):
        reply = chat_assistant("where is the shop located?")
        assert "PACHOOS Test Shop" in reply
        assert "123 Test Street" in reply

    def test_shop_delivery_details(self, shop):
        reply = chat_assistant("what are your delivery charges?")
        assert "free within 2 km" in reply
        assert "20.00" in reply

    def test_shop_timings_when_set(self, db):
        from datetime import time

        from apps.shops.models import Shop

        Shop.objects.create(
            name="Timed Shop", slug="timed-shop",
            timing_open=time(9, 0), timing_close=time(21, 0),
        )
        reply = chat_assistant("what are your timings?")
        assert "09:00 AM" in reply and "09:00 PM" in reply

    def test_password_change_instructions(self, user):
        reply = chat_assistant("how do I change my password?", user=user)
        assert "password" in reply.lower()
        assert "/account/settings" in reply or "Settings" in reply
        assert "/forgot-password" in reply


@pytest.mark.django_db
class TestShopBrandIdentityProfile:
    """Brand ("Pachoos"), shop-location, identity and profile intents."""

    def test_what_is_pachoos_brand_reply(self, shop, products):
        reply = chat_assistant("what is Pachoos?")
        assert "PACHOOS Test Shop" in reply
        assert "What we offer" in reply
        assert "Bakery" in reply

    def test_about_pachoos_variation(self, shop):
        assert "PACHOOS Test Shop" in chat_assistant("tell me about pachoos")

    def test_where_is_pachoos_location_focused(self, shop):
        reply = chat_assistant("where is Pachoos?")
        assert "123 Test Street" in reply
        assert "deliver within 2 km" in reply
        # Focused answer — not the full brand block.
        assert "cashback" not in reply.lower()

    def test_shop_location_bare_variation(self, shop):
        assert "123 Test Street" in chat_assistant("shop location")

    def test_pachoos_cakes_still_lists_products(self, shop, products):
        # Brand name must not hijack product searches.
        reply = chat_assistant("pachoos cakes")
        assert "Chocolate Cake" in reply
        assert "PACHOOS Test Shop is located" not in reply

    def test_who_are_you_identity(self):
        reply = chat_assistant("who are you?")
        assert "AI assistant" in reply
        assert "not a human" in reply
        assert "Debt Book" in reply

    def test_are_you_bot_variation(self):
        assert "AI assistant" in chat_assistant("are you a bot?")

    def test_what_can_you_do_variation(self):
        assert "AI assistant" in chat_assistant("what can you do?")

    def test_identity_not_triggered_by_domain_questions(self, user):
        reply = chat_assistant("what are you doing with my order?", user=user)
        assert "haven't placed any orders" in reply.lower()

    def test_profile_live_data(self, user):
        reply = chat_assistant("my profile", user=user)
        assert "Test User" in reply
        assert "+919876543210" in reply
        assert "test@pachoos.com" in reply
        assert "Referral code" in reply

    def test_account_details_variation(self, user):
        assert "Test User" in chat_assistant("show my account details", user=user)

    def test_profile_guest_prompted(self):
        assert "sign in" in chat_assistant("my profile").lower()


@pytest.mark.django_db
class TestGenericCatalogBrowse:
    """Broad product/category asks list live catalog data."""

    def test_show_products_lists_live_catalog(self, products):
        reply = chat_assistant("what products do you have?")
        assert "Mango" in reply and "Chocolate Cake" in reply

    def test_show_categories_lists_tree(self, products):
        reply = chat_assistant("show categories")
        assert "Bakery" in reply and "Cakes" in reply
        assert "Fruits" in reply and "Fresh" in reply

    def test_what_categories_are_available(self, products):
        assert "Fruits" in chat_assistant("what categories are available?")

    def test_specific_category_still_targeted(self, products):
        # "fruit products" must list fruits, not the whole catalog.
        reply = chat_assistant("show fruit products")
        assert "Mango" in reply
        assert "Chocolate Cake" not in reply


@pytest.mark.django_db
class TestAdminAssistantScope:
    """The admin assistant answers from live admin aggregates only."""

    def test_revenue_question_returns_dashboard_figure(self, shop):
        from apps.admin_dashboard.services import get_dashboard_stats

        expected = get_dashboard_stats(shop)["revenue"]["monthly"]
        response = admin_chat_assistant("What's the monthly revenue?", shop=shop)
        assert str(expected) in response or "0.00" in response

    def test_stock_question_lists_low_items(self, shop):
        from apps.catalog.models import Category, Subcategory

        cat = Category.objects.create(name="C", slug="c-ai-scope")
        sub = Subcategory.objects.create(category=cat, name="S", slug="s-ai-scope")
        Product.objects.create(
            subcategory=sub, name="Nearly Gone Juice", slug="nearly-gone",
            base_price=Decimal("50.00"), stock_quantity=2,
            is_available=True, sku="AI-SCOPE-001",
        )
        response = admin_chat_assistant("any low stock?", shop=shop)
        assert "Nearly Gone Juice" in response

    def test_scoped_to_shop(self, db, shop):
        """No orders → revenue is ₹0, never another shop's data."""
        response = admin_chat_assistant("total revenue", shop=shop)
        assert "₹0.00" in response


@pytest.mark.django_db
class TestAdminIntentRouting:
    """Every /admin page routes to its live data via keywords."""

    def test_dashboard_overview(self, shop):
        reply = admin_chat_assistant("show me the dashboard", shop=shop)
        assert "**Revenue overview**" in reply
        assert "Orders snapshot" in reply
        assert "Low stock items" in reply

    def test_notifications_live_and_recipient_scoped(self, admin_user, db):
        from apps.admin_dashboard.models import AdminNotification

        AdminNotification.objects.create(
            recipient=admin_user, actor=None,
            action="product.updated", entity_type="product",
            description="Updated stock for Mango",
        )
        reply = admin_chat_assistant("any new notifications?", user=admin_user)
        assert "1 unread" in reply
        assert "Updated stock for Mango" in reply

    def test_admin_profile_uses_own_account(self, admin_user):
        reply = admin_chat_assistant("my profile", user=admin_user)
        assert "Admin User" in reply
        assert "super_admin" in reply
        assert "admin@pachoos.com" in reply

    def test_shop_location_settings(self, shop):
        reply = admin_chat_assistant("what is the shop location?", shop=shop)
        assert "123 Test Street" in reply
        assert "12.97160" in reply
        assert "Delivery radius: 2 km" in reply

    def test_products_overview_with_top_sellers(self, shop, products, user):
        from apps.orders.models import Order, OrderItem

        order = Order.objects.create(
            user=user, shop=shop, order_number="ORD-TP-1",
            payment_status="paid", grand_total=Decimal("240.00"),
        )
        OrderItem.objects.create(
            order=order, product=products[3],
            product_name="Banana", quantity=6,
        )
        reply = admin_chat_assistant("products overview", shop=shop)
        assert "Total products: 4" in reply
        assert "Top sellers" in reply
        assert "Banana" in reply

    def test_payments_overview(self, shop, user):
        from apps.orders.models import Order
        from apps.payments.models import Payment

        order = Order.objects.create(
            user=user, shop=shop, order_number="ORD-PAY-1",
            payment_method="demo_upi", payment_status="paid",
            grand_total=Decimal("250.00"),
        )
        Payment.objects.create(
            order=order, user=user, method="demo_upi",
            amount=Decimal("250.00"), status="captured",
        )
        reply = admin_chat_assistant("payments this month", shop=shop)
        assert "Collected (captured/paid)" in reply
        assert "250.00" in reply
        assert "#ORD-PAY-1" in reply

    def test_customers_top_spenders(self, shop, user):
        from apps.orders.models import Order

        Order.objects.create(
            user=user, shop=shop, order_number="ORD-C-1",
            payment_status="paid", grand_total=Decimal("500.00"),
        )
        reply = admin_chat_assistant("how many customers do we have?", shop=shop)
        assert "Test User" in reply
        assert "500.00" in reply

    def test_debt_book_overview(self, shop, user):
        from apps.wallet.models import DebtBook, DebtLedger

        book = DebtBook.objects.create(user=user, shop=shop)
        DebtLedger.objects.create(
            book=book, user=user, shop=shop, entry_type="bill",
            delta=Decimal("300.00"), balance_after=Decimal("300.00"),
        )
        reply = admin_chat_assistant("debt book summary", shop=shop)
        assert "Total outstanding" in reply
        assert "300.00" in reply

    def test_orders_includes_recent_table(self, shop, user):
        from apps.orders.models import Order

        Order.objects.create(
            user=user, shop=shop, order_number="ORD-O-1",
            grand_total=Decimal("99.00"),
        )
        reply = admin_chat_assistant("orders today", shop=shop)
        assert "#ORD-O-1" in reply
        assert "Recent orders" in reply

    def test_monthly_revenue_still_answered(self, shop):
        reply = admin_chat_assistant("what's the monthly revenue?", shop=shop)
        assert "Revenue overview" in reply
        assert "This month" in reply

    def test_endpoint_passes_admin_user_for_intents(self, admin_user, db):
        from apps.admin_dashboard.models import AdminNotification

        AdminNotification.objects.create(
            recipient=admin_user, actor=None,
            action="product.updated", entity_type="product",
            description="Stock patched by other admin",
        )
        client = APIClient()
        client.force_authenticate(admin_user)
        res = client.post(
            "/api/v1/ai/admin-chat/",
            {"message": "show notifications"}, format="json",
        )
        assert res.status_code == 200
        assert "Stock patched by other admin" in res.data["response"]


@pytest.mark.django_db
class TestChatEndpointPermissions:
    """Endpoint-level separation: /chat/ = customer scope, /admin-chat/ = admins."""

    def _post(self, url, message):
        return APIClient().post(url, {"message": message}, format="json")

    def test_anonymous_can_use_customer_chat(self):
        res = self._post("/api/v1/ai/chat/", "hello")
        assert res.status_code == 200
        assert res.data["response"]

    def test_customer_cannot_use_admin_chat(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        res = client.post(
            "/api/v1/ai/admin-chat/", {"message": "monthly revenue?"},
            format="json",
        )
        assert res.status_code == 403

    def test_anonymous_cannot_use_admin_chat(self):
        res = self._post("/api/v1/ai/admin-chat/", "monthly revenue?")
        assert res.status_code in (401, 403)

    def test_admin_gets_admin_chat(self, admin_user):
        client = APIClient()
        client.force_authenticate(admin_user)
        res = client.post(
            "/api/v1/ai/admin-chat/", {"message": "How many pending orders?"},
            format="json",
        )
        assert res.status_code == 200
        assert res.data["response"]
        assert res.data["suggestions"]

    def test_staff_on_customer_endpoint_treated_as_guest(self, admin_user):
        """Staff calling the customer endpoint get NO personal grounding but
        still only customer-scope answers (admin question refused)."""
        client = APIClient()
        client.force_authenticate(admin_user)
        res = client.post("/api/v1/ai/chat/", {"message": "show the dashboard"}, format="json")
        assert res.status_code == 200
        from apps.ai.services import ADMIN_QUERY_REFUSAL

        assert res.data["response"] == ADMIN_QUERY_REFUSAL
