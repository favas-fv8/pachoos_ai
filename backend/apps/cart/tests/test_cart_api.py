"""Cart API regression tests.

Guards the full cart endpoint surface the storefront uses: lazy cart
creation, add/update/remove items, and server-side totals. This is the gap
that let a 500 crash in ``CartSerializer`` (redundant ``source`` on
``item_count``) reach production undetected.
"""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.cart.models import Cart, CartItem
from apps.catalog.models import Category, Product, Subcategory


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
def client(user, shop):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestCartApi:
    def test_list_empty_for_new_user(self, client):
        res = client.get("/api/v1/cart/carts/")
        assert res.status_code == 200
        assert res.data["count"] == 0
        assert res.data["results"] == []

    def test_create_cart_returns_201(self, client, user):
        """Regression: POST /cart/carts was 500ing because CartSerializer's
        `item_count` field declared source=item_count (same as field name),
        which DRF rejects with an AssertionError."""
        res = client.post("/api/v1/cart/carts/", data={}, format="json")
        assert res.status_code == 201, res.data
        assert res.data["id"]
        assert Cart.objects.filter(user=user, is_active=True).count() == 1

    def test_create_cart_is_idempotent_on_lazy_current(self, client, user):
        """current lazily creates the cart; a second call reuses it."""
        first = client.get("/api/v1/cart/carts/current/")
        assert first.status_code == 200
        second = client.get("/api/v1/cart/carts/current/")
        assert second.data["id"] == first.data["id"]
        assert Cart.objects.filter(user=user, is_active=True).count() == 1

    def test_add_item_then_list_reflects_cart(self, client, product):
        res = client.post("/api/v1/cart/carts/", data={}, format="json")
        cart_id = res.data["id"]
        add = client.post(
            f"/api/v1/cart/carts/{cart_id}/add_item/",
            data={"product_id": product.id, "quantity": 2},
            format="json",
        )
        assert add.status_code == 201, add.data
        assert add.data["quantity"] == 2
        assert add.data["product_data"]["id"] == product.id

        listed = client.get("/api/v1/cart/carts/")
        assert listed.status_code == 200
        assert listed.data["count"] == 1
        assert listed.data["results"][0]["item_count"] == 1

    def test_current_cart_summary_totals(self, client, product):
        current = client.get("/api/v1/cart/carts/current/")
        cart_id = current.data["id"]
        client.post(
            f"/api/v1/cart/carts/{cart_id}/add_item/",
            data={"product_id": product.id, "quantity": 2},
            format="json",
        )
        res = client.get(f"/api/v1/cart/carts/{cart_id}/summary/")
        assert res.status_code == 200, res.data
        assert Decimal(res.data["subtotal"]) == Decimal("450.00")
        assert Decimal(res.data["grand_total"]) == Decimal("472.50")

    def test_update_and_remove_item(self, client, product):
        current = client.get("/api/v1/cart/carts/current/")
        cart_id = current.data["id"]
        add = client.post(
            f"/api/v1/cart/carts/{cart_id}/add_item/",
            data={"product_id": product.id, "quantity": 2},
            format="json",
        )
        item_id = add.data["id"]
        upd = client.post(
            f"/api/v1/cart/carts/{cart_id}/update_item/",
            data={"item_id": item_id, "quantity": 3},
            format="json",
        )
        assert upd.status_code == 200, upd.data
        assert CartItem.objects.get(id=item_id).quantity == 3

        rem = client.post(
            f"/api/v1/cart/carts/{cart_id}/remove_item/",
            data={"item_id": item_id},
            format="json",
        )
        assert rem.status_code == 200, rem.data
        assert CartItem.objects.filter(id=item_id).count() == 0

    def test_cannot_add_unavailable_product(self, client, product):
        product.is_available = False
        product.save(update_fields=["is_available"])
        current = client.get("/api/v1/cart/carts/current/")
        cart_id = current.data["id"]
        add = client.post(
            f"/api/v1/cart/carts/{cart_id}/add_item/",
            data={"product_id": product.id, "quantity": 1},
            format="json",
        )
        assert add.status_code == 404

    def test_requires_authentication(self):
        anon = APIClient()
        res = anon.get("/api/v1/cart/carts/")
        assert res.status_code == 401
