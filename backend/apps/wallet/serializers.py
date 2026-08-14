"""Wallet serializers."""
from decimal import Decimal

from rest_framework import serializers

from apps.wallet.models import (
    DebtBillItem,
    DebtBook,
    DebtLedger,
    DebtNote,
    Voucher,
    VoucherRedemption,
    WalletLedger,
)
from apps.wallet.services import phone_key, validate_email, validate_phone


class WalletLedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletLedger
        fields = "__all__"


class VoucherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Voucher
        fields = "__all__"


class VoucherRedemptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoucherRedemption
        fields = "__all__"


class DebtBillItemSerializer(serializers.ModelSerializer):
    """One product line of a bill (1 bill → N items)."""

    line_total = serializers.SerializerMethodField()

    class Meta:
        model = DebtBillItem
        fields = [
            "id",
            "product",
            "product_name",
            "quantity",
            "unit",
            "unit_price",
            "discount",
            "line_total",
        ]

    def get_line_total(self, obj):
        return str(obj.line_total)


class DebtLedgerSerializer(serializers.ModelSerializer):
    """Ledger row → a statement/bill line for both Admin and Customer Debt Book."""

    entry_label = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()
    discount_total = serializers.SerializerMethodField()
    amount_added = serializers.SerializerMethodField()
    amount_paid = serializers.SerializerMethodField()
    remaining = serializers.SerializerMethodField()
    bill_remaining = serializers.SerializerMethodField()
    updated_by_name = serializers.CharField(source="updated_by.full_name", read_only=True, default="")
    items = DebtBillItemSerializer(many=True, read_only=True)

    class Meta:
        model = DebtLedger
        fields = [
            "id",
            "entry_type",
            "entry_label",
            "product_name",
            "quantity",
            "unit_price",
            "discount",
            "line_total",
            "subtotal",
            "discount_total",
            "items",
            "prev_balance",
            "delta",
            "amount_added",
            "amount_paid",
            "balance_after",
            "remaining",
            "bill_remaining",
            "reason",
            "note",
            "updated_by",
            "updated_by_name",
            "created_at",
        ]

    def get_entry_label(self, obj):
        return obj.get_entry_type_display()

    def get_line_total(self, obj):
        return str(max(obj.final_amount, 0))

    def _bill_items(self, obj):
        return list(obj.items.all())

    def get_subtotal(self, obj):
        if obj.entry_type != "bill":
            return "0"
        total = sum(i.quantity * i.unit_price for i in self._bill_items(obj))
        return str(total.quantize(Decimal("0.01")))

    def get_discount_total(self, obj):
        return str(sum(i.discount for i in self._bill_items(obj)) if obj.entry_type == "bill" else 0)

    def get_amount_added(self, obj):
        return str(max(obj.delta, 0) if obj.entry_type != "payment" else 0)

    def get_amount_paid(self, obj):
        if obj.entry_type == "payment":
            return str(max(-obj.delta, 0))
        return str(max(obj.amount_paid, 0))

    def get_remaining(self, obj):
        return str(obj.balance_after)

    def get_bill_remaining(self, obj):
        """Counter amount still owed for a single bill (total − paid at counter)."""
        if obj.entry_type != "bill":
            return "0"
        return str(max(obj.final_amount - obj.amount_paid, 0))


class DebtNoteSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    sender_role = serializers.SerializerMethodField()

    class Meta:
        model = DebtNote
        fields = ["id", "body", "sender", "sender_name", "sender_role", "created_at"]

    def get_sender_name(self, obj):
        if not obj.sender:
            return "System"
        return obj.sender.full_name or obj.sender.phone or obj.sender.email or "Staff"

    def get_sender_role(self, obj):
        if not obj.sender:
            return "system"
        return obj.sender.role


class DebtBookListSerializer(serializers.ModelSerializer):
    """Admin Debt Book default view row."""

    is_offline = serializers.BooleanField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    outstanding = serializers.SerializerMethodField()
    entry_count = serializers.SerializerMethodField()
    user_id = serializers.IntegerField(source="user.id", read_only=True, default=None)

    class Meta:
        model = DebtBook
        fields = [
            "id",
            "user_id",
            "is_offline",
            "name",
            "phone",
            "email",
            "display_name",
            "outstanding",
            "entry_count",
            "created_at",
        ]

    def get_outstanding(self, obj):
        from apps.wallet.services import get_debt_book_summary

        return get_debt_book_summary(obj)["outstanding"]

    def get_entry_count(self, obj):
        return DebtLedger.objects.filter(book=obj).count()


class DebtBookDetailSerializer(serializers.ModelSerializer):
    """Full Debt Book: summary, statement entries and notes/chat."""

    is_offline = serializers.BooleanField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    summary = serializers.SerializerMethodField()
    entries = DebtLedgerSerializer(many=True, read_only=True)
    notes = DebtNoteSerializer(many=True, read_only=True)

    class Meta:
        model = DebtBook
        fields = [
            "id",
            "user_id",
            "is_offline",
            "name",
            "phone",
            "email",
            "display_name",
            "summary",
            "entries",
            "notes",
            "created_at",
        ]

    def get_summary(self, obj):
        from apps.wallet.services import get_debt_book_summary

        return get_debt_book_summary(obj)


class OfflineDebtBookCreateSerializer(serializers.Serializer):
    """Create a Debt Book for an offline customer (or by registered user_id)."""

    user_id = serializers.IntegerField(required=False, default=None)
    name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=15, required=False, allow_blank=True, default="")
    email = serializers.EmailField(max_length=254, required=False, allow_blank=True, default="")

    def validate_phone(self, value):
        if not value:
            return ""
        try:
            return validate_phone(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e)) from None

    def validate_email(self, value):
        if not value:
            return ""
        try:
            return validate_email(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e)) from None


class DebtBookUpdateSerializer(serializers.Serializer):
    """Edit an offline Debt Book's contact details (admin only)."""

    name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=15, required=False, allow_blank=True)
    email = serializers.EmailField(max_length=254, required=False, allow_blank=True)

    def validate_phone(self, value):
        if value is None or value == "":
            return ""
        try:
            return validate_phone(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e)) from None

    def validate_email(self, value):
        if value is None or value == "":
            return ""
        try:
            return validate_email(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e)) from None


class DebtBillItemInputSerializer(serializers.Serializer):
    """One product line on a multi-product bill (server recomputes totals)."""

    product_id = serializers.UUIDField(required=False, allow_null=True)
    product_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    quantity = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, default=1, min_value=Decimal("0.01"))
    unit = serializers.ChoiceField(choices=["kg", "count"], required=False, default="count")
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0, min_value=Decimal("0"))
    discount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0, min_value=Decimal("0"))


class MultiDebtBillSerializer(serializers.Serializer):
    """Add a *multi-product* debt transaction: items[] → one bill + optional counter payment."""

    items = DebtBillItemInputSerializer(many=True)
    amount_paid = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0, min_value=Decimal("0"))
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("A bill must contain at least one product.")
        for item in value:
            if not (item.get("product_name") or "").strip():
                raise serializers.ValidationError("Each product line needs a name.")
        return value


class DebtBillSerializer(serializers.Serializer):
    """Add debt (goods on credit) — one bill line with product details."""

    product_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    quantity = serializers.IntegerField(required=False, default=1, min_value=1)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0)
    discount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    note = serializers.CharField(required=False, allow_blank=True, default="")


class DebtPaymentSerializer(serializers.Serializer):
    """Record a payment against outstanding debt."""

    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    note = serializers.CharField(required=False, allow_blank=True, default="")


class DebtAdjustmentSerializer(serializers.Serializer):
    """Correction entry — signed amount, never touches historical rows."""

    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    note = serializers.CharField(required=False, allow_blank=True, default="")


class DebtNoteCreateSerializer(serializers.Serializer):
    body = serializers.CharField()


class LinkDebtBookSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()


class WalletBalanceSerializer(serializers.Serializer):
    cashback_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    debt_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    active_vouchers = serializers.IntegerField()
    total_cashback_earned = serializers.DecimalField(max_digits=10, decimal_places=2)


class RedeemVoucherSerializer(serializers.Serializer):
    voucher_code = serializers.CharField(max_length=12)
    order_id = serializers.UUIDField()


class DebtAdjustSerializer(serializers.Serializer):
    """Legacy admin debt adjustment (registered customer by user_id)."""

    user_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    reason = serializers.CharField(max_length=255)
