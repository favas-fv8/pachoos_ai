"""Tests for AI app — chat, recommendations, search."""
import pytest
from decimal import Decimal
from apps.ai.services import chat_assistant, get_recommendations, smart_search
from apps.catalog.models import Category, Subcategory, Product


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
