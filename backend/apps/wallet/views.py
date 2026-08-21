"""Wallet views — balance, history, voucher redemption, Debt Book (admin + customer)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdmin, IsCustomer
from apps.orders.models import Order
from apps.wallet.models import DebtBook, DebtLedger, Voucher, WalletLedger
from apps.wallet.serializers import (
    DebtAdjustmentSerializer,
    DebtAdjustSerializer,
    DebtBillSerializer,
    DebtBookDetailSerializer,
    DebtBookListSerializer,
    DebtBookUpdateSerializer,
    DebtLedgerSerializer,
    DebtNoteCreateSerializer,
    DebtNoteSerializer,
    DebtPaymentSerializer,
    LinkDebtBookSerializer,
    MultiDebtBillSerializer,
    OfflineDebtBookCreateSerializer,
    RedeemCashbackSerializer,
    RedeemVoucherSerializer,
    VoucherSerializer,
    WalletBalanceSerializer,
    WalletLedgerSerializer,
)
from apps.wallet.services import (
    add_debt_adjustment,
    add_debt_bill,
    adjust_debt,
    delete_debt_customer,
    get_debt_balance,
    get_or_create_debt_book,
    get_total_cashback_redeemed,
    get_wallet_balance,
    link_offline_debt_book,
    post_debt_note,
    record_payment,
    redeem_cashback,
    redeem_voucher,
    update_debt_customer,
)

User = get_user_model()


def _resolve_shop(request):
    shop = getattr(request, "shop", None)
    if not shop:
        from apps.shops.models import Shop
        shop = Shop.objects.first()
    return shop


def _debt_book_or_404(book_id):
    try:
        return DebtBook.objects.select_related("user", "shop").get(id=book_id)
    except (DebtBook.DoesNotExist, ValueError):
        return None


class WalletBalanceView(APIView):
    """Get wallet summary for the current user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        shop = _resolve_shop(request)

        cashback = get_wallet_balance(user, shop)
        debt = get_debt_balance(user, shop)
        active_vouchers = Voucher.objects.filter(user=user, shop=shop, status="active").count()
        total_earned = (
            WalletLedger.objects.filter(user=user, shop=shop, reason="purchase_cashback")
            .aggregate(total=Sum("delta"))["total"]
            or Decimal("0.00")
        )
        total_redeemed = get_total_cashback_redeemed(user, shop)

        return Response(WalletBalanceSerializer({
            "cashback_balance": cashback,
            "debt_balance": debt,
            "active_vouchers": active_vouchers,
            "total_cashback_earned": total_earned,
            "cashback_redeemed": total_redeemed,
        }).data)


class WalletHistoryView(APIView):
    """Get cashback ledger history for the current user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        entries = WalletLedger.objects.filter(user=request.user).order_by("-created_at")[:50]
        return Response(WalletLedgerSerializer(entries, many=True).data)


class VoucherListView(APIView):
    """List vouchers for the current user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        vouchers = Voucher.objects.filter(user=request.user).order_by("-created_at")
        status_filter = request.query_params.get("status")
        if status_filter:
            vouchers = vouchers.filter(status=status_filter)
        return Response(VoucherSerializer(vouchers[:50], many=True).data)


class RedeemVoucherView(APIView):
    """Redeem a voucher against an order."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RedeemVoucherSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            order = Order.objects.get(id=data["order_id"], user=request.user)
        except Order.DoesNotExist:
            return Response(
                {"error": {"message": "Order not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            discount = redeem_voucher(request.user, data["voucher_code"], order)
        except ValueError as e:
            return Response(
                {"error": {"message": str(e)}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            "discount": str(discount),
            "message": f"Voucher applied: ₹{discount} discount",
        })


class DebtAdjustView(APIView):
    """Legacy admin-only: adjust a *registered* customer's debt/credit."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        serializer = DebtAdjustSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            user = User.objects.get(id=data["user_id"])
        except User.DoesNotExist:
            return Response(
                {"error": {"message": "User not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        entry = adjust_debt(
            user=user,
            shop=_resolve_shop(request),
            amount=data["amount"],
            reason=data["reason"],
            admin_user=request.user,
        )
        return Response(DebtLedgerSerializer(entry).data, status=status.HTTP_201_CREATED)


class DebtHistoryView(APIView):
    """Legacy admin-only: view debt history for a registered user."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response(
                {"error": {"message": "user_id is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entries = DebtLedger.objects.filter(user_id=user_id).order_by("-created_at")[:50]
        return Response(DebtLedgerSerializer(entries, many=True).data)


# ═════════════════════════════════════════════════════════════════════════════
# Debt Book — Admin
# ═════════════════════════════════════════════════════════════════════════════


class AdminDebtBookListCreateView(APIView):
    """Admin Debt Book — list customers with debt, or create a book."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        shop = _resolve_shop(request)
        qs = DebtBook.objects.filter(shop=shop).order_by("-created_at")
        q = request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(phone__icontains=q)
                | Q(user__full_name__icontains=q)
                | Q(user__phone__icontains=q)
                | Q(user__email__icontains=q)
            )
        books = []
        for book in qs:
            books.append(DebtBookListSerializer(book).data)
        return Response(books)

    def post(self, request):
        serializer = OfflineDebtBookCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data

        user = None
        if data.get("user_id") is not None:
            try:
                user = User.objects.get(id=data["user_id"])
            except User.DoesNotExist:
                return Response(
                    {"error": {"message": "User not found."}},
                    status=status.HTTP_404_NOT_FOUND,
                )

        book = get_or_create_debt_book(
            _resolve_shop(request), user=user,
            name=data["name"], phone=data["phone"], email=data["email"],
        )
        return Response(DebtBookDetailSerializer(book).data, status=status.HTTP_201_CREATED)


class AdminDebtBookDetailView(APIView):
    """Admin: full view of one customer's Debt Book (summary, entries, notes)."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, book_id):
        book = _debt_book_or_404(book_id)
        if book is None:
            return Response({"error": {"message": "Debt Book not found."}}, status=404)
        return Response(DebtBookDetailSerializer(book).data)

    def patch(self, request, book_id):
        """Edit an offline customer's contact details (name / phone / email)."""
        book = _debt_book_or_404(book_id)
        if book is None:
            return Response({"error": {"message": "Debt Book not found."}}, status=404)
        serializer = DebtBookUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            update_debt_customer(book, admin_user=request.user, request=request,
                                 **serializer.validated_data)
        except ValueError as e:
            return Response({"error": {"message": str(e)}}, status=status.HTTP_400_BAD_REQUEST)
        return Response(DebtBookDetailSerializer(book).data)

    def delete(self, request, book_id):
        """Delete an offline customer with no ledger history (history preserved)."""
        book = _debt_book_or_404(book_id)
        if book is None:
            return Response({"error": {"message": "Debt Book not found."}}, status=404)
        try:
            delete_debt_customer(book, admin_user=request.user, request=request)
        except ValueError as e:
            return Response({"error": {"message": str(e)}}, status=status.HTTP_409_CONFLICT)
        return Response({"message": "Debt Book deleted."}, status=status.HTTP_204_NO_CONTENT)


class AdminDebtBillView(APIView):
    """Admin: add debt (goods on credit) to a customer's Debt Book.

    Accepts either legacy single-product fields (``product_name``/``quantity``/
    ``unit_price``/``discount``) or a multi-product payload with ``items``.
    Totals are always recomputed on the backend.
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, book_id):
        book = _debt_book_or_404(book_id)
        if book is None:
            return Response({"error": {"message": "Debt Book not found."}}, status=404)

        if "items" in request.data:
            serializer = MultiDebtBillSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            entry = add_debt_bill(book, admin_user=request.user, request=request,
                                  **serializer.validated_data)
        else:
            serializer = DebtBillSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            entry = add_debt_bill(book, admin_user=request.user, request=request,
                                  **serializer.validated_data)
        return Response(DebtLedgerSerializer(entry).data, status=status.HTTP_201_CREATED)


class AdminDebtPaymentView(APIView):
    """Admin: record a payment against a customer's outstanding debt."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, book_id):
        book = _debt_book_or_404(book_id)
        if book is None:
            return Response({"error": {"message": "Debt Book not found."}}, status=404)
        serializer = DebtPaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            entry = record_payment(book, admin_user=request.user, request=request,
                                   **serializer.validated_data)
        except ValueError as e:
            return Response({"error": {"message": str(e)}}, status=status.HTTP_400_BAD_REQUEST)
        return Response(DebtLedgerSerializer(entry).data, status=status.HTTP_201_CREATED)


class AdminDebtAdjustView(APIView):
    """Admin: append a correction entry (immutable history preserved)."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, book_id):
        book = _debt_book_or_404(book_id)
        if book is None:
            return Response({"error": {"message": "Debt Book not found."}}, status=404)
        serializer = DebtAdjustmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        entry = add_debt_adjustment(book, admin_user=request.user, request=request,
                                    **serializer.validated_data)
        return Response(DebtLedgerSerializer(entry).data, status=status.HTTP_201_CREATED)


class AdminDebtBookLinkView(APIView):
    """Admin: safely link an offline Debt Book to a newly-registered customer."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, book_id):
        book = _debt_book_or_404(book_id)
        if book is None:
            return Response({"error": {"message": "Debt Book not found."}}, status=404)
        serializer = LinkDebtBookSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=serializer.validated_data["user_id"])
        except User.DoesNotExist:
            return Response({"error": {"message": "User not found."}}, status=404)

        try:
            link_offline_debt_book(book, user, request.user)
        except ValueError as e:
            return Response({"error": {"message": str(e)}}, status=status.HTTP_400_BAD_REQUEST)
        return Response(DebtBookDetailSerializer(book).data)


class DebtBookNotesView(APIView):
    """List / add notes (chat) for a Debt Book. Admins may read & write."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, book_id):
        book = _debt_book_or_404(book_id)
        if book is None:
            return Response({"error": {"message": "Debt Book not found."}}, status=404)
        return Response(DebtNoteSerializer(book.notes.all(), many=True).data)

    def post(self, request, book_id):
        book = _debt_book_or_404(book_id)
        if book is None:
            return Response({"error": {"message": "Debt Book not found."}}, status=404)
        serializer = DebtNoteCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            note = post_debt_note(book, request.user, serializer.validated_data["body"])
        except ValueError as e:
            return Response({"error": {"message": str(e)}}, status=status.HTTP_400_BAD_REQUEST)
        return Response(DebtNoteSerializer(note).data, status=status.HTTP_201_CREATED)


# ═════════════════════════════════════════════════════════════════════════════
# Debt Book — Customer (read-only money, own data only)
# ═════════════════════════════════════════════════════════════════════════════


class CustomerDebtBookView(APIView):
    """Customer: their own Debt Book — outstanding, statements, history, notes.

    Read-only on money: customers can never add/edit amounts or payments.
    """

    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        shop = _resolve_shop(request)
        book = DebtBook.objects.filter(user=request.user, shop=shop).first()
        if book is None:
            return Response({
                "id": None,
                "display_name": request.user.full_name or request.user.phone,
                "summary": {"outstanding": "0.00", "total_added": "0.00", "total_paid": "0.00"},
                "entries": [],
                "notes": [],
            })
        return Response(DebtBookDetailSerializer(book).data)


class CustomerDebtNoteView(APIView):
    """Customer: reply with a note about their own debt (money is read-only)."""

    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request):
        shop = _resolve_shop(request)
        book = DebtBook.objects.filter(user=request.user, shop=shop).first()
        if book is None:
            return Response({"error": {"message": "No Debt Book for this account."}}, status=404)

        serializer = DebtNoteCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            note = post_debt_note(book, request.user, serializer.validated_data["body"])
        except ValueError as e:
            return Response({"error": {"message": str(e)}}, status=status.HTTP_400_BAD_REQUEST)
        return Response(DebtNoteSerializer(note).data, status=status.HTTP_201_CREATED)


class RedeemCashbackView(APIView):
    """Redeem cashback from the wallet balance.

    POST ``{}`` or ``{amount: null}`` → redeem the full current balance.
    POST ``{amount: 250}``             → redeem a custom amount.

    Rules enforced server-side: balance must be ≥ ₹10; a custom amount must
    be ≥ ₹10 and ≤ the available balance. The redemption is recorded as an
    immutable ``cashback_redeemed`` ledger row (appears in Cashback History).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RedeemCashbackSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        shop = _resolve_shop(request)
        try:
            entry = redeem_cashback(
                request.user, shop, serializer.validated_data.get("amount")
            )
        except ValueError as e:
            return Response(
                {"error": {"message": str(e)}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            "message": f"Cashback redeemed: ₹{abs(entry.delta)}",
            "ledger": WalletLedgerSerializer(entry).data,
            "cashback_balance": str(get_wallet_balance(request.user, shop)),
            "cashback_redeemed": str(get_total_cashback_redeemed(request.user, shop)),
        })
