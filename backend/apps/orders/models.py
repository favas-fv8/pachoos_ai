"""Orders app — order lifecycle, timeline, delivery, payments."""
from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel, UUIDPrimaryKeyModel


class Order(UUIDPrimaryKeyModel, TimeStampedModel):
    """A customer order."""

    shop = models.ForeignKey(
        "shops.Shop", on_delete=models.PROTECT, related_name="orders"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    order_number = models.CharField(max_length=14, unique=True, db_index=True)

    # Status lifecycle
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("accepted", "Accepted"),
            ("preparing", "Preparing"),
            ("packed", "Packed"),
            ("out_for_delivery", "Out for Delivery"),
            ("delivered", "Delivered"),
            ("cancelled", "Cancelled"),
            ("refunded", "Refunded"),
        ],
        default="pending",
    )

    # Financials
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Coupon / voucher
    coupon_id = models.BigIntegerField(null=True, blank=True)
    coupon_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    voucher_id = models.BigIntegerField(null=True, blank=True)
    voucher_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Delivery
    delivery_address_id = models.BigIntegerField(null=True, blank=True)
    distance_km = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    delivery_free = models.BooleanField(default=False)
    delivery_eta = models.DateTimeField(null=True, blank=True)

    # Cashback earned
    cashback_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cashback_credited_at = models.DateTimeField(null=True, blank=True)

    # Cancellation
    cancellation_reason = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["order_number"]),
        ]

    def __str__(self):
        return f"#{self.order_number} ({self.status})"


class OrderItem(TimeStampedModel):
    """A single line item within an order."""

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="order_items"
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    product_name = models.CharField(max_length=200)
    variant_name = models.CharField(max_length=60, blank=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    gst_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"


class OrderTimeline(UUIDPrimaryKeyModel, TimeStampedModel):
    """Immutable log of every status change on an order."""

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="timeline"
    )
    status = models.CharField(max_length=30, db_index=True)
    note = models.CharField(max_length=255, blank=True)
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_actions",
    )
    actor_role = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["-created_at"]


class Delivery(UUIDPrimaryKeyModel, TimeStampedModel):
    """Delivery partner assignment and tracking."""

    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name="delivery"
    )
    partner_name = models.CharField(max_length=120, blank=True)
    partner_phone = models.CharField(max_length=15, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    proof_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)