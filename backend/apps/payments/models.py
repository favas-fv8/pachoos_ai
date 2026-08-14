"""Payment models — Razorpay records, refunds, GST invoices."""
from django.conf import settings
from django.db import models

from apps.core.models import UUIDPrimaryKeyModel, TimeStampedModel


class Payment(UUIDPrimaryKeyModel, TimeStampedModel):
    """Payment record for an order."""

    order = models.OneToOneField(
        "orders.Order", on_delete=models.CASCADE, related_name="payment"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
    )
    razorpay_order_id = models.CharField(max_length=64, blank=True)
    razorpay_payment_id = models.CharField(max_length=64, blank=True)
    razorpay_signature = models.CharField(max_length=256, blank=True)
    method = models.CharField(
        max_length=20,
        choices=[
            ("upi", "UPI"),
            ("card", "Card"),
            ("netbanking", "Net Banking"),
            ("wallet", "Wallet"),
            ("emi", "EMI"),
        ],
        default="upi",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=[
            ("created", "Created"),
            ("authorized", "Authorized"),
            ("captured", "Captured"),
            ("failed", "Failed"),
            ("refunded", "Refunded"),
            ("partially_refunded", "Partially Refunded"),
        ],
        default="created",
    )
    attempts = models.PositiveIntegerField(default=0)
    webhook_received_at = models.DateTimeField(null=True, blank=True)
    webhook_verified = models.BooleanField(default=False)
    raw_response = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["razorpay_payment_id"]),
            models.Index(fields=["razorpay_order_id"]),
        ]

    def __str__(self):
        return f"Payment {self.status} - {self.amount}"


class Refund(UUIDPrimaryKeyModel, TimeStampedModel):
    """Refund record for a payment."""

    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name="refunds"
    )
    razorpay_refund_id = models.CharField(max_length=64, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("processed", "Processed"),
            ("failed", "Failed"),
        ],
        default="pending",
    )
    reason = models.TextField(blank=True)
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="initiated_refunds",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Refund {self.status} - {self.amount}"


class BankAccount(TimeStampedModel):
    """A bank account used for transfers — the shop's payout account (admin
    managed) or a customer's own account (self-managed for settling debt).

    Only contact/identity details and the encrypted account number are stored;
    the raw number is never exposed by the API and online-banking passwords,
    PINs or credentials are never saved. ``account_number`` is AES-GCM
    encrypted (see :mod:`apps.payments.encryption`).
    """

    # Exactly one owner is set: an admin-managed *shop* account or a
    # customer-managed *user* account. Both are nullable so the model has no
    # meaningless stub values; serializers/services validate ownership.
    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bank_accounts",
        help_text="Shop whose payout account this is (admin managed).",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bank_accounts",
        help_text="Customer who owns this account (self managed).",
    )

    account_holder_name = models.CharField(max_length=150)
    bank_name = models.CharField(max_length=120)
    account_number_encrypted = models.TextField(help_text="AES-GCM ciphertext of the account number.")
    account_number_last4 = models.CharField(max_length=4, blank=True)
    ifsc = models.CharField(max_length=11, blank=True)

    is_active = models.BooleanField(default=True, help_text="Account status (active / inactive).")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["shop", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]
        verbose_name = "Bank account"
        verbose_name_plural = "Bank accounts"

    def __str__(self):
        owner = self.account_holder_name or self.bank_name or f"#{self.pk}"
        return f"Bank account {owner} ({self.bank_name})"

    @property
    def owner_shop(self) -> bool:
        return self.shop_id is not None

    def masked_account_number(self) -> str:
        """Masked form derived from the plaintext last 4 digits."""
        digits = self.account_number_last4
        return f"••••{digits}" if digits else "••••"

    def set_account_number(self, value: str):
        """Encrypt an account number and cache its last 4 digits (plaintext)."""
        from apps.payments.encryption import encrypt_account_number, normalize_account_number

        digits = normalize_account_number(value)
        self.account_number_encrypted = encrypt_account_number(digits)
        self.account_number_last4 = digits[-4:]


class Invoice(UUIDPrimaryKeyModel, TimeStampedModel):
    """GST invoice PDF for a completed order."""

    order = models.OneToOneField(
        "orders.Order", on_delete=models.CASCADE, related_name="invoice"
    )
    invoice_number = models.CharField(max_length=30, unique=True)
    pdf_url = models.URLField(blank=True)
    gstin_shop = models.CharField(max_length=15, blank=True)
    gstin_customer = models.CharField(max_length=15, blank=True)
    base_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self):
        return f"Invoice {self.invoice_number}"