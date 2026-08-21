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
    """Purchase intake — saving a purchase item automatically increases the
    product's stock (and mirrors variants), keeping /shop in sync."""
    list_display = ("id", "purchase", "product", "quantity", "unit_cost", "total")
    list_filter = ("purchase", "product")

    def save_model(self, request, obj, form, change):
        old_qty = obj.quantity if change else 0
        if change:
            old_qty = PurchaseItem.objects.get(pk=obj.pk).quantity
        super().save_model(request, obj, form, change)

        delta = obj.quantity - old_qty
        if delta:
            product = obj.product
            product.stock_quantity += delta
            product.save(update_fields=["stock_quantity"])
            product.variants.update(stock_quantity=product.stock_quantity)
            StockMovement.objects.create(
                product=product,
                variant=obj.variant,
                quantity=delta,
                reason="purchase" if delta > 0 else "adjustment",
                ref_purchase_id=obj.purchase_id,
                note=f"Purchase {obj.purchase.invoice_ref or obj.purchase_id}".strip(),
                created_by=request.user,
            )

    def delete_model(self, request, obj):
        product = obj.product
        quantity = obj.quantity
        purchase_id = obj.purchase_id
        super().delete_model(request, obj)
        product.stock_quantity -= quantity
        product.save(update_fields=["stock_quantity"])
        product.variants.update(stock_quantity=product.stock_quantity)
        StockMovement.objects.create(
            product=product,
            quantity=-quantity,
            reason="adjustment",
            ref_purchase_id=purchase_id,
            note="Purchase item removed",
            created_by=request.user,
        )