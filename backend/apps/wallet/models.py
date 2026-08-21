"""Wallet models — cashback ledger, voucher pool, and debt ledger."""
from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel, UUIDPrimaryKeyModel


class WalletLedger(UUIDPrimaryKeyModel, TimeStampedModel):
    """Cashback ledger — balance only, never spendable directly."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet_ledger"
    )
    shop = models.ForeignKey(
        "shops.Shop", on_delete=models.PROTECT, related_name="wallet_ledgers"
    )
    delta = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reason = models.CharField(
        max_length=20,
        choices=[
            ("purchase_cashback", "Purchase cashback"),
            ("voucher_mint", "Voucher mint"),
            ("cashback_redeemed", "Cashback redeemed"),
            ("adjustment", "Adjustment"),
        ],
        default="purchase_cashback",
    )
    ref_order = models.ForeignKey(
        "orders.Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_ledgers"
    )
    ref_voucher = models.ForeignKey(
        "wallet.Voucher", on_delete=models.SET_NULL, null=True, blank=True, related_name="ledgers"
    )
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self):
        return f"Wallet {self.user_id}: {self.delta:+} ({self.reason})"


class Voucher(UUIDPrimaryKeyModel, TimeStampedModel):
    """A ₹10 voucher minted from cashback. Single-use, expires after VOUCHER_EXPIRY_DAYS."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vouchers"
    )
    shop = models.ForeignKey(
        "shops.Shop", on_delete=models.PROTECT, related_name="vouchers"
    )
    code = models.CharField(max_length=12, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=10.00)
    minted_from_ledger = models.ForeignKey(
        WalletLedger, on_delete=models.SET_NULL, null=True, blank=True, related_name="vouchers"
    )
    status = models.CharField(
        max_length=10,
        choices=[("active", "Active"), ("used", "Used"), ("expired", "Expired"), ("void", "Void")],
        default="active",
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Voucher {self.code} ({self.amount})"


class VoucherRedemption(UUIDPrimaryKeyModel, TimeStampedModel):
    """Record of a voucher being applied to an order."""

    voucher = models.ForeignKey(
        Voucher, on_delete=models.PROTECT, related_name="redemptions"
    )
    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, related_name="voucher_redemptions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
    )
    amount_used = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    redeemed_at = models.DateTimeField(auto_now_add=True)


class DebtBook(UUIDPrimaryKeyModel, TimeStampedModel):
    """A customer's Debt Book — one per customer.

    Anchors every registered or **offline** customer that has any debt. A
    registered customer has ``user`` set; an offline customer is identified by
    ``name``/``phone`` and is never given a login account. When an offline
    customer later registers, an admin links the book to the verified ``user``
    (see ``link_offline_debt_book``) — old ledger rows stay untouched.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="debt_book",
        help_text="Verified customer account (set once the customer registers).",
    )
    shop = models.ForeignKey(
        "shops.Shop", on_delete=models.PROTECT, related_name="debt_books"
    )
    name = models.CharField(max_length=150, blank=True, help_text="Offline customer name.")
    phone = models.CharField(max_length=15, blank=True, help_text="Offline customer phone (10 digits).")
    email = models.EmailField(
        max_length=254, blank=True, default="",
        help_text="Offline customer contact email (e.g. Gmail).",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Debt book"
        verbose_name_plural = "Debt books"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "shop"],
                name="uniq_debt_book_user_shop",
                condition=models.Q(user__isnull=False),
            )
        ]
        indexes = [models.Index(fields=["shop", "-created_at"])]

    def __str__(self):
        return f"Debt book: {self.name or self.phone or self.user or self.pk}"

    @property
    def is_offline(self) -> bool:
        return self.user_id is None

    @property
    def display_name(self) -> str:
        if self.user:
            return self.user.full_name or self.user.phone or self.user.email or "Customer"
        return self.name or self.phone or "Offline customer"


class DebtLedger(UUIDPrimaryKeyModel, TimeStampedModel):
    """Immutable, admin-only debt ledger for a customer's Debt Book.

    One row per transaction. Money movement rules:
      * ``bill``       — goods taken on credit: ``delta = +final amount``
      * ``payment``    — payment received:      ``delta = -amount paid``
      * ``adjustment`` — correction:            ``delta = ±amount``

    ``prev_balance`` → ``balance_after`` chain is monotonic per book. Rows are
    never edited/deleted; corrections append a new ``adjustment`` entry and the
    change is mirrored to AuditLog (see ``apps.admin_dashboard.activity``).
    """

    ENTRY_TYPES = [
        ("bill", "Debt added / goods on credit"),
        ("payment", "Payment received"),
        ("adjustment", "Adjustment / correction"),
    ]

    book = models.ForeignKey(
        DebtBook, on_delete=models.SET_NULL, null=True, blank=True, related_name="entries"
    )
    # Legacy anchor retained for registered customers; prefer ``book``.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="debt_ledger",
    )
    shop = models.ForeignKey(
        "shops.Shop", on_delete=models.PROTECT, related_name="debt_ledgers"
    )
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPES, default="bill", db_index=True)

    # Bill line (bill entries only) — flattened so each entry reads as a bill line.
    product_name = models.CharField(max_length=255, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Counter payment captured at the same time as a bill (bill entries only).
    # Nearly always 0; the payment is mirrored as its own immutable ledger row
    # so the running balance stays monotonic.
    amount_paid = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Amount paid at the counter when this bill was created.",
    )

    # Money movement (signed) + running outstanding.
    prev_balance = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Outstanding before this transaction.",
    )
    delta = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Positive = debt added, Negative = amount paid / correction downward",
    )
    balance_after = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Outstanding remaining after this transaction.",
    )

    reason = models.CharField(max_length=255, blank=True)
    note = models.TextField(blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="debt_updates",
        help_text="Admin who created/updated this entry.",
    )

    @property
    def final_amount(self):
        """Bill total after discount (qty × price − discount)."""
        return (self.quantity * self.unit_price) - self.discount

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Debt ledgers"
        indexes = [
            models.Index(fields=["book", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"DebtLedger {self.entry_type}: {self.delta:+} (after {self.balance_after})"


class DebtBillItem(UUIDPrimaryKeyModel, TimeStampedModel):
    """One product line of a single multi-product debt transaction.

    A "bill" ``DebtLedger`` entry (the immutable money movement row) owns zero
    or more :class:`DebtBillItem` children — one per product purchased at the
    same time. This is the proper 1 → N relationship for a debt transaction
    (never a comma-separated text blob). The parent ledger row still carries the
    flat ``product_name``/``quantity``/``unit_price`` fields for single-product
    backwards compatibility; multi-product bills use ``items`` instead and the
    totals are always recomputed on the backend (never trusted from the client).
    """

    UNIT_CHOICES = [
        ("kg", "kg"),
        ("count", "count"),
    ]

    bill = models.ForeignKey(
        DebtLedger, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="debt_bill_items",
        help_text="Optional catalog product this line was selected from.",
    )
    product_name = models.CharField(max_length=255, blank=True)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    unit = models.CharField(max_length=8, choices=UNIT_CHOICES, default="count")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.product_name or 'Item'} × {self.quantity}{self.unit}"


class DebtNote(UUIDPrimaryKeyModel, TimeStampedModel):
    """Notes / chat attached to a Debt Book.

    Admins add notes about a customer's debt; the customer can reply about
    their own debt. All messages are preserved chronologically; sender identity
    is resolved from ``sender`` (admins vs customer role) so the UI can
    distinguish Admin and Customer messages.
    """

    book = models.ForeignKey(DebtBook, on_delete=models.CASCADE, related_name="notes")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="debt_notes_sent",
    )
    body = models.TextField()

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["book", "created_at"])]

    def __str__(self):
        return f"DebtNote (#{self.book_id}) by {self.sender_id}"
