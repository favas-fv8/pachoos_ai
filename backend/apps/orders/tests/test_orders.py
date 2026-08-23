"""Tests for orders app — models, services (delivery, tax, coupon)."""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.orders.models import Order
from apps.orders.services import (
    calculate_delivery,
    calculate_tax,
    resolve_delivery_distance,
)

# The conftest ``shop`` fixture sits at this location. 1° of latitude is
# 6371·π/180 ≈ 111.195 km, so offsetting the customer's latitude by
# km / KM_PER_DEG_LAT yields (almost exactly) a north-south `km` distance.
SHOP_LAT, SHOP_LNG = 12.9716, 77.5946
KM_PER_DEG_LAT = 111.19492664455874


def _north_of_shop(distance_km: float) -> tuple[float, float]:
    return SHOP_LAT + distance_km / KM_PER_DEG_LAT, SHOP_LNG


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


@pytest.fixture
def order(db, shop, user):
    return Order.objects.create(
        shop=shop,
        user=user,
        order_number="PCH-20260804-TEST",
        subtotal=Decimal("200.00"),
        grand_total=Decimal("225.00"),
        status="accepted",
    )


@pytest.mark.django_db
class TestDeliveryCalculation:
    def test_free_delivery_within_radius(self):
        result = calculate_delivery(1.5)
        assert result["delivery_charge"] == 0.0
        assert result["delivery_free"] is True
        assert result["distance_km"] == 1.5

    def test_free_delivery_at_exact_radius(self):
        """Exactly 2 km is still free (<= comparison)."""
        result = calculate_delivery(2.0)
        assert result["delivery_charge"] == 0.0
        assert result["delivery_free"] is True

    def test_paid_delivery_beyond_radius(self):
        result = calculate_delivery(3.0)
        assert result["delivery_charge"] == 40.0
        assert result["delivery_free"] is False

    def test_undetermined_distance_charges_standard_fee(self):
        """Missing coordinates never grant free delivery."""
        result = calculate_delivery(None)
        assert result["delivery_charge"] == 40.0
        assert result["delivery_free"] is False
        assert result["distance_km"] is None


@pytest.mark.django_db
class TestDeliveryDistanceResolution:
    """Server-side haversine between the customer and the shop row."""

    def test_known_offset_distance(self, shop):
        lat, lon = _north_of_shop(1.5)
        distance = resolve_delivery_distance(lat, lon, shop)
        assert distance is not None
        assert abs(distance - 1.5) < 0.01

    def test_exact_two_km_resolves_free(self, shop):
        lat, lon = _north_of_shop(2.0)
        distance = resolve_delivery_distance(lat, lon, shop)
        assert distance == 2.0
        assert calculate_delivery(distance)["delivery_free"] is True

    def test_beyond_two_km_is_paid(self, shop):
        lat, lon = _north_of_shop(2.5)
        distance = resolve_delivery_distance(lat, lon, shop)
        assert distance == 2.5
        assert calculate_delivery(distance)["delivery_charge"] == 40.0

    def test_missing_customer_coords_return_none(self, shop):
        assert resolve_delivery_distance(None, None, shop) is None
        assert resolve_delivery_distance("not-a-number", SHOP_LNG, shop) is None
        assert resolve_delivery_distance(999.0, SHOP_LNG, shop) is None  # out of range

    def test_missing_shop_coords_return_none(self, db, shop, user):
        from apps.shops.models import Shop

        bare = Shop.objects.create(name="No Geo", slug="no-geo")
        assert bare.lat is None
        assert resolve_delivery_distance(SHOP_LAT, SHOP_LNG, bare) is None


@pytest.mark.django_db
class TestTaxCalculation:
    def test_default_gst(self):
        assert calculate_tax(100.0) == 5.0

    def test_custom_gst(self):
        assert calculate_tax(100.0, gst_percent=12.0) == 12.0

    def test_zero_subtotal(self):
        assert calculate_tax(0.0) == 0.0

    def test_rounding(self):
        result = calculate_tax(33.33)
        assert result == round(33.33 * 0.05, 2)


@pytest.mark.django_db
class TestOrderListAPIContract:
    """The frontend account Payments/Orders pages consume GET /api/v1/orders/.

    OrderViewSet inherits DRF's global StandardPagination, so the JSON must be
    the paginated envelope ({count, next, previous, results}), which the
    frontend normalises to an array. These tests lock the contract in place —
    they must NOT silently yield a bare array or a shape mismatch.
    """

    @pytest.fixture
    def customer_client(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    @pytest.fixture
    def admin_client(self, admin_user):
        client = APIClient()
        client.force_authenticate(user=admin_user)
        return client

    def test_returns_paginated_envelope(self, customer_client, order):
        res = customer_client.get("/api/v1/orders/")
        assert res.status_code == 200
        assert isinstance(res.data, dict)
        assert set(res.data.keys()) == {
            "count", "page", "num_pages", "next", "previous", "results"
        }
        assert res.data["count"] == 1
        assert isinstance(res.data["results"], list)
        assert res.data["results"][0]["order_number"] == "PCH-20260804-TEST"

    def test_zero_records(self, customer_client):
        res = customer_client.get("/api/v1/orders/")
        assert res.status_code == 200
        assert res.data["count"] == 0
        assert res.data["results"] == []

    def test_multiple_records(self, customer_client, shop, user):
        for i in range(3):
            Order.objects.create(
                shop=shop, user=user,
                order_number=f"PCH-MULTI-{i}",
                grand_total=Decimal("100.00"),
                status="pending",
            )
        res = customer_client.get("/api/v1/orders/")
        assert res.status_code == 200
        assert res.data["count"] == 3
        assert len(res.data["results"]) == 3

    def test_pagination_with_page_size(self, customer_client, shop, user):
        for i in range(5):
            Order.objects.create(
                shop=shop, user=user,
                order_number=f"PCH-PAGE-{i}",
                grand_total=Decimal("100.00"),
                status="pending",
            )
        res = customer_client.get("/api/v1/orders/?page_size=2")
        assert res.status_code == 200
        assert res.data["count"] == 5
        assert res.data["num_pages"] == 3
        assert len(res.data["results"]) == 2
        assert res.data["next"] is not None

    def test_customer_only_sees_own_orders(self, customer_client, order, shop, customer2):
        other = Order.objects.create(
            shop=shop, user=customer2,
            order_number="PCH-OTHER-1",
            grand_total=Decimal("50.00"),
            status="pending",
        )
        res = customer_client.get("/api/v1/orders/")
        nums = [r["order_number"] for r in res.data["results"]]
        assert nums == [order.order_number]
        assert other.order_number not in nums

    def test_admin_sees_all_orders(self, admin_client, order, shop, customer2):
        Order.objects.create(
            shop=shop, user=customer2,
            order_number="PCH-OTHER-2",
            grand_total=Decimal("75.00"),
            status="pending",
        )
        res = admin_client.get("/api/v1/orders/")
        assert res.status_code == 200
        assert res.data["count"] == 2

    def test_anonymous_rejected(self, order):
        res = APIClient().get("/api/v1/orders/")
        assert res.status_code in (401, 403)

    def test_list_fields_match_frontend_types(self, customer_client, order):
        res = customer_client.get("/api/v1/orders/")
        item = res.data["results"][0]
        for field in ("id", "order_number", "status", "status_display", "grand_total", "created_at", "items_count"):
            assert field in item
