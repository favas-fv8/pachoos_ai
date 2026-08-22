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
        status="delivered", payment_status="paid",
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

    def test_at_or_below_3_rule(self, db, user, shop):
        """Stock ≤ 3 is low regardless of per-product thresholds;
        above 3 is not."""
        from apps.admin_dashboard.services import LOW_STOCK_THRESHOLD

        cat = Category.objects.create(name="Fruits", slug="fruits-ls")
        sub = Subcategory.objects.create(category=cat, name="Apples", slug="apples-ls")
        Product.objects.create(
            subcategory=sub, name="Low Apples", slug="low-apples",
            base_price=Decimal("10.00"), stock_quantity=2,
            low_stock_threshold=1, is_available=True, sku="LS-LOW-001",
        )
        Product.objects.create(
            subcategory=sub, name="Edge Apples", slug="edge-apples",
            base_price=Decimal("10.00"), stock_quantity=3,
            low_stock_threshold=9, is_available=True, sku="LS-EDGE-001",
        )
        Product.objects.create(
            subcategory=sub, name="Ok Apples", slug="ok-apples",
            base_price=Decimal("10.00"), stock_quantity=4,
            low_stock_threshold=9, is_available=True, sku="LS-OK-001",
        )
        low = {p["name"] for p in get_low_stock_products()}
        assert LOW_STOCK_THRESHOLD == 3
        assert "Low Apples" in low
        assert "Edge Apples" in low
        assert "Ok Apples" not in low


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

    def test_shop_filter_applied_after_slice_regression(self, setup_data, shop):
        """Filtering a sliced queryset raises TypeError ('Cannot filter a
        query once a slice has been taken') — the bug behind 'Failed to load
        dashboard data' whenever request.shop was set."""
        orders = get_recent_orders(shop)
        assert len(orders) > 0
        assert all(o["order_number"] for o in orders)


@pytest.mark.django_db
class TestMonthlyReset:
    def test_monthly_counts_only_current_calendar_month(self, setup_data, shop, user):
        """Monthly Revenue / Monthly Orders cover only the current calendar
        month; last-month orders stay in history without inflating them."""
        from django.utils import timezone

        Order.objects.filter(order_number="PCH-DASH-001").update(
            payment_status="paid"
        )
        stats_now = get_dashboard_stats()
        assert stats_now["orders"]["monthly"] >= 1
        assert float(stats_now["revenue"]["monthly"]) >= 275.00

        # An order dated in the previous calendar month must not count.
        prev_month = (timezone.localtime().replace(day=1) - timezone.timedelta(days=1))
        Order.objects.filter(order_number="PCH-DASH-001").update(created_at=prev_month)
        stats_prev = get_dashboard_stats()
        assert stats_prev["orders"]["monthly"] == 0
        assert stats_prev["revenue"]["monthly"] == "0.00"
        # Historical data untouched.
        assert Order.objects.get(order_number="PCH-DASH-001").grand_total == Decimal("275.00")

    def test_monthly_counts_paid_orders_only(self, setup_data, shop, user):
        """Failed / pending payments never count toward monthly revenue or
        monthly orders — only successful (paid) ones."""
        from django.utils import timezone

        now = timezone.localtime()

        def _order(number, payment_status):
            o = Order.objects.create(
                shop=shop, user=user, order_number=number,
                subtotal=Decimal("100.00"), grand_total=Decimal("100.00"),
                status="accepted", payment_status=payment_status,
            )
            Order.objects.filter(pk=o.pk).update(created_at=now)
            return o

        _order("PCH-DASH-P01", "paid")
        _order("PCH-DASH-F01", "failed")
        _order("PCH-DASH-P02", "pending")

        stats = get_dashboard_stats()
        assert stats["orders"]["monthly"] >= 1
        # Only the single paid order's ₹100 counts — failed/pending excluded.
        paid_total = 100.00 + (
            275.00
            if Order.objects.filter(
                order_number="PCH-DASH-001", payment_status="paid"
            ).exists()
            else 0.0
        )
        assert float(stats["revenue"]["monthly"]) == paid_total


@pytest.mark.django_db
class TestRevenueChartMonth:
    def test_month_mode_current_calendar_month_paid_only(self, setup_data, shop, user):
        from apps.admin_dashboard.services import get_revenue_chart
        from django.utils import timezone

        Order.objects.filter(order_number="PCH-DASH-001").update(payment_status="paid")
        chart = get_revenue_chart(shop, month=True)
        assert len(chart) >= 1
        today = str(timezone.localdate())
        entry = next(d for d in chart if d["date"] == today)
        assert float(entry["revenue"]) >= 275.00


@pytest.mark.django_db
class TestCustomerList:
    def test_returns_customers(self, setup_data):
        customers = get_customer_list()
        assert len(customers) > 0

    def test_total_customers_matches_customer_list(self, setup_data, db):
        """Dashboard 'Total Customers' must agree with /admin/customers —
        soft-deleted (inactive) accounts are excluded from both."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.create_user(
            phone="+919876543299", email="gone@pachoos.com",
            password="x", full_name="Deleted Customer", role="customer",
            is_active=False,
        )
        assert get_dashboard_stats()["customers"]["total"] == len(get_customer_list())
