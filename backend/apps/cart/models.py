"""Cart models — cart and cart items."""
from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Cart(TimeStampedModel):
    """A shopping cart tied to a user (or null for anonymous sessions)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="carts",
    )
    shop = models.ForeignKey(
        "shops.Shop", on_delete=models.PROTECT, related_name="carts"
    )
    session_key = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["session_key"]),
        ]
        unique_together = [("user", "is_active")]

    def __str__(self):
        return f"Cart {self.pk} ({self.user or self.session_key})"

    @property
    def item_count(self) -> int:
        return self.items.filter(is_active=True).count()

    @property
    def subtotal(self) -> float:
        return sum(
            item.line_total for item in self.items.filter(is_active=True)
        )


class CartItem(TimeStampedModel):
    """A single line item in a cart."""

    cart = models.ForeignKey(
        Cart, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="cart_items"
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        unique_together = [("cart", "product", "variant")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"

    @property
    def line_total(self) -> float:
        price = (
            self.variant.effective_price
            if self.variant
            else self.product.effective_price
        )
        discount = price * (float(self.discount_percent) / 100)
        return float(price - discount) * self.quantity