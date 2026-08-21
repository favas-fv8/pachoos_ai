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
    ProductTag,
    ProductVariant,
    Purchase,
    PurchaseItem,
    StockMovement,
    Subcategory,
    Tag,
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

    def test_category_delete_cascades_products_and_subcategories(self, api_admin1, db):
        """Products with no order/inventory history are removed with the
        category (same rule as the per-product delete flow)."""
        cat = Category.objects.create(name="Bakery X", slug="bakery-x")
        sub = Subcategory.objects.create(category=cat, name="Cakes", slug="cakes-x")
        product = Product.objects.create(
            subcategory=sub, name="Cake", base_price=Decimal("100")
        )

        res = api_admin1.delete(f"/api/v1/catalog/admin/categories/{cat.id}/")
        assert res.status_code == 204
        assert not Category.objects.filter(id=cat.id).exists()
        assert not Subcategory.objects.filter(id=sub.id).exists()
        assert not Product.objects.filter(id=product.id).exists()

    def test_category_delete_blocked_when_products_reference_history(
        self, api_admin1, db
    ):
        """Products referenced by orders/stock history are PROTECTed — the
        delete is refused up front and nothing is removed."""
        cat = Category.objects.create(name="Legacy Cat", slug="legacy-cat")
        sub = Subcategory.objects.create(category=cat, name="Old", slug="old-sub")
        product = Product.objects.create(
            subcategory=sub, name="Old Cake", base_price=Decimal("100")
        )
        StockMovement.objects.create(product=product, quantity=5, reason="adjustment")

        res = api_admin1.delete(f"/api/v1/catalog/admin/categories/{cat.id}/")
        assert res.status_code == 409
        assert "history" in res.json()["error"]
        assert Category.objects.filter(id=cat.id).exists()
        assert Subcategory.objects.filter(id=sub.id).exists()
        assert Product.objects.filter(id=product.id).exists()

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


@pytest.mark.django_db
class TestAdminProductExtendedFields:
    """The 7 customer-visible product fields must be admin-manageable.

    Covers: freshness, variants (size/weight), ingredients, brand, SKU, tags
    and nutritional info. Verifies create, edit, persistence and that the
    customer-facing detail endpoint reflects the saved values.
    """

    def _make_category_and_sub(self, api_admin1):
        cat = api_admin1.post(
            "/api/v1/catalog/admin/categories/", {"name": "Extended"}
        ).json()
        sub = api_admin1.post(
            f"/api/v1/catalog/admin/categories/{cat['id']}/subcategories/",
            {"name": "Extended sub"},
        ).json()
        return cat, sub

    def test_create_product_with_all_extended_fields(self, api_admin1, api_admin2):
        cat, sub = self._make_category_and_sub(api_admin1)
        payload = {
            "name": "Granola Bar",
            "subcategory": sub["id"],
            "base_price": "120",
            "stock_quantity": 10,
            "is_available": True,
            "freshness": "dry",
            "brand": "PACHOOS",
            "sku": "EXT-GRANOLA-001",
            "ingredients": "Oats, honey, nuts",
            "nutritional_info": {"calories": "200 kcal", "protein": "5g"},
            "tags": ["new", "healthy"],
            "variants": [
                {
                    "name": "200g",
                    "sku": "EXT-GRANOLA-200",
                    "price": "120",
                    "stock_quantity": 5,
                    "is_active": True,
                },
                {
                    "name": "500g",
                    "sku": "EXT-GRANOLA-500",
                    "price": "250",
                    "stock_quantity": 5,
                    "is_active": True,
                },
            ],
        }
        res = api_admin1.post("/api/v1/catalog/admin/products/", payload, format="json")
        assert res.status_code == 201, res.json()
        data = res.json()
        assert data["freshness"] == "dry"
        assert data["brand"] == "PACHOOS"
        assert data["sku"] == "EXT-GRANOLA-001"
        assert data["ingredients"] == "Oats, honey, nuts"
        assert data["nutritional_info"] == {"calories": "200 kcal", "protein": "5g"}
        tag_names = {t["name"] for t in data["tags"]}
        assert tag_names == {"new", "healthy"}
        assert len(data["variants"]) == 2

        product = Product.objects.get(pk=data["id"])
        assert product.ingredients == "Oats, honey, nuts"
        assert product.nutritional_info["protein"] == "5g"
        assert product.freshness == "dry"
        assert product.brand == "PACHOOS"
        assert product.sku == "EXT-GRANOLA-001"
        assert product.variants.count() == 2
        assert ProductTag.objects.filter(product=product).count() == 2

        # Customer-facing detail reflects the saved values.
        cust = api_admin2.get(
            f"/api/v1/catalog/products/{product.slug}/"
        )
        assert cust.status_code == 200
        cdata = cust.json()
        assert cdata["ingredients"] == "Oats, honey, nuts"
        assert cdata["nutritional_info"]["calories"] == "200 kcal"
        assert cdata["freshness"] == "dry"
        assert cdata["brand"] == "PACHOOS"
        assert cdata["sku"] == "EXT-GRANOLA-001"
        assert {t["name"] for t in cdata["tags"]} == {"new", "healthy"}
        assert len(cdata["variants"]) == 2

    def test_edit_product_updates_extended_fields(self, api_admin1):
        cat, sub = self._make_category_and_sub(api_admin1)
        created = api_admin1.post(
            "/api/v1/catalog/admin/products/",
            {
                "name": "Edit Me",
                "subcategory": sub["id"],
                "base_price": "50",
                "stock_quantity": 3,
                "is_available": True,
                "freshness": "fresh",
                "brand": "A",
                "tags": ["old"],
            },
            format="json",
        ).json()

        res = api_admin1.patch(
            f"/api/v1/catalog/admin/products/{created['id']}/",
            {
                "name": "Edited Product",
                "brand": "Brand B",
                "freshness": "frozen",
                "ingredients": "Milk, sugar",
                "sku": "EDIT-SKU-9",
                "nutritional_info": {"servings": 2},
                "tags": ["fresh", "seasonal"],
                "variants": [
                    {
                        "id": created["variants"][0]["id"] if created["variants"] else None,
                        "name": "500g",
                        "sku": "EDIT-V-500",
                        "price": "60",
                        "stock_quantity": 4,
                        "is_active": True,
                    }
                ],
            },
            format="json",
        )
        assert res.status_code == 200, res.json()
        data = res.json()
        assert data["brand"] == "Brand B"
        assert data["freshness"] == "frozen"
        assert data["ingredients"] == "Milk, sugar"
        assert data["sku"] == "EDIT-SKU-9"
        assert data["nutritional_info"] == {"servings": 2}
        assert {t["name"] for t in data["tags"]} == {"fresh", "seasonal"}
        assert len(data["variants"]) == 1

        product = Product.objects.get(pk=created["id"])
        assert product.brand == "Brand B"
        assert product.freshness == "frozen"
        assert product.ingredients == "Milk, sugar"
        assert {pt.tag.name for pt in product.product_tags.all()} == {"fresh", "seasonal"}
        assert product.variants.count() == 1
        assert product.variants.first().name == "500g"

    def test_extended_fields_persist_after_refresh(self, api_admin1):
        cat, sub = self._make_category_and_sub(api_admin1)
        created = api_admin1.post(
            "/api/v1/catalog/admin/products/",
            {
                "name": "Persist Me",
                "subcategory": sub["id"],
                "base_price": "80",
                "stock_quantity": 6,
                "is_available": True,
                "freshness": "bakery",
                "brand": "Persist Brand",
                "ingredients": "Flour, yeast",
                "tags": ["baked"],
            },
            format="json",
        ).json()

        refetched = api_admin1.get(
            f"/api/v1/catalog/admin/categories/{cat['id']}/products/"
        ).json()["results"]
        match = next(p for p in refetched if p["id"] == created["id"])
        assert match["freshness"] == "bakery"
        assert match["brand"] == "Persist Brand"
        assert match["ingredients"] == "Flour, yeast"
        assert [t["name"] for t in match["tags"]] == ["baked"]

        detail = api_admin1.get(
            f"/api/v1/catalog/admin/products/{created['id']}/"
        ).json()
        assert detail["freshness"] == "bakery"
        assert detail["brand"] == "Persist Brand"
        assert detail["ingredients"] == "Flour, yeast"
        assert [t["name"] for t in detail["tags"]] == ["baked"]

    def test_blank_sku_gets_unique_auto_value(self, api_admin1):
        cat, sub = self._make_category_and_sub(api_admin1)
        first = api_admin1.post(
            "/api/v1/catalog/admin/products/",
            {
                "name": "No Sku One",
                "subcategory": sub["id"],
                "base_price": "10",
                "stock_quantity": 1,
                "is_available": True,
            },
        ).json()
        second = api_admin1.post(
            "/api/v1/catalog/admin/products/",
            {
                "name": "No Sku Two",
                "subcategory": sub["id"],
                "base_price": "10",
                "stock_quantity": 1,
                "is_available": True,
            },
        ).json()
        assert first["sku"]
        assert second["sku"]
        assert first["sku"] != second["sku"]

    def test_duplicate_sku_is_rejected(self, api_admin1):
        cat, sub = self._make_category_and_sub(api_admin1)
        api_admin1.post(
            "/api/v1/catalog/admin/products/",
            {
                "name": "Has Sku",
                "subcategory": sub["id"],
                "base_price": "10",
                "stock_quantity": 1,
                "is_available": True,
                "sku": "DUP-SKU-1",
            },
        )
        res = api_admin1.post(
            "/api/v1/catalog/admin/products/",
            {
                "name": "Other",
                "subcategory": sub["id"],
                "base_price": "10",
                "stock_quantity": 1,
                "is_available": True,
                "sku": "DUP-SKU-1",
            },
        )
        assert res.status_code == 400

    def test_duplicate_variant_sku_is_rejected(self, api_admin1):
        cat, sub = self._make_category_and_sub(api_admin1)
        res = api_admin1.post(
            "/api/v1/catalog/admin/products/",
            {
                "name": "Variant Dup",
                "subcategory": sub["id"],
                "base_price": "10",
                "stock_quantity": 1,
                "is_available": True,
                "variants": [
                    {"name": "A", "sku": "V-DUP", "price": "5", "stock_quantity": 1},
                    {"name": "B", "sku": "V-DUP", "price": "5", "stock_quantity": 1},
                ],
            },
            format="json",
        )
        assert res.status_code == 400

    def test_invalid_nutritional_info_is_rejected(self, api_admin1):
        cat, sub = self._make_category_and_sub(api_admin1)
        res = api_admin1.post(
            "/api/v1/catalog/admin/products/",
            {
                "name": "Bad Nutrition",
                "subcategory": sub["id"],
                "base_price": "10",
                "stock_quantity": 1,
                "is_available": True,
                "nutritional_info": [1, 2, 3],
            },
            format="json",
        )
        assert res.status_code == 400

    def test_existing_product_without_new_values_still_works(self, api_admin1):
        cat, sub = self._make_category_and_sub(api_admin1)
        created = api_admin1.post(
            "/api/v1/catalog/admin/products/",
            {
                "name": "Minimal",
                "subcategory": sub["id"],
                "base_price": "20",
                "stock_quantity": 2,
                "is_available": True,
            },
        ).json()
        assert created["freshness"] == "fresh"
        assert created["ingredients"] == ""
        assert created["brand"] == ""
        assert created["nutritional_info"] is None
        assert created["tags"] == []
        assert created["variants"] == []

        res = api_admin1.patch(
            f"/api/v1/catalog/admin/products/{created['id']}/", {"name": "Minimal 2"}
        )
        assert res.status_code == 200
        assert res.json()["name"] == "Minimal 2"

    def test_create_works_when_legacy_blank_unique_row_exists(self, api_admin1, db):
        """Regression: a row stored with blank slug/sku (pre-fix bug) made
        every subsequent create fail with UNIQUE constraint → 500."""
        cat = Category.objects.create(name="Legacy Cat", slug="legacy-cat-2")
        sub = Subcategory.objects.create(category=cat, name="Legacy Sub", slug="legacy-sub-2")
        Product.objects.create(subcategory=sub, name="Audit Product", base_price=Decimal("10"))
        assert Product.objects.filter(slug="", sku="").exists()

        res = api_admin1.post(
            "/api/v1/catalog/admin/products/",
            {
                "name": "Fresh After Legacy",
                "subcategory": sub.id,
                "base_price": "10",
                "stock_quantity": 1,
                "is_available": True,
                "sku": "",
            },
            format="json",
        )
        assert res.status_code == 201, res.json()
        data = res.json()
        assert data["slug"] == "fresh-after-legacy"
        assert data["sku"] and data["sku"] != ""

    def test_update_with_blank_sku_does_not_500(self, api_admin1, db):
        """Regression: PATCHing a product with sku:"" used to write "" to the
        UNIQUE column (500 when any other blank row existed)."""
        cat = Category.objects.create(name="Upd Cat", slug="upd-cat")
        sub = Subcategory.objects.create(category=cat, name="Upd Sub", slug="upd-sub")
        legacy = Product.objects.create(subcategory=sub, name="Legacy Row", base_price=Decimal("10"))

        res = api_admin1.patch(
            f"/api/v1/catalog/admin/products/{legacy.id}/",
            {"sku": "", "base_price": "12"},
            format="json",
        )
        assert res.status_code == 200, res.json()
        legacy.refresh_from_db()
        assert legacy.sku != ""
        assert str(legacy.base_price) == "12.00"

    def test_variant_without_sku_gets_generated_one(self, api_admin1):
        cat, sub = self._make_category_and_sub(api_admin1)
        res = api_admin1.post(
            "/api/v1/catalog/admin/products/",
            {
                "name": "Blank Variant SKU",
                "subcategory": sub["id"],
                "base_price": "10",
                "stock_quantity": 1,
                "is_available": True,
                "variants": [
                    {"name": "A", "sku": "", "price": "5", "stock_quantity": 1},
                    {"name": "B", "sku": "", "price": "6", "stock_quantity": 1},
                ],
            },
            format="json",
        )
        assert res.status_code == 201, res.json()
        skus = [v["sku"] for v in res.json()["variants"]]
        assert all(skus)
        assert len(set(skus)) == 2

    def test_variant_price_and_stock_follow_product(self, api_admin1):
        """The admin-defined product price/stock is the single source of
        truth — variants share it so /shop matches /admin/products."""
        cat, sub = self._make_category_and_sub(api_admin1)
        res = api_admin1.post(
            "/api/v1/catalog/admin/products/",
            {
                "name": "Sync Cake",
                "subcategory": sub["id"],
                "base_price": "399",
                "discount_percent": "10",
                "stock_quantity": 20,
                "is_available": True,
                "variants": [
                    {"name": "1kg", "sku": "SYNC-1", "price": "749", "stock_quantity": 5},
                ],
            },
            format="json",
        )
        assert res.status_code == 201, res.json()
        variant = res.json()["variants"][0]
        assert float(variant["price"]) == 399.0
        assert float(variant["discount_percent"]) == 10.0
        assert variant["stock_quantity"] == 20

        # Updating the product price updates every variant with it.
        pid = res.json()["id"]
        res = api_admin1.patch(
            f"/api/v1/catalog/admin/products/{pid}/",
            {"base_price": "500", "discount_percent": "20", "stock_quantity": 30},
            format="json",
        )
        assert res.status_code == 200
        variant = res.json()["variants"][0]
        assert float(variant["price"]) == 500.0
        assert float(variant["discount_percent"]) == 20.0
        assert variant["stock_quantity"] == 30
        assert float(res.json()["selling_price"]) == 400.0


@pytest.mark.django_db
class TestPurchaseStockIntake:
    """Recording a purchase item automatically increases product stock."""

    def _admin_instance(self):
        from django.contrib.admin import AdminSite

        from apps.catalog.admin import PurchaseItemAdmin

        return PurchaseItemAdmin(PurchaseItem, AdminSite())

    def test_purchase_item_increases_product_stock(self, db, admin_user, shop):
        from django.test import RequestFactory

        cat = Category.objects.create(name="Intake Cat", slug="intake-cat")
        sub = Subcategory.objects.create(category=cat, name="Intake Sub", slug="intake-sub")
        product = Product.objects.create(
            subcategory=sub, name="Intake Product", base_price=Decimal("50"),
            stock_quantity=10,
        )
        purchase = Purchase.objects.create(shop=shop, supplier="Supplier X")
        item = PurchaseItem(
            purchase=purchase, product=product, quantity=5,
            unit_cost=Decimal("30"), total=Decimal("150"),
        )

        request = RequestFactory().post("/")
        request.user = admin_user
        self._admin_instance().save_model(request, item, None, False)

        product.refresh_from_db()
        assert product.stock_quantity == 15
        movement = StockMovement.objects.get(product=product, reason="purchase")
        assert movement.quantity == 5

    def test_purchase_item_delete_reverses_stock(self, db, admin_user, shop):
        from django.test import RequestFactory

        cat = Category.objects.create(name="Rev Cat", slug="rev-cat")
        sub = Subcategory.objects.create(category=cat, name="Rev Sub", slug="rev-sub")
        product = Product.objects.create(
            subcategory=sub, name="Rev Product", base_price=Decimal("50"),
            stock_quantity=10,
        )
        purchase = Purchase.objects.create(shop=shop)
        item = PurchaseItem(
            purchase=purchase, product=product, quantity=4,
            unit_cost=Decimal("30"), total=Decimal("120"),
        )
        request = RequestFactory().post("/")
        request.user = admin_user
        admin_instance = self._admin_instance()
        admin_instance.save_model(request, item, None, False)
        admin_instance.delete_model(request, item)

        product.refresh_from_db()
        assert product.stock_quantity == 10
