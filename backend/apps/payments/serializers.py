"""Payment serializers."""
import re

from rest_framework import serializers

from apps.payments.models import BankAccount, Invoice, Payment, Refund

IFSC_OK = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"


class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = "__all__"


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = "__all__"


class RazorpayOrderSerializer(serializers.Serializer):
    amount = serializers.IntegerField()
    currency = serializers.CharField(default="INR")
    receipt = serializers.CharField(required=False, default="")
    notes = serializers.DictField(required=False, default=dict)


class RazorpayPaymentSerializer(serializers.Serializer):
    razorpay_order_id = serializers.CharField()
    razorpay_payment_id = serializers.CharField()
    razorpay_signature = serializers.CharField()


class RefundRequestSerializer(serializers.Serializer):
    payment_id = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    reason = serializers.CharField(required=False, default="")
    speed = serializers.CharField(
        required=False,
        default="normal",
        help_text="normal | instant | express",
    )


# ── Bank accounts ──────────────────────────────────────────────────────────────

def _normalize_ifsc(value: str) -> str:
    """Upper-case IFSC and enforce the RBI format (4 letters, 0, 6 chars)."""
    ifsc = (value or "").strip().upper()
    if not IFSC_OK.match(ifsc):
        raise serializers.ValidationError(
            "Enter a valid IFSC code (e.g. HDFC0001234)."
        )
    return ifsc


def _normalize_account_number(value: str) -> str:
    from apps.payments.encryption import normalize_account_number

    try:
        return normalize_account_number(value)
    except ValueError as e:
        raise serializers.ValidationError(str(e)) from None


class BankAccountWriteSerializer(serializers.Serializer):
    """Shared write fields (customer & admin). Never persists the raw number —
    ``account_number`` is validated then encrypted by the model.
    """

    account_holder_name = serializers.CharField(max_length=150)
    bank_name = serializers.CharField(max_length=120)
    account_number = serializers.CharField()
    ifsc = serializers.CharField(max_length=11)

    def validate_account_holder_name(self, value):
        if not (value or "").strip():
            raise serializers.ValidationError("Account holder name is required.")
        return value.strip()

    def validate_bank_name(self, value):
        if not (value or "").strip():
            raise serializers.ValidationError("Bank name is required.")
        return value.strip()

    def validate_account_number(self, value):
        return _normalize_account_number(value)

    def validate_ifsc(self, value):
        return _normalize_ifsc(value)


class BankAccountAdminWriteSerializer(BankAccountWriteSerializer):
    """Admin write serializer — adds the account status toggle."""

    is_active = serializers.BooleanField(required=False, default=True)


class BankAccountSerializer(serializers.ModelSerializer):
    """Output: masked account number only, never the plaintext."""

    account_number_masked = serializers.SerializerMethodField()
    account_number_last4 = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    owner_shop = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = BankAccount
        fields = [
            "id",
            "account_holder_name",
            "bank_name",
            "account_number_masked",
            "account_number_last4",
            "ifsc",
            "is_active",
            "owner_shop",
            "created_at",
        ]

    def get_account_number_masked(self, obj):
        return obj.masked_account_number()