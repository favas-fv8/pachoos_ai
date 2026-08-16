"""Catalog models — categories, products, variants, inventory, tags."""
import secrets

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


def _default_pid() -> str:
    """Generate a short, unique, human-typable Product ID (PID)."""
    return f"PCH-{secrets.token_hex(3).upper()}"


class Category(TimeStampedModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    image_url = models.URLField(blank=True)
    image = models.ImageField(
        upload_to="categories/",
        null=True,
        blank=True,
        help_text="Uploaded category image (stored locally in dev, S3 in prod).",
    )
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    @property
    def resolved_url(self) -> str:
        """Prefer the uploaded file; fall back to an external URL."""
        if self.image:
            try:
                return self.image.url
            except ValueError:
                pass
        return self.image_url


class Subcategory(TimeStampedModel):
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="subcategories"
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    image_url = models.URLField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]
        unique_together = [("category", "slug")]

    def __str__(self):
        return f"{self.category.name} → {self.name}"


class Product(TimeStampedModel):
    """A sellable item. Variants hold the actual stock/price."""

    subcategory = models.ForeignKey(
        Subcategory, on_delete=models.PROTECT, related_name="products"
    )
    pid = models.CharField(
        max_length=24,
        unique=True,
        blank=True,
        default=_default_pid,
        help_text="Unique Product ID shown in the admin catalog.",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    ingredients = models.TextField(blank=True)
    nutritional_info = models.JSONField(null=True, blank=True)
    brand = models.CharField(max_length=120, blank=True)
    sku = models.CharField(max_length=64, unique=True, blank=True)
    barcode = models.CharField(max_length=64, unique=True, null=True, blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    gst_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    stock_quantity = models.IntegerField(default=0)
    stock_unit = models.CharField(
        max_length=8,
        choices=[("kg", "Kilograms (kg)"), ("count", "Count (pieces)")],
        default="count",
        help_text="Unit for stock: kg for weight-based items, count for piece-based items.",
    )
    low_stock_threshold = models.PositiveIntegerField(default=5)
    freshness = models.CharField(
        max_length=16,
        choices=[
            ("fresh", "Fresh"),
            ("frozen", "Frozen"),
            ("bakery", "Bakery"),
            ("dry", "Dry"),
        ],
        default="fresh",
    )
    is_available = models.BooleanField(default=True)
    video_url = models.URLField(blank=True)
    avg_rating = models.DecimalField(
        max_digits=2, decimal_places=1, default=0
    )
    rating_count = models.PositiveIntegerField(default=0)
    times_sold = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["subcategory"]),
            models.Index(fields=["is_available"]),
            models.Index(fields=["avg_rating"], name="catalog_prod_avg_rating_idx"),
            models.Index(fields=["name"], name="catalog_prod_name_idx"),
        ]

    def __str__(self):
        return self.name

    @property
    def effective_price(self) -> float:
        discount = float(self.discount_percent) / 100
        return float(self.base_price) * (1 - discount)


class ProductVariant(TimeStampedModel):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="variants"
    )
    name = models.CharField(max_length=60, help_text="e.g. 500g, 1kg, Chocolate")
    sku = models.CharField(max_length=64, unique=True, blank=True)
    barcode = models.CharField(max_length=64, unique=True, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    stock_quantity = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("product", "name")]

    def __str__(self):
        return f"{self.product.name} — {self.name}"

    @property
    def effective_price(self) -> float:
        discount = float(self.discount_percent) / 100
        return float(self.price) * (1 - discount)


class ProductImage(TimeStampedModel):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(
        upload_to="products/",
        null=True,
        blank=True,
        help_text="Uploaded product photo (stored locally in dev, S3 in prod).",
    )
    image_url = models.URLField(blank=True)
    alt_text = models.CharField(max_length=200, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["sort_order"]
        unique_together = [("product", "sort_order")]

    @property
    def resolved_url(self) -> str:
        """Prefer the uploaded file; fall back to an external URL."""
        if self.image:
            try:
                return self.image.url
            except ValueError:
                pass
        return self.image_url


class Wishlist(TimeStampedModel):
    """A customer's wishlisted product."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wishlist_items",
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="wishlist_entries"
    )

    class Meta:
        unique_together = [("user", "product")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} ♥ {self.product}"


class Tag(TimeStampedModel):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ProductTag(TimeStampedModel):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="product_tags"
    )
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="product_tags")

    class Meta:
        unique_together = [("product", "tag")]


class StockMovement(TimeStampedModel):
    """Immutable ledger of every stock change."""

    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="stock_movements"
    )
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="stock_movements",
    )
    quantity = models.IntegerField(
        help_text="Positive = restock, negative = sale/adjustment"
    )
    reason = models.CharField(
        max_length=20,
        choices=[
            ("sale", "Sale"),
            ("purchase", "Purchase"),
            ("restock", "Restock"),
            ("adjustment", "Adjustment"),
            ("return", "Return"),
        ],
    )
    ref_order_id = models.CharField(
        max_length=36,
        null=True,
        blank=True,
        help_text="Order UUID that caused this movement (orders use UUID primary keys).",
    )
    ref_purchase_id = models.BigIntegerField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "-created_at"]),
        ]


class Purchase(TimeStampedModel):
    """Admin stock intake record."""

    shop = models.ForeignKey(
        "shops.Shop", on_delete=models.PROTECT, related_name="purchases"
    )
    supplier = models.CharField(max_length=120, blank=True)
    invoice_ref = models.CharField(max_length=64, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    purchased_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)


class PurchaseItem(TimeStampedModel):
    purchase = models.ForeignKey(
        Purchase, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="purchase_items"
    )
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True
    )
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
