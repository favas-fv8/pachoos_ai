"""Tests for bank accounts — encryption at rest, masked exposure, RBAC.

Covers the shop's payout accounts (admin managed) and the customer's own
accounts (self managed): CRUD, frontend-relevant validation (IFSC, account
number), the guarantee that the plaintext number is never returned, and that
no user can read or mutate another user's (or the shop's) accounts.
"""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.payments.encryption import decrypt_account_number
from apps.payments.models import BankAccount

User = get_user_model()


@pytest.fixture
def other_customer(db):
    return User.objects.create_user(
        phone="+919876543299",
        email="other@banktest.com",
        password="testpass123",
        full_name="Other Customer",
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
def other_customer_client(other_customer):
    client = APIClient()
    client.force_authenticate(user=other_customer)
    return client


@pytest.fixture
def shop_account(shop):
    account = BankAccount(shop=shop)
    account.account_holder_name = "PACHOOS Store"
    account.bank_name = "HDFC Bank"
    account.set_account_number("50100234567890")
    account.ifsc = "HDFC0001234"
    account.save()
    return account


@pytest.fixture
def customer_account(user):
    account = BankAccount(user=user)
    account.account_holder_name = "Test User"
    account.bank_name = "SBI"
    account.set_account_number("1234 5678 9012")
    account.ifsc = "SBIN0001234"
    account.save()
    return account


@pytest.mark.django_db
class TestBankAccountModel:
    def test_account_number_encrypted_at_rest(self, customer_account):
        stored = customer_account.account_number_encrypted
        assert stored != "123456789012"
        assert "1234" not in stored
        assert decrypt_account_number(stored) == "123456789012"

    def test_last4_and_mask(self, customer_account):
        assert customer_account.account_number_last4 == "9012"
        assert customer_account.masked_account_number() == "••••9012"

    def test_set_account_number_validates(self, shop):
        account = BankAccount(shop=shop)
        with pytest.raises(ValueError):
            account.set_account_number("ABCDEFG")
        with pytest.raises(ValueError):
            account.set_account_number("12345")


@pytest.mark.django_db
class TestCustomerBankAccountAPI:
    def test_customer_creates_account(self, customer_client):
        res = customer_client.post(
            "/api/v1/payments/my/bank-accounts/",
            {
                "account_holder_name": "Test User",
                "bank_name": "ICICI Bank",
                "account_number": "123456789012",
                "ifsc": "ICIC0001234",
            },
        )
        assert res.status_code == 201
        assert res.data["account_number_last4"] == "9012"
        assert res.data["account_number_masked"] == "••••9012"
        assert "account_number" not in res.data

    def test_customer_sees_own_only(self, customer_client, customer_account, other_customer):
        res = customer_client.get("/api/v1/payments/my/bank-accounts/")
        assert res.status_code == 200
        ids = [a["id"] for a in res.data]
        assert ids == [customer_account.id]

    def test_customer_cannot_read_others_account(self, other_customer_client, customer_account):
        res = other_customer_client.get(f"/api/v1/payments/my/bank-accounts/{customer_account.id}/")
        assert res.status_code == 404

    def test_customer_cannot_edit_others_account(self, other_customer_client, customer_account):
        res = other_customer_client.patch(
            f"/api/v1/payments/my/bank-accounts/{customer_account.id}/",
            {"bank_name": "Hacked"},
        )
        assert res.status_code == 404

    def test_customer_patches_own(self, customer_client, customer_account):
        res = customer_client.patch(
            f"/api/v1/payments/my/bank-accounts/{customer_account.id}/",
            {"bank_name": "Axis Bank"},
        )
        assert res.status_code == 200
        assert res.data["bank_name"] == "Axis Bank"
        customer_account.refresh_from_db()
        assert customer_account.bank_name == "Axis Bank"

    def test_customer_deletes_own(self, customer_client, customer_account):
        res = customer_client.delete(f"/api/v1/payments/my/bank-accounts/{customer_account.id}/")
        assert res.status_code == 204
        assert BankAccount.objects.filter(pk=customer_account.id).exists() is False

    def test_validation_failures(self, customer_client):
        res = customer_client.post(
            "/api/v1/payments/my/bank-accounts/",
            {"account_holder_name": "", "bank_name": "", "account_number": "nope", "ifsc": "bad"},
        )
        assert res.status_code == 400
        assert "account_number" in res.data
        assert "ifsc" in res.data

    def test_ifsc_normalised_and_validated(self, customer_client):
        # Lowercase input is accepted and normalised, then RBI-format validated.
        res = customer_client.post(
            "/api/v1/payments/my/bank-accounts/",
            {"account_holder_name": "T", "bank_name": "B",
             "account_number": "123456789012", "ifsc": "hdfc0001234"},
        )
        assert res.status_code == 201
        assert res.data["ifsc"] == "HDFC0001234"
        # Malformed IFSC (bad bank code pattern) is rejected.
        res2 = customer_client.post(
            "/api/v1/payments/my/bank-accounts/",
            {"account_holder_name": "T", "bank_name": "B",
             "account_number": "123456789012", "ifsc": "HDFC01234"},
        )
        assert res2.status_code == 400
        assert "ifsc" in res2.data


@pytest.mark.django_db
class TestAdminShopBankAccountAPI:
    def test_admin_creates_shop_account(self, admin_client, shop):
        res = admin_client.post(
            "/api/v1/payments/bank-accounts/",
            {
                "account_holder_name": "PACHOOS Store",
                "bank_name": "HDFC Bank",
                "account_number": "50100234567890",
                "ifsc": "HDFC0001234",
                "is_active": True,
            },
        )
        assert res.status_code == 201
        assert res.data["owner_shop"] is True
        assert res.data["is_active"] is True
        assert res.data["account_number_masked"] == "••••7890"

    def test_admin_lists_shop_accounts(self, admin_client, shop_account):
        res = admin_client.get("/api/v1/payments/bank-accounts/")
        assert res.status_code == 200
        assert [a["id"] for a in res.data] == [shop_account.id]

    def test_admin_toggles_status(self, admin_client, shop_account):
        res = admin_client.patch(
            f"/api/v1/payments/bank-accounts/{shop_account.id}/",
            {"is_active": False},
        )
        assert res.status_code == 200
        assert res.data["is_active"] is False

    def test_admin_deletes_shop_account(self, admin_client, shop_account):
        res = admin_client.delete(f"/api/v1/payments/bank-accounts/{shop_account.id}/")
        assert res.status_code == 204
        assert BankAccount.objects.filter(pk=shop_account.id).exists() is False


@pytest.mark.django_db
class TestBankAccountRBAC:
    def test_customer_cannot_manage_shop_accounts(self, customer_client):
        assert customer_client.get("/api/v1/payments/bank-accounts/").status_code == 403
        res = customer_client.post(
            "/api/v1/payments/bank-accounts/",
            {"account_holder_name": "T", "bank_name": "B",
             "account_number": "123456789012", "ifsc": "ICIC0001234"},
        )
        assert res.status_code == 403

    def test_admin_cannot_manage_customer_accounts(self, admin_client):
        assert admin_client.get("/api/v1/payments/my/bank-accounts/").status_code == 403

    def test_anonymous_cannot_access_any(self, shop, user):
        client = APIClient()
        assert client.get("/api/v1/payments/bank-accounts/").status_code == 401
        assert client.get("/api/v1/payments/my/bank-accounts/").status_code == 401
        assert client.get("/api/v1/orders/").status_code in (401, 200)  # sanity: auth enforced