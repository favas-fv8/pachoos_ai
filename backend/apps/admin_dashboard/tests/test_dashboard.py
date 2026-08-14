"""Tests for admin dashboard app — services."""
from decimal import Decimal

import pytest

from apps.admin_dashboard.services import (
    get_customer_list,
    get_dashboard_stats,
    get_low_stock_products,
    get_recent_orders,
    get_top_products,
)
from apps.catalog.models import Category, Product, Subcategory
from apps.orders.models import Order


@pytest.fixture
def setup_data(db, user, shop):
    from apps.orders.models import OrderItem

    cat = Category.objects.create(name="Bakery", slug="bakery")
    sub = Subcategory.objects.create(category=cat, name="Cakes", slug="cakes")
    p1 = Product.objects.create(
        subcategory=sub, name="Chocolate Cake", slug="choc-cake",
        base_price=Decimal("250.00"), stock_quantity=50, is_available=True, times_sold=100,
        sku="DASH-CHOC-001",
    )
    p2 = Product.objects.create(
        subcategory=sub, name="Vanilla Cake", slug="van-cake",
        base_price=Decimal("200.00"), stock_quantity=2, low_stock_threshold=5, is_available=True, times_sold=50,
        sku="DASH-VAN-001",
    )
    o = Order.objects.create(
        shop=shop, user=user, order_number="PCH-DASH-001",
        subtotal=Decimal("250.00"), grand_total=Decimal("275.00"),
        status="delivered",
    )
    OrderItem.objects.create(
        order=o, product=p1, product_name="Chocolate Cake",
        quantity=2, unit_price=Decimal("250.00"), line_total=Decimal("500.00"),
    )
    OrderItem.objects.create(
        order=o, product=p2, product_name="Vanilla Cake",
        quantity=1, unit_price=Decimal("200.00"), line_total=Decimal("200.00"),
    )
    return {"p1": p1, "p2": p2, "order": o}


@pytest.mark.django_db
class TestDashboardStats:
    def test_returns_stats(self, setup_data):
        stats = get_dashboard_stats()
        assert "revenue" in stats
        assert "orders" in stats
        assert "customers" in stats
        assert "products" in stats

    def test_revenue_counted(self, setup_data):
        stats = get_dashboard_stats()
        assert float(stats["revenue"]["total"]) > 0


@pytest.mark.django_db
class TestTopProducts:
    def test_returns_products(self, setup_data):
        top = get_top_products(limit=5)
        assert len(top) > 0

    def test_sorted_by_sales(self, setup_data):
        top = get_top_products(limit=5)
        assert top[0]["total_sold"] >= top[-1]["total_sold"]


@pytest.mark.django_db
class TestLowStock:
    def test_finds_low_stock(self, setup_data):
        low = get_low_stock_products()
        names = [p["name"] for p in low]
        assert "Vanilla Cake" in names


@pytest.mark.django_db
class TestRecentOrders:
    def test_returns_orders(self, setup_data):
        orders = get_recent_orders()
        assert len(orders) > 0

    def test_order_has_fields(self, setup_data):
        orders = get_recent_orders()
        o = orders[0]
        assert "order_number" in o
        assert "user_name" in o
        assert "grand_total" in o


@pytest.mark.django_db
class TestCustomerList:
    def test_returns_customers(self, setup_data):
        customers = get_customer_list()
        assert len(customers) > 0
