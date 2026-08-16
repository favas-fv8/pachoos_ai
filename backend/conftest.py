"""Shared test fixtures for PACHOOS backend."""
import pytest
from decimal import Decimal


def _get_user_model():
    from django.contrib.auth import get_user_model
    return get_user_model()


@pytest.fixture
def user(db):
    """Create a regular test user."""
    User = _get_user_model()
    return User.objects.create_user(
        phone="+919876543210",
        email="test@pachoos.com",
        password="testpass123",
        full_name="Test User",
        role="customer",
    )


@pytest.fixture
def admin_user(db):
    """Create an admin test user."""
    User = _get_user_model()
    return User.objects.create_user(
        phone="+919876543211",
        email="admin@pachoos.com",
        password="adminpass123",
        full_name="Admin User",
        role="super_admin",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def shop(db):
    """Create a test shop."""
    from apps.shops.models import Shop

    return Shop.objects.create(
        name="PACHOOS Test Shop",
        slug="pachoos-test",
        address_line1="123 Test Street",
        phone="+919876543210",
    )
