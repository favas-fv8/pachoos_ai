"""Shop registry.

Purpose: business operating configuration (name, location, timings, GSTIN,
delivery rules, logo). Branches may be added later as additional rows, but
staff is always the fixed set of 2 admins — adding a branch never creates
staff accounts.
"""
from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Shop(TimeStampedModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    tagline = models.CharField(max_length=200, blank=True)
    logo_url = models.URLField(blank=True)

    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    lng = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    gstin = models.CharField(max_length=15, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    timing_open = models.TimeField(null=True, blank=True)
    timing_close = models.TimeField(null=True, blank=True)

    delivery_radius_km = models.DecimalField(max_digits=5, decimal_places=2, default=2.00)
    free_delivery_min_order = models.DecimalField(max_digits=10, decimal_places=2, default=99.00)
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=20.00)

    is_active = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]
        verbose_name = "Shop"
        verbose_name_plural = "Shops"

    def __str__(self):
        return self.name

    @classmethod
    def primary(cls) -> "Shop | None":
        return cls.objects.filter(is_primary=True, is_active=True).order_by("id").first()

    @classmethod
    def delivery_rule(cls) -> dict:
        """Expose business delivery rules as a config dict."""
        shop = cls.primary()
        if shop:
            return {
                "free_delivery_min_order": float(shop.free_delivery_min_order),
                "free_delivery_max_km": float(shop.delivery_radius_km),
                "delivery_charge": float(shop.delivery_charge),
            }
        return settings.BUSINESS
