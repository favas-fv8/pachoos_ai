"""Tests for admin customer management — safe profile edits and soft delete.

Soft-deleting a customer must never harm financial records: orders, wallet
ledger and the Debt Book (including a previously linked offline book) all stay
intact. Editing is limited to profile fields (name/phone/email/active).
Also verifies the customer detail payload carries the *complete linked Debt
Book* so admin and customer views always agree.
"""
import pytest
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.orders.models import Order
from apps.wallet.models import WalletLedger
from apps.wallet.services import (
    add_debt_bill,
    get_or_create_debt_book,
    link_offline_debt_book,
)

User = get_user_model()


@pytest.fixture
def customer2(db):
    return User.objects.create_user(
        phone="+919876543244",
        email="customer2@admin.com",
        password="testpass123",
        full_name="Second Customer",
        role="customer",
    )


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def customer_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def customer_with_financials(db, user, shop, admin_user):
    """Customer owning an order, cashback, an offline-linked Debt Book."""
    order = Order.objects.create(
        shop=shop, user=user, order_number="PCH-CUST-DEL-001",
        subtotal=Decimal("500.00"), grand_total=Decimal("545.00"), status="delivered",
    )
    WalletLedger.objects.create(user=user, shop=shop, delta=Decimal("5.00"),
                                balance_after=Decimal("5.00"),
                                reason="purchase_cashback", ref_order=order)
    offline_book = get_or_create_debt_book(
        shop, name="Offline Debtor", phone="+919000001111"
    )
    add_debt_bill(offline_book, admin_user=admin_user,
                  product_name="Ghee", unit_price=300, note="Linked credit")
    link_offline_debt_book(offline_book, user, admin_user)
    return order, offline_book


@pytest.mark.django_db
class TestCustomerEditService:
    def test_updates_profile_fields(self, user, admin_user):
        from apps.admin_dashboard.services import update_customer

        updated = update_customer(user.id, admin_user, full_name="New Name")
        assert updated.full_name == "New Name"
        update_customer(user.id, admin_user, phone="9876500001")
        user.refresh_from_db()
        assert user.phone == "9876500001"

    def test_phone_and_email_validated(self, user, admin_user):
        from apps.admin_dashboard.services import update_customer
        from apps.wallet.services import validate_phone

        normalized = validate_phone("+91 98711 23456")
        update_customer(user.id, admin_user, phone="+91 98711 23456")
        user.refresh_from_db()
        assert user.phone == normalized

        with pytest.raises(ValueError):
            update_customer(user.id, admin_user, phone="123")

    def test_duplicate_phone_and_email_rejected(self, user, customer2, admin_user):
        from apps.admin_dashboard.services import update_customer

        with pytest.raises(ValueError):
            update_customer(user.id, admin_user, phone=customer2.phone)
        with pytest.raises(ValueError):
            update_customer(user.id, admin_user, email=customer2.email)

    def test_staff_cannot_be_edited(self, admin_user):
        from apps.admin_dashboard.services import update_customer

        with pytest.raises(ValueError):
            update_customer(admin_user.id, admin_user, full_name="Hacked")


@pytest.mark.django_db
class TestCustomerDeleteService:
    def test_soft_delete_preserves_financial_history(self, user, shop, admin_user,
                                                     customer_with_financials):
        from apps.admin_dashboard.services import deactivate_customer

        deactivate_customer(user.id, admin_user)
        user.refresh_from_db()
        assert user.is_active is False
        # Orders, cashback ledger and Debt Book (with its linked ledger) intact.
        assert Order.objects.filter(user=user).count() == 1
        assert WalletLedger.objects.filter(user=user).count() == 1
        book = user.debt_book.first()
        assert book is not None
        assert book.entries.count() == 1
        assert book.entries.first().amount_paid == Decimal("0.00")

    def test_soft_delete_hides_from_customer_list(self, user, admin_user, shop):
        from apps.admin_dashboard.services import deactivate_customer, get_customer_list

        deactivate_customer(user.id, admin_user)
        net = [c["id"] for c in get_customer_list() if c["phone"] == user.phone]
        assert user.id not in net

    def test_soft_delete_writes_audit(self, user, admin_user):
        from apps.accounts.models import AuditLog
        from apps.admin_dashboard.services import deactivate_customer

        deactivate_customer(user.id, admin_user)
        log = AuditLog.objects.filter(action="customer.deleted", entity_type="customer",
                                      entity_id=str(user.id)).last()
        assert log is not None
        assert log.after == {"is_active": False}


@pytest.mark.django_db
class TestCustomerAPI:
    def test_patch_updates_customer(self, admin_client, user):
        res = admin_client.patch(
            f"/api/v1/admin-dashboard/customers/{user.id}/",
            {"full_name": "Edited Name", "phone": "9876500002"},
        )
        assert res.status_code == 200
        assert res.data["full_name"] == "Edited Name"
        assert res.data["phone"] == "9876500002"

    def test_patch_rejects_uneditable_fields(self, admin_client, user):
        res = admin_client.patch(
            f"/api/v1/admin-dashboard/customers/{user.id}/",
            {"role": "super_admin", "is_superuser": True},
        )
        assert res.status_code == 400

    def test_patch_duplicate_phone_conflict(self, admin_client, user, customer2):
        res = admin_client.patch(
            f"/api/v1/admin-dashboard/customers/{user.id}/",
            {"phone": customer2.phone},
        )
        assert res.status_code == 400

    def test_delete_soft_deactivates(self, admin_client, user):
        res = admin_client.delete(f"/api/v1/admin-dashboard/customers/{user.id}/")
        assert res.status_code == 204
        user.refresh_from_db()
        assert user.is_active is False

    def test_customer_cannot_admin_other(self, customer_client, user):
        assert customer_client.get("/api/v1/admin-dashboard/customers/").status_code == 403
        assert customer_client.patch(
            f"/api/v1/admin-dashboard/customers/{user.id}/", {"full_name": "Hack"}
        ).status_code == 403

    def test_detail_includes_full_linked_debt_book(self, admin_client, user,
                                                   customer_with_financials,
                                                   admin_user):
        res = admin_client.get(f"/api/v1/admin-dashboard/customers/{user.id}/")
        assert res.status_code == 200
        book = res.data["debt_book"]
        assert book is not None
        assert book["summary"]["outstanding"] == "300.00"
        assert len(book["entries"]) == 1
        assert book["entries"][0]["product_name"] == "Ghee"
        assert book["notes"] == []
        assert res.data["total_debt"] == "300.00"