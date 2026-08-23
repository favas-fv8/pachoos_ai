"""Tests for the cart → order → demo-payment flow.

Covers: single-discount cart totals (the old double-discount bug), place_order
snapshotting, idempotent payment confirmation (double-click / refresh safe),
stock deducted exactly once via the StockMovement ledger, cashback credited
exactly once, the failed-payment path, the demo payment service/view, and the
admin order endpoints used by the orders page.
"""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.cart.models import Cart, CartItem
from apps.cart.services import compute_cart_summary
from apps.catalog.models import (
    Category,
    Product,
    ProductVariant,
    StockMovement,
    Subcategory,
)
from apps.orders.models import Order
from apps.orders.services import (
    mark_payment_failed,
    mark_payment_successful,
    place_order,
)
from apps.payments.gateway import DemoPaymentGateway
from apps.payments.models import Payment
from apps.payments.services import process_demo_payment

# The conftest ``shop`` fixture sits here; offsetting the customer's latitude
# by km / KM_PER_DEG_LAT yields a north-south distance of (almost exactly) km.
SHOP_LAT, SHOP_LNG = 12.9716, 77.5946
KM_PER_DEG_LAT = 111.19492664455874

# ~1 km away → free delivery (within the 2 km radius).
NEAR_COORDS = {
    "customer_lat": SHOP_LAT + 1.0 / KM_PER_DEG_LAT,
    "customer_lon": SHOP_LNG,
}
# ~2.5 km away → ₹40 delivery charge.
FAR_COORDS = {
    "customer_lat": SHOP_LAT + 2.5 / KM_PER_DEG_LAT,
    "customer_lon": SHOP_LNG,
}


@pytest.fixture
def category(db):
    return Category.objects.create(name="Bakery", slug="bakery")


@pytest.fixture
def subcategory(db, category):
    return Subcategory.objects.create(category=category, name="Cakes", slug="cakes")


@pytest.fixture
def product(db, subcategory):
    """250 base, 10% discount → 225 effective, 5% GST."""
    return Product.objects.create(
        subcategory=subcategory,
        name="Chocolate Cake",
        slug="chocolate-cake",
        base_price=Decimal("250.00"),
        discount_percent=Decimal("10.00"),
        gst_percent=Decimal("5.00"),
        stock_quantity=50,
        is_available=True,
    )


@pytest.fixture
def variant(db, product):
    return ProductVariant.objects.create(
        product=product,
        name="1kg",
        price=Decimal("300.00"),
        discount_percent=Decimal("20.00"),
        stock_quantity=30,
    )


@pytest.fixture
def cart(db, user, shop):
    return Cart.objects.create(user=user, shop=shop, is_active=True)


@pytest.fixture
def cart_with_item(db, cart, product):
    """unit_price deliberately stored at the FULL (pre-discount) price — the
    old buggy shape. Services must still price at the discounted effective
    price so the discount is never applied twice."""
    CartItem.objects.create(
        cart=cart,
        product=product,
        quantity=2,
        unit_price=Decimal("250.00"),
        discount_percent=Decimal("10.00"),
    )
    return cart


@pytest.fixture
def customer_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def customer2(db):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create_user(
        phone="+919876543222",
        email="customer2@pachoos.com",
        password="testpass123",
        full_name="Second Customer",
        role="customer",
    )


@pytest.mark.django_db
class TestCartSummaryNoDoubleDiscount:
    def test_subtotal_uses_effective_price_once(self, cart_with_item):
        summary = compute_cart_summary(cart_with_item, **NEAR_COORDS)
        assert summary["subtotal"] == 450.0
        assert summary["base_subtotal"] == 500.0
        assert summary["product_discount"] == 50.0
        assert summary["tax_total"] == 22.5
        assert summary["delivery_free"] is True
        assert summary["delivery_charge"] == 0.0
        assert summary["grand_total"] == 472.5
        assert summary["items"][0]["line_total"] == 450.0

    def test_variant_discount_used(self, cart, variant):
        CartItem.objects.create(
            cart=cart,
            product=variant.product,
            variant=variant,
            quantity=1,
            unit_price=Decimal("300.00"),
        )
        summary = compute_cart_summary(cart, **NEAR_COORDS)
        assert summary["subtotal"] == 240.0
        assert summary["product_discount"] == 60.0

    def test_line_total_property_not_double_discounted(self, cart_with_item):
        item = cart_with_item.items.get()
        # effective 225 * qty 2 — NOT 225 * 0.9 again
        assert item.line_total == 450.0

    def test_paid_delivery_breaks_past_distance(self, cart_with_item):
        """~2.5 km away → ₹40 charge on top of the item totals."""
        summary = compute_cart_summary(cart_with_item, **FAR_COORDS)
        assert summary["distance_km"] == 2.5
        assert summary["delivery_charge"] == 40.0
        assert summary["delivery_free"] is False
        assert summary["grand_total"] == 512.5

    def test_missing_coords_apply_standard_delivery(self, cart_with_item):
        summary = compute_cart_summary(cart_with_item)
        assert summary["distance_km"] is None
        assert summary["delivery_free"] is False
        assert summary["delivery_charge"] == 40.0
        assert summary["grand_total"] == 512.5


@pytest.mark.django_db
class TestPlaceOrder:
    def test_creates_order_with_correct_totals(self, cart_with_item, user):
        order = place_order(
            cart=cart_with_item,
            user=user,
            delivery_address_id=1,
            **NEAR_COORDS,
            payment_method="demo_upi",
        )
        assert order.payment_status == "pending"
        assert order.payment_method == "demo_upi"
        assert order.status == "pending"
        assert len(order.order_number) <= 32
        assert order.order_number.startswith("PCH-")
        assert order.subtotal == Decimal("450.00")
        assert order.discount_total == Decimal("50.00")
        assert order.tax_total == Decimal("22.50")
        assert order.grand_total == Decimal("472.50")
        assert order.distance_km == Decimal("1.00")
        assert order.delivery_free is True
        assert order.cashback_earned > 0

    def test_far_order_stores_distance_and_delivery_charge(self, cart_with_item, user):
        order = place_order(
            cart=cart_with_item,
            user=user,
            delivery_address_id=1,
            **FAR_COORDS,
            payment_method="demo_upi",
        )
        assert order.distance_km == Decimal("2.50")
        assert order.delivery_free is False
        assert order.delivery_charge == Decimal("40.00")
        assert order.grand_total == Decimal("512.50")

    def test_stock_untouched_and_cart_cleared(self, cart_with_item, user, product):
        place_order(cart=cart_with_item, user=user, delivery_address_id=1)
        product.refresh_from_db()
        assert product.stock_quantity == 50
        assert not CartItem.objects.filter(cart=cart_with_item).exists()
        cart_with_item.refresh_from_db()
        assert cart_with_item.is_active is False

    def test_order_items_snapshot_effective_price(self, cart_with_item, user):
        order = place_order(cart=cart_with_item, user=user, delivery_address_id=1)
        item = order.items.get()
        assert item.unit_price == Decimal("225.00")
        assert item.line_total == Decimal("450.00")
        assert item.quantity == 2

    def test_insufficient_stock_raises_and_rolls_back(self, cart_with_item, user, product):
        product.stock_quantity = 1
        product.save(update_fields=["stock_quantity"])
        with pytest.raises(ValueError, match="Insufficient stock"):
            place_order(cart=cart_with_item, user=user, delivery_address_id=1)
        assert Order.objects.count() == 0
        assert CartItem.objects.filter(cart=cart_with_item).exists()

    def test_empty_cart_rejected(self, cart, user):
        with pytest.raises(ValueError, match="empty"):
            place_order(cart=cart, user=user, delivery_address_id=1)


@pytest.mark.django_db
class TestPaymentConfirmation:
    def test_success_marks_order_paid_and_deducts_stock_once(
        self, cart_with_item, user, product
    ):
        order = place_order(cart=cart_with_item, user=user, delivery_address_id=1)
        p1 = mark_payment_successful(
            order, method="demo_upi", provider="demo", transaction_id="DEMO-AAA", is_demo=True
        )
        assert p1.status == "paid"
        assert p1.is_demo is True
        order.refresh_from_db()
        assert order.payment_status == "paid"
        assert order.status == "accepted"
        product.refresh_from_db()
        assert product.stock_quantity == 48
        assert (
            StockMovement.objects.filter(ref_order_id=order.id, reason="sale").count()
            == 1
        )

    def test_double_confirm_is_idempotent(self, cart_with_item, user, product):
        order = place_order(cart=cart_with_item, user=user, delivery_address_id=1)
        p1 = mark_payment_successful(
            order, method="demo_upi", provider="demo", transaction_id="DEMO-1", is_demo=True
        )
        p2 = mark_payment_successful(
            order, method="demo_upi", provider="demo", transaction_id="DEMO-2", is_demo=True
        )
        assert p1.id == p2.id
        assert Payment.objects.filter(order=order).count() == 1
        product.refresh_from_db()
        assert product.stock_quantity == 48
        assert (
            StockMovement.objects.filter(ref_order_id=order.id, reason="sale").count()
            == 1
        )

    def test_variant_sale_updates_product_stock(self, cart, product, variant, user):
        """Sales of a specific variant must still decrement the product-level
        stock that /admin/products and /shop display (variants mirror it)."""
        CartItem.objects.create(
            cart=cart,
            product=product,
            variant=variant,
            quantity=2,
            unit_price=Decimal("240.00"),
        )
        order = place_order(cart=cart, user=user, delivery_address_id=1)
        mark_payment_successful(
            order, method="demo_upi", provider="demo", transaction_id="DEMO-V", is_demo=True
        )
        product.refresh_from_db()
        variant.refresh_from_db()
        assert product.stock_quantity == 48
        assert variant.stock_quantity == 48

    def test_cashback_credited_once(self, cart_with_item, user):
        order = place_order(
            cart=cart_with_item, user=user, delivery_address_id=1, **NEAR_COORDS
        )
        mark_payment_successful(order, method="demo_upi", provider="demo", is_demo=True)
        order.refresh_from_db()
        assert order.cashback_credited_at is not None
        assert order.cashback_earned == Decimal("4.72")
        mark_payment_successful(
            order, method="demo_upi", provider="demo", transaction_id="DEMO-X", is_demo=True
        )
        order.refresh_from_db()
        assert order.cashback_credited_at is not None
        from apps.wallet.models import WalletLedger

        assert WalletLedger.objects.filter(ref_order=order, reason="purchase_cashback").count() == 1

    def test_failed_then_success_upgrades_same_payment(
        self, cart_with_item, user, product
    ):
        order = place_order(cart=cart_with_item, user=user, delivery_address_id=1)
        mark_payment_failed(
            order,
            method="demo_card",
            provider="demo",
            transaction_id="DEMO-F",
            is_demo=True,
            reason="Simulated failure",
        )
        order.refresh_from_db()
        assert order.payment_status == "failed"
        assert order.status == "pending"
        product.refresh_from_db()
        assert product.stock_quantity == 50

        p = mark_payment_successful(
            order, method="demo_upi", provider="demo", transaction_id="DEMO-S", is_demo=True
        )
        order.refresh_from_db()
        assert order.payment_status == "paid"
        assert p.status == "paid"
        assert Payment.objects.filter(order=order).count() == 1
        product.refresh_from_db()
        assert product.stock_quantity == 48
        assert (
            StockMovement.objects.filter(ref_order_id=order.id, reason="sale").count()
            == 1
        )

    def test_failed_after_success_is_ignored(self, cart_with_item, user):
        order = place_order(cart=cart_with_item, user=user, delivery_address_id=1)
        mark_payment_successful(order, method="demo_upi", provider="demo", is_demo=True)
        result = mark_payment_failed(order, method="demo_upi", provider="demo", is_demo=True)
        assert result is None
        order.refresh_from_db()
        assert order.payment_status == "paid"


@pytest.mark.django_db
class TestDemoPayment:
    def test_gateway_success_and_fail(self):
        gw = DemoPaymentGateway()
        res = gw.charge(None, method="demo_upi")
        assert res["success"] is True
        assert res["provider"] == "demo"
        assert res["transaction_id"].startswith("DEMO-")
        fail = gw.charge(None, method="demo_upi", simulate="fail")
        assert fail["success"] is False
        assert fail["provider"] == "demo"

    def test_process_demo_success(self, cart_with_item, user):
        order = place_order(cart=cart_with_item, user=user, delivery_address_id=1)
        data = process_demo_payment(order, method="demo_upi", simulate="success")
        assert data["success"] is True
        assert data["payment"].status == "paid"
        order.refresh_from_db()
        assert order.payment_status == "paid"

    def test_process_demo_fail_leaves_order_pending(self, cart_with_item, user, product):
        order = place_order(cart=cart_with_item, user=user, delivery_address_id=1)
        data = process_demo_payment(order, method="demo_card", simulate="fail")
        assert data["success"] is False
        order.refresh_from_db()
        assert order.payment_status == "failed"
        assert order.status == "pending"
        product.refresh_from_db()
        assert product.stock_quantity == 50


@pytest.mark.django_db
class TestDemoPaymentAPI:
    def test_confirm_success(self, customer_client, cart_with_item, user):
        order = place_order(cart=cart_with_item, user=user, delivery_address_id=1)
        res = customer_client.post(
            "/api/v1/payments/demo/confirm/",
            {"order_id": str(order.id), "method": "demo_upi"},
            format="json",
        )
        assert res.status_code == 200
        assert res.data["success"] is True
        assert res.data["payment"]["status"] == "paid"
        assert res.data["order"]["payment_status"] == "paid"

    def test_double_submit_is_idempotent(self, customer_client, cart_with_item, user):
        order = place_order(cart=cart_with_item, user=user, delivery_address_id=1)
        first = customer_client.post(
            "/api/v1/payments/demo/confirm/", {"order_id": str(order.id)}, format="json"
        )
        second = customer_client.post(
            "/api/v1/payments/demo/confirm/", {"order_id": str(order.id)}, format="json"
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.data["payment"]["id"] == second.data["payment"]["id"]

    def test_simulate_fail(self, customer_client, cart_with_item, user):
        order = place_order(cart=cart_with_item, user=user, delivery_address_id=1)
        res = customer_client.post(
            "/api/v1/payments/demo/confirm/",
            {"order_id": str(order.id), "simulate": "fail"},
            format="json",
        )
        assert res.status_code == 200
        assert res.data["success"] is False
        assert res.data["order"]["payment_status"] == "failed"

    def test_other_users_order_rejected(self, customer_client, cart_with_item, user, customer2):
        order = place_order(cart=cart_with_item, user=user, delivery_address_id=1)
        client2 = APIClient()
        client2.force_authenticate(user=customer2)
        res = client2.post(
            "/api/v1/payments/demo/confirm/",
            {"order_id": str(order.id)},
            format="json",
        )
        assert res.status_code == 404

    def test_status_endpoint(self, customer_client, cart_with_item, user):
        order = place_order(
            cart=cart_with_item, user=user, delivery_address_id=1, **FAR_COORDS
        )
        res = customer_client.get(f"/api/v1/payments/order/{order.id}/status/")
        assert res.status_code == 200
        assert res.data["payment_status"] == "pending"
        assert res.data["order_number"] == order.order_number
        assert res.data["order_status"] == "pending"
        # Delivery snapshot is echoed for the payment page.
        assert Decimal(res.data["distance_km"]) == Decimal("2.50")
        assert Decimal(res.data["delivery_charge"]) == Decimal("40.00")
        assert res.data["delivery_free"] is False
        # amount (grand_total) includes the ₹40 delivery charge.
        assert Decimal(res.data["amount"]) == Decimal("512.50")


@pytest.mark.django_db
class TestOrderListPaymentFields:
    def test_list_exposes_payment_fields(self, customer_client, cart_with_item, user):
        order = place_order(cart=cart_with_item, user=user, delivery_address_id=1)
        mark_payment_successful(order, method="demo_upi", provider="demo", is_demo=True)
        res = customer_client.get("/api/v1/orders/")
        item = res.data["results"][0]
        assert item["payment_status"] == "paid"
        assert item["payment_method"] == "demo_upi"
        assert "payment_status_display" in item


@pytest.mark.django_db
class TestAdminOrders:
    def test_all_orders_include_payment_fields(self, admin_client, cart_with_item, user):
        order = place_order(cart=cart_with_item, user=user, delivery_address_id=1)
        mark_payment_successful(order, method="demo_upi", provider="demo", is_demo=True)
        res = admin_client.get("/api/v1/admin-dashboard/all-orders/")
        assert res.status_code == 200
        row = next(r for r in res.data if r["id"] == str(order.id))
        assert row["payment_status"] == "paid"
        assert row["payment_method"] == "demo_upi"
        assert Decimal(row["grand_total"]) == order.grand_total

    def test_order_detail_endpoint(self, admin_client, cart_with_item, user):
        order = place_order(cart=cart_with_item, user=user, delivery_address_id=1)
        mark_payment_successful(
            order,
            method="demo_upi",
            provider="demo",
            transaction_id="DEMO-DET",
            is_demo=True,
        )
        res = admin_client.get(f"/api/v1/admin-dashboard/orders/{order.id}/")
        assert res.status_code == 200
        assert res.data["order_number"] == order.order_number
        assert res.data["payment"]["status"] == "paid"
        assert res.data["payment"]["transaction_id"] == "DEMO-DET"
        assert res.data["payment"]["is_demo"] is True
        assert len(res.data["items"]) == 1
        assert Decimal(res.data["totals"]["grand_total"]) == order.grand_total
