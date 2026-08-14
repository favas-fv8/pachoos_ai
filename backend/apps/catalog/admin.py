"""Django admin for catalog models."""
from django.contrib import admin

from apps.catalog.models import (
    Category,
    Subcategory,
    Product,
    ProductVariant,
    ProductImage,
    Tag,
    StockMovement,
    Purchase,
    PurchaseItem,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "is_active")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Subcategory)
class SubcategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "category", "name", "slug", "is_active")
    list_filter = ("category", "is_active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "subcategory",
        "base_price",
        "discount_percent",
        "stock_quantity",
        "freshness",
        "is_available",
    )
    list_filter = ("subcategory__category", "freshness", "is_available")
    search_fields = ("name", "sku", "barcode")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "name", "price", "stock_quantity", "is_active")
    list_filter = ("product", "is_active")


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "sort_order", "is_primary")
    list_filter = ("product",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug")
    search_fields = ("name",)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "variant", "quantity", "reason", "created_at")
    list_filter = ("reason", "product")
    date_hierarchy = "created_at"


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("id", "shop", "supplier", "total_amount", "purchased_at")
    list_filter = ("shop",)
    date_hierarchy = "purchased_at"


@admin.register(PurchaseItem)
class PurchaseItemAdmin(admin.ModelAdmin):
    list_display = ("id", "purchase", "product", "quantity", "unit_cost", "total")
    list_filter = ("purchase", "product")