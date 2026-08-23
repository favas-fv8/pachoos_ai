"""Payment views — Razorpay order creation, webhooks, refunds, invoices."""
import hashlib
import hmac
import logging

from django.conf import settings
from django.http import HttpRequest
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdmin, IsCustomer
from apps.orders.models import Order
from apps.orders.serializers import OrderSerializer
from apps.orders.services import record_payment
from apps.payments.models import BankAccount, Invoice, Payment, Refund
from apps.payments.serializers import (
    BankAccountAdminWriteSerializer,
    BankAccountSerializer,
    BankAccountWriteSerializer,
    InvoiceSerializer,
    PaymentSerializer,
    RefundRequestSerializer,
    RefundSerializer,
)
from apps.payments.services import process_demo_payment
from apps.payments.gateway import normalize_payment_method
from apps.payments.services.cashfree import (
    confirm_cashfree_payment,
    handle_cashfree_webhook,
    initiate_cashfree_payment,
)

logger = logging.getLogger("apps.payments")


def _resolve_shop(request):
    """Shop for staff-scoped operations (wallet-style middleware resolution)."""
    shop = getattr(request, "shop", None)
    if not shop:
        from apps.shops.models import Shop

        shop = Shop.objects.first()
    return shop


class DemoPaymentView(APIView):
    """Demo Payment — simulate a successful or failed payment for an order.

    POST ``{order_id, method, simulate}`` where ``simulate`` is
    ``"success"`` (default) or ``"fail"``.

    This is a **simulation only** — no real money moves. It creates/updates the
    Payment record, confirms the order, deducts stock and credits cashback via
    the idempotent confirmers in ``apps.orders.services``.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: HttpRequest) -> Response:
        order_id = request.data.get("order_id")
        method = request.data.get("method", "demo_upi")
        simulate = request.data.get("simulate", "success")

        if simulate not in ("success", "fail"):
            return Response(
                {"error": {"message": "simulate must be 'success' or 'fail'."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except (Order.DoesNotExist, ValueError, TypeError):
            return Response(
                {"error": {"message": "Order not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            data = process_demo_payment(order, method=method, simulate=simulate)
        except ValueError as e:
            return Response(
                {"error": {"message": str(e)}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "success": data["success"],
                "message": data["message"],
                "transaction_id": data["transaction_id"],
                "payment": PaymentSerializer(data["payment"]).data
                if data["payment"]
                else None,
                "order": OrderSerializer(data["order"]).data,
            }
        )


class OrderPaymentStatusView(APIView):
    """GET the payment/order status for an order (survives page refresh).

    Replaces the previously broken ``/orders/{id}/payment/`` polling contract —
    this endpoint reads the persisted Payment + Order records directly.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: HttpRequest, order_id) -> Response:
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except (Order.DoesNotExist, ValueError, TypeError):
            return Response(
                {"error": {"message": "Order not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment = Payment.objects.filter(order=order).first()
        return Response(
            {
                "order_id": str(order.id),
                "order_number": order.order_number,
                "order_status": order.status,
                "payment_status": order.payment_status,
                "payment_method": normalize_payment_method(
                    order.payment_method or (payment.method if payment else "")
                ),
                "amount": str(order.grand_total),
                "cashback_used": str(order.cashback_used),
                "transaction_id": payment.transaction_id if payment else "",
                # Delivery snapshot captured at order placement (server-computed
                # haversine). distance_km is None when coordinates were missing.
                "distance_km": (
                    str(order.distance_km) if order.distance_km is not None else None
                ),
                "delivery_charge": str(order.delivery_charge),
                "delivery_free": order.delivery_free,
                "created_at": order.created_at.isoformat(),
            }
        )


class RazorpayOrderView(APIView):
    """Create a Razorpay order for a given order_id."""

    permission_classes = [IsAuthenticated]

    def post(self, request: HttpRequest) -> Response:
        order_id = request.data.get("order_id")
        if not order_id:
            return Response(
                {"error": {"message": "order_id is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response(
                {"error": {"message": "Order not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        if hasattr(order, "payment") and order.payment.status == "captured":
            return Response(
                {"error": {"message": "Order already paid."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount_paise = int(order.grand_total * 100)

        # Dev mode: return a mock Razorpay order
        if settings.DEBUG:
            import random
            mock_order_id = f"order_{random.randint(100000, 999999)}"
            return Response(
                {
                    "id": mock_order_id,
                    "amount": amount_paise,
                    "currency": "INR",
                    "status": "created",
                }
            )

        # Production: create actual Razorpay order
        import razorpay

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        try:
            razorpay_order = client.order.create(
                {
                    "amount": amount_paise,
                    "currency": "INR",
                    "receipt": str(order.id),
                    "notes": {"order_id": order.order_number},
                }
            )
            return Response(razorpay_order)
        except Exception as e:
            return Response(
                {"error": {"message": f"Failed to create Razorpay order: {str(e)}"}},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class RazorpayWebhookView(APIView):
    """Handle Razorpay webhook events (payment.captured, payment.failed)."""

    permission_classes = []

    def post(self, request: HttpRequest) -> Response:
        payload = request.data
        event = payload.get("event", "")

        if settings.DEBUG:
            # Dev mode: skip signature verification
            pass
        else:
            # Verify webhook signature
            signature = request.headers.get("X-Razorpay-Signature", "")
            expected = hmac.new(
                settings.RAZORPAY_WEBHOOK_SECRET.encode(),
                request.body,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                return Response(
                    {"error": {"message": "Invalid webhook signature"}},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

        payment_data = payload.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = payment_data.get("order_id", "")

        if event == "payment.captured":
            try:
                order = Order.objects.get(id=int(payload.get("notes", {}).get("order_id", 0)))
                record_payment(
                    order,
                    {
                        "razorpay_order_id": payment_data.get("order_id", ""),
                        "razorpay_payment_id": payment_data.get("id", ""),
                        "razorpay_signature": signature if not settings.DEBUG else "mock_signature",
                        "method": payment_data.get("method", "upi"),
                        "status": "authorized",
                    },
                )
            except Order.DoesNotExist:
                pass

        elif event == "payment.failed":
            try:
                payment = Payment.objects.get(razorpay_order_id=order_id)
                payment.status = "failed"
                payment.save(update_fields=["status"])
            except Payment.DoesNotExist:
                pass

        return Response({"status": "ok"})


class RefundView(APIView):
    """Process a refund for a payment (admin only)."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request: HttpRequest) -> Response:
        serializer = RefundRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            payment = Payment.objects.get(razorpay_payment_id=data["payment_id"])
        except Payment.DoesNotExist:
            return Response(
                {"error": {"message": "Payment not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        refund = Refund.objects.create(
            payment=payment,
            amount=data["amount"],
            reason=data.get("reason", ""),
            initiated_by=request.user,
            status="processed",
        )

        # Dev mode: skip actual Razorpay refund
        if not settings.DEBUG:
            import razorpay

            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            try:
                rp_refund = client.payment.refund(
                    payment.razorpay_payment_id,
                    {"amount": int(data["amount"] * 100)},
                )
                refund.razorpay_refund_id = rp_refund.get("id", "")
                refund.save(update_fields=["razorpay_refund_id"])
            except Exception:
                refund.status = "failed"
                refund.save(update_fields=["status"])

        return Response(RefundSerializer(refund).data, status=status.HTTP_201_CREATED)


class InvoiceView(APIView):
    """Get or generate a GST invoice for an order."""

    permission_classes = [IsAuthenticated]

    def get(self, request: HttpRequest, order_id: int) -> Response:
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response(
                {"error": {"message": "Order not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Non-staff users can only view their own invoices
        if not request.user.is_staff and order.user_id != request.user.id:
            return Response(
                {"error": {"message": "Not authorized."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        invoice, created = Invoice.objects.get_or_create(
            order=order,
            defaults={
                "invoice_number": f"INV-{order.order_number}",
                "gstin_shop": getattr(settings, "SHOP_GSTIN", ""),
                "base_amount": order.subtotal,
                "tax_total": order.tax_total,
                "grand_total": order.grand_total,
            },
        )

        return Response(InvoiceSerializer(invoice).data)


# ═════════════════════════════════════════════════════════════════════════════
# Bank accounts — Admin shop payout accounts + Customer self-managed accounts.
# Only the masked account number is ever exposed; the plaintext is encrypted
# at rest and online-banking credentials are never stored.
# ═════════════════════════════════════════════════════════════════════════════


class AdminBankAccountListCreateView(APIView):
    """Admin: list / add the *shop's* bank accounts (used for payouts)."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        shop = _resolve_shop(request)
        accounts = BankAccount.objects.filter(shop=shop)
        return Response(BankAccountSerializer(accounts, many=True).data)

    def post(self, request):
        serializer = BankAccountAdminWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        account = BankAccount(shop=_resolve_shop(request), is_active=data.get("is_active", True))
        account.account_holder_name = data["account_holder_name"]
        account.bank_name = data["bank_name"]
        account.set_account_number(data["account_number"])
        account.ifsc = data["ifsc"]
        account.save()
        return Response(
            BankAccountSerializer(account).data, status=status.HTTP_201_CREATED
        )


class AdminBankAccountDetailView(APIView):
    """Admin: view / edit / delete one of the shop's bank accounts."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def _get(self, request, pk):
        shop = _resolve_shop(request)
        try:
            return BankAccount.objects.get(pk=pk, shop=shop)
        except (BankAccount.DoesNotExist, ValueError, TypeError):
            return None

    def get(self, request, pk):
        account = self._get(request, pk)
        if account is None:
            return Response({"error": {"message": "Bank account not found."}}, status=404)
        return Response(BankAccountSerializer(account).data)

    def patch(self, request, pk):
        account = self._get(request, pk)
        if account is None:
            return Response({"error": {"message": "Bank account not found."}}, status=404)
        serializer = BankAccountAdminWriteSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        if "account_holder_name" in data:
            account.account_holder_name = data["account_holder_name"]
        if "bank_name" in data:
            account.bank_name = data["bank_name"]
        if "account_number" in data:
            account.set_account_number(data["account_number"])
        if "ifsc" in data:
            account.ifsc = data["ifsc"]
        if "is_active" in data:
            account.is_active = data["is_active"]
        account.save()
        return Response(BankAccountSerializer(account).data)

    def delete(self, request, pk):
        account = self._get(request, pk)
        if account is None:
            return Response({"error": {"message": "Bank account not found."}}, status=404)
        account.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomerBankAccountListCreateView(APIView):
    """Customer: list / add their own bank accounts (settling debt etc.)."""

    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        accounts = BankAccount.objects.filter(user=request.user)
        return Response(BankAccountSerializer(accounts, many=True).data)

    def post(self, request):
        serializer = BankAccountWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        account = BankAccount(user=request.user)
        account.account_holder_name = data["account_holder_name"]
        account.bank_name = data["bank_name"]
        account.set_account_number(data["account_number"])
        account.ifsc = data["ifsc"]
        account.save()
        return Response(
            BankAccountSerializer(account).data, status=status.HTTP_201_CREATED
        )


class CustomerBankAccountDetailView(APIView):
    """Customer: edit / delete their own bank account only (403/404 for others)."""

    permission_classes = [IsAuthenticated, IsCustomer]

    def _get(self, request, pk):
        try:
            return BankAccount.objects.get(pk=pk, user=request.user)
        except (BankAccount.DoesNotExist, ValueError, TypeError):
            return None

    def get(self, request, pk):
        account = self._get(request, pk)
        if account is None:
            return Response({"error": {"message": "Bank account not found."}}, status=404)
        return Response(BankAccountSerializer(account).data)

    def patch(self, request, pk):
        account = self._get(request, pk)
        if account is None:
            return Response({"error": {"message": "Bank account not found."}}, status=404)
        serializer = BankAccountWriteSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        if "account_holder_name" in data:
            account.account_holder_name = data["account_holder_name"]
        if "bank_name" in data:
            account.bank_name = data["bank_name"]
        if "account_number" in data:
            account.set_account_number(data["account_number"])
        if "ifsc" in data:
            account.ifsc = data["ifsc"]
        account.save()
        return Response(BankAccountSerializer(account).data)

    def delete(self, request, pk):
        account = self._get(request, pk)
        if account is None:
            return Response({"error": {"message": "Bank account not found."}}, status=404)
        account.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ═════════════════════════════════════════════════════════════════════════════
# Cashfree PG v2 — Sandbox / Production checkout
# ═════════════════════════════════════════════════════════════════════════════


class CashfreeOrderView(APIView):
    """Create a Cashfree payment order and return the payment session ID.

    POST ``{ order_id, customer_email?, customer_phone?, use_cashback? }``

    ``use_cashback`` (optional, decimal): cashback the customer wants to put
    toward this order. Validated server-side — must be ≥ ₹10 (or the full
    balance when that is smaller), never more than the wallet balance or the
    order total. The Cashfree order is created for
    ``grand_total − applied cashback``. Wallet deduction happens only after
    the payment succeeds (see ``apps.orders.services``).

    Returns ``{ cf_order_id, payment_session_id, order_status }`` for the
    frontend to initialize the Cashfree checkout SDK.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: HttpRequest) -> Response:
        from decimal import Decimal, InvalidOperation

        from apps.wallet.services import MIN_CASHBACK_REDEEM, get_wallet_balance

        order_id = request.data.get("order_id")
        if not order_id:
            return Response(
                {"error": {"message": "order_id is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except (Order.DoesNotExist, ValueError, TypeError):
            return Response(
                {"error": {"message": "Order not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        if order.payment_status == "paid":
            return Response(
                {"error": {"message": "Order is already paid."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Resolve + validate the requested cashback server-side ────────
        raw_cashback = request.data.get("use_cashback")
        applied = Decimal("0.00")
        if raw_cashback not in (None, "", False):
            try:
                requested = Decimal(str(raw_cashback)).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError, TypeError):
                return Response(
                    {"error": {"message": "Invalid cashback amount."}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if requested <= 0:
                requested = Decimal("0.00")

            if requested > 0:
                if requested < MIN_CASHBACK_REDEEM:
                    return Response(
                        {
                            "error": {
                                "message": f"Minimum cashback amount is ₹{MIN_CASHBACK_REDEEM:.0f}."
                            }
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                balance = get_wallet_balance(request.user, _resolve_shop(request))
                payable = Decimal(str(order.grand_total)).quantize(Decimal("0.01"))
                if requested > balance:
                    return Response(
                        {"error": {"message": "Amount exceeds your available cashback balance."}},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                # Keep at least ₹1 for the gateway charge.
                if requested > payable - Decimal("1"):
                    return Response(
                        {"error": {"message": "Amount exceeds the order payable amount."}},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                applied = requested

        # Persist the resolved amount — also *resets* a stale value when
        # the customer retries without cashback.
        if Decimal(str(order.cashback_used)) != applied:
            order.cashback_used = applied
            order.save(update_fields=["cashback_used", "updated_at"])

        # Check if there's already a pending Cashfree order
        existing_payment = Payment.objects.filter(
            order=order, provider="cashfree", status__in=["created", "authorized"]
        ).first()
        if (
            existing_payment
            and existing_payment.razorpay_order_id
            and Decimal(str(order.cashback_used)) == applied
        ):
            # Reuse existing Cashfree order if still valid *and* created with
            # the same cashback amount (otherwise fall through so the fresh
            # session carries the correct net amount).
            from apps.payments.gateway import CashfreeGateway

            gw = CashfreeGateway()
            # Use the stored merchant order ID for verification
            merchant_order_id = str(order.id)
            if existing_payment.raw_response:
                merchant_order_id = existing_payment.raw_response.get(
                    "cashfree_merchant_order_id", str(order.id)
                )
            verification = gw.verify_payment(merchant_order_id)
            if verification.get("success") and verification.get("order_status") not in (
                "EXPIRED",
                "TERMINATED",
            ):
                return Response(
                    {
                        "cf_order_id": existing_payment.razorpay_order_id,
                        "payment_session_id": existing_payment.razorpay_payment_id,
                        "order_status": verification.get("order_status", ""),
                        "cashback_used": str(order.cashback_used),
                    }
                )

        customer_email = request.data.get("customer_email", "")
        customer_phone = request.data.get("customer_phone", "")
        if not customer_phone and request.user.phone:
            customer_phone = request.user.phone

        try:
            result = initiate_cashfree_payment(
                order,
                customer_email=customer_email,
                customer_phone=customer_phone,
            )
        except ValueError as e:
            return Response(
                {"error": {"message": str(e)}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Persist a Payment record so CashfreeVerifyView can look up the
        # cf_order_id when the customer returns from checkout.  Reuses an
        # existing row when one already exists for this order.
        payment, _created = Payment.objects.update_or_create(
            order=order,
            defaults={
                "user": request.user,
                "provider": "cashfree",
                "razorpay_order_id": result["cf_order_id"],
                "razorpay_payment_id": result["payment_session_id"],
                "amount": order.payable_amount,
                "status": "created",
                "raw_response": {
                    "cashfree_merchant_order_id": result.get("order_id", str(order.id)),
                },
            },
        )

        return Response(
            {
                "cf_order_id": result["cf_order_id"],
                "payment_session_id": result["payment_session_id"],
                "order_status": result["order_status"],
                "cashback_used": str(order.cashback_used),
            }
        )


class CashfreeVerifyView(APIView):
    """Verify Cashfree payment status after return from checkout.

    GET ``/api/v1/payments/cashfree/verify/?order_id=<order_id>``

    Called by the frontend when the customer returns to the return URL.
    Idempotent — safe on page refresh.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: HttpRequest) -> Response:
        order_id = request.query_params.get("order_id")
        if not order_id:
            return Response(
                {"error": {"message": "order_id query parameter is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except (Order.DoesNotExist, ValueError, TypeError):
            return Response(
                {"error": {"message": "Order not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # If already paid, return immediately
        if order.payment_status == "paid":
            payment = Payment.objects.filter(order=order, provider="cashfree").first()
            return Response(
                {
                    "paid": True,
                    "order_id": str(order.id),
                    "order_number": order.order_number,
                    "order_status": order.status,
                    "payment_status": order.payment_status,
                    "amount": str(order.payable_amount),
                    "cashback_used": str(order.cashback_used),
                    "transaction_id": payment.transaction_id if payment else "",
                    "message": "Payment successful.",
                }
            )

        # Find the Cashfree order ID from the payment record
        payment = Payment.objects.filter(order=order, provider="cashfree").first()
        if not payment or not payment.razorpay_order_id:
            return Response(
                {
                    "paid": False,
                    "order_id": str(order.id),
                    "order_number": order.order_number,
                    "payment_status": order.payment_status,
                    "amount": str(order.grand_total),
                    "cashback_used": str(order.cashback_used),
                    "message": "No Cashfree payment found for this order.",
                }
            )

        # Verify with Cashfree using the stored merchant order ID
        # (not the original PACHOOS order.id, which may differ from
        # the unique Cashfree order ID used for this payment attempt).
        cashfree_order_id = str(order.id)
        if payment.raw_response:
            cashfree_order_id = payment.raw_response.get(
                "cashfree_merchant_order_id", str(order.id)
            )
        result = confirm_cashfree_payment(order, cashfree_order_id)

        return Response(
            {
                "paid": result["paid"],
                "order_id": str(order.id),
                "order_number": order.order_number,
                "order_status": order.status,
                "payment_status": order.payment_status,
                "cf_order_status": result.get("cf_order_status", ""),
                "cf_payment_status": result.get("cf_payment_status", ""),
                "amount": str(order.payable_amount),
                "cashback_used": str(order.cashback_used),
                "transaction_id": result["payment"].transaction_id if result.get("payment") else "",
                "message": result["message"],
            }
        )


class CashfreeWebhookView(APIView):
    """Handle Cashfree webhook events (PAYMENT_SUCCESS_WEBHOOK, etc.).

    Public endpoint — no authentication. Signature is verified using the
    webhook secret.
    """

    permission_classes = []

    def post(self, request: HttpRequest) -> Response:
        payload = request.data
        request_body = request.body
        request_headers = {
            "x-webhook-signature": request.headers.get("x-webhook-signature", ""),
            "x-webhook-timestamp": request.headers.get("x-webhook-timestamp", ""),
        }

        result = handle_cashfree_webhook(payload, request_body, request_headers)

        if not result["handled"]:
            return Response(
                {"error": {"message": result["message"]}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"status": "ok"})
