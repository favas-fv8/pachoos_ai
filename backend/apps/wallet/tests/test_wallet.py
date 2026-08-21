"""Tests for wallet app — cashback, manual redemption, voucher usage."""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.wallet.models import Voucher, WalletLedger
from apps.wallet.services import (
    adjust_debt,
    credit_cashback,
    get_debt_balance,
    get_total_cashback_redeemed,
    get_wallet_balance,
    redeem_cashback,
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

    def test_credit_cashback_never_auto_redeems(self, order, shop, user):
        """Reaching ₹10 via cashback credit must not deduct or mark redeemed."""
        order.grand_total = Decimal("1500.00")
        credit_cashback(order)
        assert get_wallet_balance(user, shop) == Decimal("15.00")
        assert get_total_cashback_redeemed(user, shop) == Decimal("0.00")
        assert not WalletLedger.objects.filter(
            user=user, reason__in=["cashback_redeemed", "voucher_mint"]
        ).exists()


@pytest.mark.django_db
class TestCashbackRedemption:
    def _credit(self, user, shop, amount):
        WalletLedger.objects.create(
            user=user,
            shop=shop,
            delta=amount,
            balance_after=amount,
            reason="purchase_cashback",
        )

    def test_below_minimum_rejected(self, user, shop):
        self._credit(user, shop, Decimal("9.99"))
        with pytest.raises(ValueError, match="at least"):
            redeem_cashback(user, shop)

    def test_full_redemption(self, user, shop):
        self._credit(user, shop, Decimal("25.50"))
        entry = redeem_cashback(user, shop)
        assert entry.delta == Decimal("-25.50")
        assert entry.reason == "cashback_redeemed"
        assert get_wallet_balance(user, shop) == Decimal("0.00")
        assert get_total_cashback_redeemed(user, shop) == Decimal("25.50")

    def test_custom_amount_redemption(self, user, shop):
        self._credit(user, shop, Decimal("40.00"))
        redeem_cashback(user, shop, amount=Decimal("12.00"))
        assert get_wallet_balance(user, shop) == Decimal("28.00")
        assert get_total_cashback_redeemed(user, shop) == Decimal("12.00")

    def test_custom_amount_below_minimum_rejected(self, user, shop):
        self._credit(user, shop, Decimal("40.00"))
        with pytest.raises(ValueError, match="Minimum redemption"):
            redeem_cashback(user, shop, amount=Decimal("5.00"))

    def test_custom_amount_above_balance_rejected(self, user, shop):
        self._credit(user, shop, Decimal("40.00"))
        with pytest.raises(ValueError, match="exceeds"):
            redeem_cashback(user, shop, amount=Decimal("50.00"))

    def test_cumulative_redeemed_includes_legacy_mints(self, user, shop):
        """Legacy voucher_mint rows count toward Cashback Redeemed."""
        self._credit(user, shop, Decimal("30.00"))
        WalletLedger.objects.create(
            user=user,
            shop=shop,
            delta=Decimal("-10.00"),
            balance_after=Decimal("20.00"),
            reason="voucher_mint",
            note="Minted voucher PCH-LEGACY",
        )
        redeem_cashback(user, shop, amount=Decimal("10.00"))
        assert get_total_cashback_redeemed(user, shop) == Decimal("20.00")


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
