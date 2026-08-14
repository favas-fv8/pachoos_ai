"""Django admin for orders models."""
from django.contrib import admin

from apps.orders.models import (
    Order,
    OrderItem,
    OrderTimeline,
    Delivery,
)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "user",
        "status",
        "grand_total",
        "delivery_free",
        "created_at",
    )
    list_filter = ("status", "delivery_free")
    search_fields = ("order_number", "user__phone")
    date_hierarchy = "created_at"


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "product_name", "quantity", "line_total")
    list_filter = ("product_name",)


@admin.register(OrderTimeline)
class OrderTimelineAdmin(admin.ModelAdmin):
    list_display = ("created_at", "order", "status", "actor_role")
    list_filter = ("status",)
    date_hierarchy = "created_at"


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "partner_name", "assigned_at", "delivered_at")
    list_filter = ("assigned_at",)