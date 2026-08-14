from django.contrib import admin

from apps.shops.models import Shop


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "city", "is_primary", "is_active")
    list_filter = ("is_active", "is_primary", "state")
    search_fields = ("name", "slug", "city")
