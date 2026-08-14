"""Coupon models — percentage, flat, and BOGO discount coupons."""
import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel, UUIDPrimaryKeyModel


class Coupon(UUIDPrimaryKeyModel, TimeStampedModel):
    """A discount coupon usable by customers."""

    shop = models.ForeignKey(
        "shops.Shop", on_delete=models.PROTECT, related_name="coupons"
    )
    code = models.CharField(max_length=30, unique=True)
    kind = models.CharField(
        max_length=10,
        choices=[("percent", "Percent"), ("flat", "Flat"), ("bogo", "BOGO")],
    )
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Coupon {self.code} ({self.kind})"


class CouponRedemption(UUIDPrimaryKeyModel, TimeStampedModel):
    """Record of a coupon being applied to an order."""

    coupon = models.ForeignKey(
        Coupon, on_delete=models.PROTECT, related_name="redemptions"
    )
    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, related_name="coupon_redemptions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
    )
    redeemed_at = models.DateTimeField(auto_now_add=True)