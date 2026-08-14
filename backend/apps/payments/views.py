"""Payment views — Razorpay order creation, webhooks, refunds, invoices."""
import hashlib
import hmac

from django.conf import settings
from django.http import HttpRequest
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdmin, IsCustomer
from apps.orders.models import Order
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


def _resolve_shop(request):
    """Shop for staff-scoped operations (wallet-style middleware resolution)."""
    shop = getattr(request, "shop", None)
    if not shop:
        from apps.shops.models import Shop

        shop = Shop.objects.first()
    return shop


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
