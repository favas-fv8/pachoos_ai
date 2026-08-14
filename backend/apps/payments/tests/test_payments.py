"""Tests for payments app — models."""
import pytest
from decimal import Decimal
from apps.payments.models import Payment, Refund, Invoice
from apps.orders.models import Order


@pytest.fixture
def order(db, user, shop):
    return Order.objects.create(
        shop=shop,
        user=user,
        order_number="PCH-20260804-TEST",
        subtotal=Decimal("200.00"),
        grand_total=Decimal("225.00"),
        status="accepted",
    )


@pytest.fixture
def payment(db, order, user):
    return Payment.objects.create(
        order=order,
        user=user,
        razorpay_order_id="order_test123",
        razorpay_payment_id="pay_test456",
        method="upi",
        amount=Decimal("225.00"),
        status="captured",
    )


@pytest.mark.django_db
class TestPayment:
    def test_create_payment(self, payment):
        assert payment.razorpay_order_id == "order_test123"
        assert payment.amount == Decimal("225.00")
        assert payment.status == "captured"

    def test_one_to_one_with_order(self, payment, order):
        assert order.payment == payment

    def test_str(self, payment):
        s = str(payment)
        assert "Payment" in s


@pytest.mark.django_db
class TestRefund:
    def test_create_refund(self, payment, admin_user):
        refund = Refund.objects.create(
            payment=payment,
            amount=Decimal("50.00"),
            status="processed",
            reason="Customer request",
            initiated_by=admin_user,
        )
        assert refund.amount == Decimal("50.00")
        assert refund.payment == payment

    def test_refund_status(self, payment, admin_user):
        refund = Refund.objects.create(
            payment=payment,
            amount=Decimal("25.00"),
            status="pending",
        )
        assert refund.status == "pending"


@pytest.mark.django_db
class TestInvoice:
    def test_create_invoice(self, order):
        invoice = Invoice.objects.create(
            order=order,
            invoice_number="INV-PCH-20260804-TEST",
            grand_total=Decimal("225.00"),
        )
        assert invoice.invoice_number.startswith("INV-")
        assert invoice.grand_total == Decimal("225.00")
