"""Django admin for cart models."""
from django.contrib import admin

from apps.cart.models import Cart, CartItem


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "shop", "item_count", "subtotal", "is_active", "created_at")
    list_filter = ("is_active", "shop")
    search_fields = ("user__phone", "user__email")


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "cart", "product", "variant", "quantity", "line_total")
    list_filter = ("product",)