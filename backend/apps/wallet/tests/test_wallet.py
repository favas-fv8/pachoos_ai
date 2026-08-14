"""Tests for wallet app — cashback, voucher minting, redemption."""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.wallet.models import Voucher, WalletLedger
from apps.wallet.services import (
    adjust_debt,
    credit_cashback,
    get_debt_balance,
    get_wallet_balance,
    mint_voucher,
    redeem_voucher,
)


@pytest.fixture
def product(db, shop):
    from apps.catalog.models import Category, Product, Subcategory

    cat = Category.objects.create(name="Bakery", slug="bakery")
    sub = Subcategory.objects.create(category=cat, name="Cakes", slug="cakes")
    return Product.objects.create(
        subcategory=sub,
        name="Test Cake",
        slug="test-cake",
        base_price=Decimal("200.00"),
        stock_quantity=50,
        is_available=True,
    )


@pytest.fixture
def order(db, user, shop, product):
    from apps.orders.models import Order, OrderItem

    o = Order.objects.create(
        shop=shop,
        user=user,
        order_number="PCH-20260804-0001",
        subtotal=Decimal("200.00"),
        grand_total=Decimal("225.00"),
        status="pending",
    )
    OrderItem.objects.create(
        order=o,
        product=product,
        product_name="Test Cake",
        quantity=1,
        unit_price=Decimal("200.00"),
        line_total=Decimal("200.00"),
    )
    return o


@pytest.mark.django_db
class TestCashback:
    def test_credit_cashback(self, order, shop):
        ledger = credit_cashback(order)
        assert ledger is not None
        # grand_total=225 / 100 = 2.25
        assert ledger.delta == Decimal("2.25")
        assert ledger.reason == "purchase_cashback"
        assert ledger.ref_order == order

    def test_cashback_updates_order(self, order, shop):
        credit_cashback(order)
        order.refresh_from_db()
        assert order.cashback_earned == Decimal("2.25")
        assert order.cashback_credited_at is not None

    def test_get_wallet_balance(self, order, shop, user):
        credit_cashback(order)
        balance = get_wallet_balance(user, shop)
        assert balance == Decimal("2.25")


@pytest.mark.django_db
class TestVoucherMinting:
    def test_insufficient_balance(self, user, shop):
        voucher = mint_voucher(user, shop)
        assert voucher is None

    def test_mint_voucher(self, user, shop):
        WalletLedger.objects.create(
            user=user,
            shop=shop,
            delta=Decimal("10.00"),
            balance_after=Decimal("10.00"),
            reason="purchase_cashback",
        )
        voucher = mint_voucher(user, shop)
        assert voucher is not None
        assert voucher.code.startswith("PCH-")
        assert voucher.amount == Decimal("10.00")
        assert voucher.status == "active"

    def test_mint_debits_balance(self, user, shop):
        WalletLedger.objects.create(
            user=user,
            shop=shop,
            delta=Decimal("15.00"),
            balance_after=Decimal("15.00"),
            reason="purchase_cashback",
        )
        mint_voucher(user, shop)
        balance = get_wallet_balance(user, shop)
        assert balance == Decimal("5.00")


@pytest.mark.django_db
class TestVoucherRedemption:
    def test_redeem_valid_voucher(self, user, shop, order):
        voucher = Voucher.objects.create(
            user=user,
            shop=shop,
            code="PCH-TESTCODE",
            amount=Decimal("10.00"),
            status="active",
            expires_at=timezone.now() + timezone.timedelta(days=30),
        )
        discount = redeem_voucher(user, "PCH-TESTCODE", order)
        assert discount == Decimal("10.00")
        voucher.refresh_from_db()
        assert voucher.status == "used"

    def test_redeem_expired_voucher(self, user, shop, order):
        Voucher.objects.create(
            user=user,
            shop=shop,
            code="PCH-EXPIRED",
            amount=Decimal("10.00"),
            status="active",
            expires_at=timezone.now() - timezone.timedelta(days=1),
        )
        with pytest.raises(ValueError, match="expired"):
            redeem_voucher(user, "PCH-EXPIRED", order)

    def test_redeem_invalid_code(self, user, shop, order):
        with pytest.raises(ValueError, match="Invalid"):
            redeem_voucher(user, "NONEXISTENT", order)


@pytest.mark.django_db
class TestDebtLedger:
    def test_adjust_debt(self, user, shop, admin_user):
        entry = adjust_debt(user, shop, Decimal("50.00"), "Credit given", admin_user)
        assert entry.delta == Decimal("50.00")
        assert entry.balance_after == Decimal("50.00")

    def test_get_debt_balance(self, user, shop, admin_user):
        adjust_debt(user, shop, Decimal("100.00"), "Credit", admin_user)
        adjust_debt(user, shop, Decimal("-30.00"), "Payment received", admin_user)
        balance = get_debt_balance(user, shop)
        assert balance == Decimal("70.00")
