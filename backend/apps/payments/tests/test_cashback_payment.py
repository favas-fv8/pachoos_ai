"""Tests for cashback-at-payment flow.

Covers:
  * ``redeem_cashback_for_order`` — wallet deduction only on success, once.
  * FAILED payments leave the wallet untouched.
  * ``CashfreeOrderView`` server-side validation of ``use_cashback`` and the
    net (grand_total − cashback) amount sent to Cashfree.
"""
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.orders.services import mark_payment_failed, mark_payment_successful
from apps.payments.models import Payment
from apps.wallet.models import WalletLedger
from apps.wallet.services import (
    get_total_cashback_redeemed,
    get_wallet_balance,
    redeem_cashback_for_order,
)


@pytest.fixture
def order(db, user, shop):
    from apps.orders.models import Order

    return Order.objects.create(
        shop=shop,
        user=user,
        order_number="PCH-20260822-0001",
        subtotal=Decimal("200.00"),
        grand_total=Decimal("225.00"),
        status="pending",
        cashback_used=Decimal("25.00"),
    )


def _credit(user, shop, amount):
    WalletLedger.objects.create(
        user=user,
        shop=shop,
        delta=amount,
        balance_after=amount,
        reason="purchase_cashback",
    )


@pytest.mark.django_db
class TestRedeemCashbackForOrder:
    def test_deducts_balance_and_records_history(self, order, shop, user):
        _credit(user, shop, Decimal("100.00"))
        entry = redeem_cashback_for_order(order)

        assert entry.delta == Decimal("-25.00")
        assert entry.reason == "cashback_redeemed"
        assert entry.ref_order == order
        assert get_wallet_balance(user, shop) == Decimal("75.00")
        assert get_total_cashback_redeemed(user, shop) == Decimal("25.00")

    def test_idempotent(self, order, shop, user):
        _credit(user, shop, Decimal("100.00"))
        first = redeem_cashback_for_order(order)
        assert redeem_cashback_for_order(order) is None
        assert (
            WalletLedger.objects.filter(
                user=user, reason="cashback_redeemed"
            ).count()
            == 1
        )
        assert get_wallet_balance(user, shop) == Decimal("75.00")
        assert first is not None

    def test_noop_without_applied_cashback(self, order, shop, user):
        order.cashback_used = Decimal("0.00")
        _credit(user, shop, Decimal("50.00"))
        assert redeem_cashback_for_order(order) is None
        assert get_wallet_balance(user, shop) == Decimal("50.00")

    def test_clamps_to_available_balance(self, order, shop, user):
        # Ledger says 100 but balance_after bookkeeping aside, the SUM is the
        # source of truth — credit only 10 so the clamp path is exercised.
        WalletLedger.objects.create(
            user=user,
            shop=shop,
            delta=Decimal("10.00"),
            balance_after=Decimal("10.00"),
            reason="purchase_cashback",
        )
        entry = redeem_cashback_for_order(order)
        assert entry.delta == Decimal("-10.00")


@pytest.mark.django_db
class TestWalletOnlyOnSuccess:
    def test_successful_payment_deducts_once(self, order, shop, user):
        _credit(user, shop, Decimal("100.00"))

        payment = mark_payment_successful(
            order, method="upi", provider="cashfree", transaction_id="TX1"
        )

        order.refresh_from_db()
        # Charged net of applied cashback.
        assert payment.amount == Decimal("200.00")
        # Balance = 100 − 25 used + 2.25 earned (1% of grand_total).
        assert get_wallet_balance(user, shop) == Decimal("77.25")
        assert get_total_cashback_redeemed(user, shop) == Decimal("25.00")
        assert order.cashback_used_at is not None
        # Idempotent retry never double-deducts.
        mark_payment_successful(
            order, method="upi", provider="cashfree", transaction_id="TX1"
        )
        assert get_wallet_balance(user, shop) == Decimal("77.25")
        assert get_total_cashback_redeemed(user, shop) == Decimal("25.00")

    def test_failed_payment_leaves_wallet_untouched(self, order, shop, user):
        _credit(user, shop, Decimal("100.00"))

        payment = mark_payment_failed(
            order, method="upi", provider="cashfree", reason="USER_DROPPED"
        )

        order.refresh_from_db()
        assert payment.status == "failed"
        assert get_wallet_balance(user, shop) == Decimal("100.00")
        assert get_total_cashback_redeemed(user, shop) == Decimal("0.00")
        assert not WalletLedger.objects.filter(reason="cashback_redeemed").exists()
        assert order.cashback_used_at is None


@pytest.mark.django_db
class TestCashfreeOrderViewCashback:
    @pytest.fixture
    def client(self, user):
        c = APIClient()
        c.force_authenticate(user=user)
        return c

    def _post(self, client, order, **extra):
        return client.post(
            "/api/v1/payments/cashfree/order/",
            {"order_id": str(order.id), **extra},
            format="json",
        )

    def test_minimum_amount_enforced(self, client, order, shop, user):
        _credit(user, shop, Decimal("100.00"))
        res = self._post(client, order, use_cashback="5")
        assert res.status_code == 400

    def test_exceeding_balance_rejected(self, client, order, user, shop):
        _credit(user, shop, Decimal("20.00"))
        res = self._post(client, order, use_cashback="50")
        assert res.status_code == 400

    def test_exceeding_payable_rejected(self, client, order, user, shop):
        _credit(user, shop, Decimal("500.00"))
        res = self._post(client, order, use_cashback="230")
        assert res.status_code == 400

    def test_valid_cashback_creates_net_order(self, client, order, user, shop):
        _credit(user, shop, Decimal("100.00"))

        with patch(
            "apps.payments.views.initiate_cashfree_payment",
            return_value={
                "cf_order_id": "cf_123",
                "order_id": f"{order.id}-abc12345",
                "payment_session_id": "session_123",
                "order_status": "ACTIVE",
            },
        ) as mock_init:
            res = self._post(client, order, use_cashback="25")

        assert res.status_code == 200
        assert res.data["cashback_used"] == "25.00"
        order.refresh_from_db()
        assert order.cashback_used == Decimal("25.00")
        # Gateway received the NET amount, computed server-side.
        sent_order = mock_init.call_args.args[0]
        assert sent_order.payable_amount == Decimal("200.00")
        payment = Payment.objects.get(order=order)
        assert payment.amount == Decimal("200.00")

    def test_no_cashback_keeps_original_amount(self, client, order, user, shop):
        with patch(
            "apps.payments.views.initiate_cashfree_payment",
            return_value={
                "cf_order_id": "cf_123",
                "order_id": f"{order.id}-abc12345",
                "payment_session_id": "session_123",
                "order_status": "ACTIVE",
            },
        ):
            res = self._post(client, order)

        assert res.status_code == 200
        assert res.data["cashback_used"] == "0.00"
        order.refresh_from_db()
        assert order.cashback_used == Decimal("0.00")
