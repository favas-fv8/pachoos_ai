"""Tests for the shared admin catalog + cross-admin activity notifications.

Validates the single-source-of-truth dashboard: Admin 1 (super_admin) and
Admin 2 (store_manager) operate on the same data through the same `admin/*`
endpoints, and each admin is notified of the other's mutations.
"""
import io
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.accounts.models import AuditLog
from apps.admin_dashboard.models import AdminNotification
from apps.catalog.models import (
    Category,
    Product,
    ProductImage,
    StockMovement,
    Subcategory,
)

User = get_user_model()


@pytest.fixture
def store_manager(db):
    """Admin 2 — the store manager."""
    return User.objects.create_user(
        phone="+919876543212",
        email="manager@pachoos.com",
        password="managerpass123",
        full_name="Store Manager",
        role="store_manager",
        is_staff=True,
    )


@pytest.fixture
def api_admin1(admin_user):
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def api_admin2(store_manager):
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=store_manager)
    return client


@pytest.fixture
def api_customer(user):
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _make_png(name="pixel.png"):
    img = Image.new("RGB", (8, 8), color="green")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


@pytest.mark.django_db
class TestSharedCategoryManagement:
    def test_admin1_adds_category_admin2_sees_it(self, api_admin1, api_admin2):
        res = api_admin1.post(
            "/api/v1/catalog/admin/categories/", {"name": "Dairy", "description": "Milk & eggs"}
        )
        assert res.status_code == 201
        assert res.json()["is_active"] is True

        names = [c["name"] for c in api_admin2.get("/api/v1/catalog/admin/categories/").json()]
        assert "Dairy" in names

    def test_category_edit_and_delete(self, api_admin1, api_admin2):
        created = api_admin1.post(
            "/api/v1/catalog/admin/categories/", {"name": "Snacks"}
        ).json()

        res = api_admin1.patch(
            f"/api/v1/catalog/admin/categories/{created['id']}/",
            {"name": "Healthy Snacks"},
        )
        assert res.status_code == 200
        assert res.json()["name"] == "Healthy Snacks"

        deleted = api_admin1.post(
            "/api/v1/catalog/admin/categories/", {"name": "Temp"}
        ).json()
        res = api_admin1.delete(f"/api/v1/catalog/admin/categories/{deleted['id']}/")
        assert res.status_code == 204

    def test_category_delete_blocked_when_has_products(self, api_admin1, db):
        cat = Category.objects.create(name="Bakery X", slug="bakery-x")
        sub = Subcategory.objects.create(category=cat, name="Cakes", slug="cakes-x")
        Product.objects.create(subcategory=sub, name="Cake", base_price=Decimal("100"))

        res = api_admin1.delete(f"/api/v1/catalog/admin/categories/{cat.id}/")
        assert res.status_code == 409
        assert Category.objects.filter(id=cat.id).exists()

    def test_category_activate_deactivate(self, api_admin1, api_admin2):
        cat = api_admin1.post("/api/v1/catalog/admin/categories/", {"name": "Seasonal"}).json()
        res = api_admin1.patch(
            f"/api/v1/catalog/admin/categories/{cat['id']}/", {"is_active": False}
        )
        assert res.json()["is_active"] is False

        unread = api_admin2.get("/api/v1/admin-dashboard/notifications/").json()["unread_count"]
        actions = {n["action"] for n in api_admin2.get(
            "/api/v1/admin-dashboard/notifications/").json()["results"]}
        assert unread >= 3  # added + updated + deactivated
        assert "category_deactivated" in actions


@pytest.mark.django_db
class TestSharedProductManagement:
    def _make_category_and_sub(self, client, name):
        cat = client.post("/api/v1/catalog/admin/categories/", {"name": name}).json()
        sub = client.post(
            f"/api/v1/catalog/admin/categories/{cat['id']}/subcategories/",
            {"name": f"{name} sub"},
        ).json()
        return cat, sub

    def test_admin2_adds_product_admin1_sees_it(self, api_admin2, api_admin1):
        cat, sub = self._make_category_and_sub(api_admin2, "Beverages")
        res = api_admin2.post(
            "/api/v1/catalog/admin/products/",
            {
                "name": "Fresh Juice",
                "subcategory": sub["id"],
                "base_price": "120",
                "stock_quantity": 30,
                "is_available": True,
            },
        )
        assert res.status_code == 201
        pid = res.json()["pid"]
        assert pid.startswith("PCH-")

        products = api_admin1.get(
            f"/api/v1/catalog/admin/categories/{cat['id']}/products/"
        ).json()["results"]
        assert any(p["pid"] == pid for p in products)

    def test_product_edit_and_delete(self, api_admin2):
        cat, sub = self._make_category_and_sub(api_admin2, "Frozen")
        created = api_admin2.post(
            "/api/v1/catalog/admin/products/",
            {"name": "Ice Cream", "subcategory": sub["id"], "base_price": "99",
             "stock_quantity": 5, "is_available": True},
        ).json()

        res = api_admin2.patch(
            f"/api/v1/catalog/admin/products/{created['id']}/", {"name": "Mango Ice Cream"}
        )
        assert res.status_code == 200
        assert res.json()["name"] == "Mango Ice Cream"

        res = api_admin2.delete(f"/api/v1/catalog/admin/products/{created['id']}/")
        assert res.status_code == 204

    def test_stock_update_via_action_creates_ledger(self, api_admin1, admin_user):
        cat, sub = self._make_category_and_sub(api_admin1, "Stock Test")
        product = api_admin1.post(
            "/api/v1/catalog/admin/products/",
            {"name": "Bread", "subcategory": sub["id"], "base_price": "40",
             "stock_quantity": 10, "is_available": True},
        ).json()

        res = api_admin1.post(
            f"/api/v1/catalog/admin/products/{product['id']}/stock/",
            {"quantity": 40, "reason": "restock", "note": "Morning delivery"},
        )
        assert res.status_code == 200
        assert res.json()["stock_quantity"] == 40
        movement = StockMovement.objects.get(product_id=product["id"])
        assert movement.quantity == 30
        assert movement.reason == "restock"
        assert movement.created_by_id == admin_user.id

    def test_product_status_change(self, api_admin1, api_admin2):
        cat, sub = self._make_category_and_sub(api_admin1, "Toggle")
        product = api_admin1.post(
            "/api/v1/catalog/admin/products/",
            {"name": "Toggle Item", "subcategory": sub["id"], "base_price": "10",
             "stock_quantity": 3, "is_available": True},
        ).json()
        res = api_admin1.patch(
            f"/api/v1/catalog/admin/products/{product['id']}/", {"is_available": False}
        )
        assert res.json()["is_available"] is False
        actions = {n["action"] for n in api_admin2.get(
            "/api/v1/admin-dashboard/notifications/").json()["results"]}
        assert "product_deactivated" in actions

    def test_image_upload(self, api_admin1):
        cat, sub = self._make_category_and_sub(api_admin1, "Imaged")
        product = api_admin1.post(
            "/api/v1/catalog/admin/products/",
            {"name": "Photo Item", "subcategory": sub["id"], "base_price": "20",
             "stock_quantity": 5, "is_available": True},
        ).json()

        res = api_admin1.post(
            f"/api/v1/catalog/admin/products/{product['id']}/images/",
            {"image": _make_png(), "is_primary": "true"},
            format="multipart",
        )
        assert res.status_code == 201
        assert res.json()["image_url"].startswith("/media/products/")
        img = ProductImage.objects.get(product_id=product["id"])
        assert img.image.name.startswith("products/")
        assert img.is_primary is True

    def test_image_url_without_file(self, api_admin1):
        cat, sub = self._make_category_and_sub(api_admin1, "Linked")
        product = api_admin1.post(
            "/api/v1/catalog/admin/products/",
            {"name": "URL Item", "subcategory": sub["id"], "base_price": "30",
             "stock_quantity": 5, "is_available": True},
        ).json()
        res = api_admin1.post(
            f"/api/v1/catalog/admin/products/{product['id']}/images/",
            {"image_url": "https://example.com/p.png"},
        )
        assert res.status_code == 201
        assert res.json()["image_url"] == "https://example.com/p.png"


@pytest.mark.django_db
class TestCrossAdminNotifications:
    def test_notifications_only_other_admins_activity(self, api_admin1, api_admin2, admin_user, store_manager):
        api_admin1.post("/api/v1/catalog/admin/categories/", {"name": "Notify Me"})

        mine = api_admin1.get("/api/v1/admin-dashboard/notifications/").json()
        assert mine["unread_count"] == 0

        theirs = api_admin2.get("/api/v1/admin-dashboard/notifications/").json()
        assert theirs["unread_count"] == 1
        n = theirs["results"][0]
        assert n["action"] == "category_added"
        assert n["actor_name"] == admin_user.full_name
        assert n["is_read"] is False

        assert AdminNotification.objects.filter(recipient=store_manager).count() == 1
        assert AdminNotification.objects.filter(recipient=admin_user).count() == 0

    def test_mark_read(self, api_admin1, api_admin2):
        api_admin1.post("/api/v1/catalog/admin/categories/", {"name": "Read Me"})
        theirs = api_admin2.get("/api/v1/admin-dashboard/notifications/").json()
        nid = theirs["results"][0]["id"]

        res = api_admin2.post("/api/v1/admin-dashboard/notifications/read/", {"id": nid})
        assert res.status_code == 200
        assert res.json()["marked"] == 1

        after = api_admin2.get("/api/v1/admin-dashboard/notifications/").json()
        assert after["unread_count"] == 0
        assert after["results"][0]["is_read"] is True

    def test_audit_log_persists_activity(self, api_admin1, admin_user):
        api_admin1.post("/api/v1/catalog/admin/categories/", {"name": "Audited"})
        assert AuditLog.objects.filter(user=admin_user, action="category_added").exists()


@pytest.mark.django_db
class TestAdminSecurity:
    def test_customer_cannot_access_admin_catalog(self, api_customer):
        assert api_customer.get("/api/v1/catalog/admin/categories/").status_code == 403
        assert api_customer.get("/api/v1/catalog/admin/products/").status_code == 403
        assert api_customer.get("/api/v1/admin-dashboard/notifications/").status_code == 403

    def test_anonymous_cannot_access_admin_catalog(self):
        from rest_framework.test import APIClient

        anon = APIClient()
        assert anon.get("/api/v1/catalog/admin/categories/").status_code in (401, 403)
        assert anon.get("/api/v1/admin-dashboard/notifications/").status_code in (401, 403)

    def test_store_manager_has_same_access_as_super_admin(self, api_admin2):
        res = api_admin2.post("/api/v1/catalog/admin/categories/", {"name": "Manager Cat"})
        assert res.status_code == 201
