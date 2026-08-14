"""Tests for catalog app — models, services, serializers."""
from decimal import Decimal

import pytest

from apps.catalog.models import Category, Product, Subcategory
from apps.catalog.serializers import (
    ProductDetailSerializer,
    ProductListSerializer,
)


@pytest.fixture
def category(db):
    return Category.objects.create(name="Bakery", slug="bakery")


@pytest.fixture
def subcategory(db, category):
    return Subcategory.objects.create(category=category, name="Cakes", slug="cakes")


@pytest.fixture
def product(db, subcategory):
    return Product.objects.create(
        subcategory=subcategory,
        name="Chocolate Cake",
        slug="chocolate-cake",
        description="Delicious chocolate cake",
        base_price=Decimal("250.00"),
        discount_percent=Decimal("10.00"),
        gst_percent=Decimal("5.00"),
        stock_quantity=50,
        is_available=True,
        avg_rating=Decimal("4.5"),
        times_sold=100,
    )


@pytest.mark.django_db
class TestCategory:
    def test_create_category(self, category):
        assert category.name == "Bakery"
        assert category.slug == "bakery"
        assert category.is_active is True

    def test_str(self, category):
        assert str(category) == "Bakery"


@pytest.mark.django_db
class TestProduct:
    def test_create_product(self, product):
        assert product.name == "Chocolate Cake"
        assert product.base_price == Decimal("250.00")
        assert product.stock_quantity == 50

    def test_effective_price(self, product):
        # 250 * (1 - 0.10) = 225
        assert product.effective_price == 225.0

    def test_str(self, product):
        assert str(product) == "Chocolate Cake"

    def test_zero_discount(self, db, subcategory):
        p = Product.objects.create(
            subcategory=subcategory,
            name="Plain Bread",
            slug="plain-bread",
            base_price=Decimal("50.00"),
            discount_percent=Decimal("0.00"),
            stock_quantity=100,
        )
        assert p.effective_price == 50.0


@pytest.mark.django_db
class TestProductRatingSerialization:
    """avg_rating must be a numeric JSON value so the frontend can call .toFixed()."""

    def test_list_serializer_avg_rating_is_number(self, product):
        data = ProductListSerializer(product).data
        assert data["avg_rating"] == Decimal("4.5")
        assert not isinstance(data["avg_rating"], str)

    def test_detail_serializer_avg_rating_is_number(self, product):
        data = ProductDetailSerializer(product).data
        assert data["avg_rating"] == Decimal("4.5")
        assert not isinstance(data["avg_rating"], str)

    def test_serializer_default_rating_when_no_reviews(self, db, subcategory):
        p = Product.objects.create(
            subcategory=subcategory,
            name="Unrated Cake",
            slug="unrated-cake",
        )
        data = ProductListSerializer(p).data
        assert data["avg_rating"] == Decimal("0.0")
        assert not isinstance(data["avg_rating"], str)
        assert data["rating_count"] == 0

    def test_api_product_list_returns_numeric_rating(self, client):
        sub = Subcategory.objects.create(
            category=Category.objects.create(name="Bakery", slug="bakery-2"),
            name="Cakes",
            slug="cakes-2",
        )
        Product.objects.create(
            subcategory=sub,
            name="Chocolate Cake 2",
            slug="chocolate-cake-2",
            avg_rating=Decimal("4.5"),
            rating_count=12,
        )
        res = client.get("/api/v1/catalog/products/")
        assert res.status_code == 200
        payload = res.json()
        product = payload["results"][0]
        assert product["avg_rating"] == 4.5
        assert isinstance(product["avg_rating"], float)
        assert not isinstance(product["avg_rating"], str)


@pytest.mark.django_db
class TestProductDetailLookup:
    """The storefront links products by slug (/product/<slug>/); the detail
    endpoint must resolve slugs (and keep resolving numeric pks)."""

    def test_detail_by_slug(self, client, product):
        res = client.get(f"/api/v1/catalog/products/{product.slug}/")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == product.id
        assert data["slug"] == product.slug
        assert data["pid"] == product.pid
        assert data["subcategory_name"] == "Cakes"
        assert data["category_name"] == "Bakery"
        assert data["stock_unit"] == "count"

    def test_detail_by_numeric_pk(self, client, product):
        res = client.get(f"/api/v1/catalog/products/{product.id}/")
        assert res.status_code == 200
        assert res.json()["id"] == product.id

    def test_detail_unknown_slug_is_404(self, client):
        res = client.get("/api/v1/catalog/products/does-not-exist/")
        assert res.status_code == 404

    def test_related_by_slug(self, client, product, subcategory):
        Product.objects.create(
            subcategory=subcategory,
            name="Vanilla Cake",
            slug="vanilla-cake",
            sku="VC-001",
            base_price=Decimal("200.00"),
            times_sold=50,
        )
        res = client.get(f"/api/v1/catalog/products/{product.slug}/related/")
        assert res.status_code == 200
        slugs = [p["slug"] for p in res.json()]
        assert "vanilla-cake" in slugs
        assert product.slug not in slugs
