"""Django admin registrations for identity models."""
from django.contrib import admin

from apps.accounts.models import ActivityLog, AuditLog, User, UserDevice


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "phone", "email", "full_name", "role", "is_active", "is_verified")
    list_filter = ("role", "is_active", "is_verified")
    search_fields = ("phone", "email", "full_name")
    fieldsets = (
        (None, {"fields": ("phone", "email", "password")}),
        ("Profile", {"fields": ("full_name", "role", "shop", "avatar_url")}),
        ("Status", {"fields": ("is_active", "is_verified", "is_staff", "is_superuser")}),
        ("Referral", {"fields": ("referral_code", "referred_by")}),
        ("Meta", {"fields": ("last_login_at", "last_login_ip", "last_login_ua")}),
    )


@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "device_name", "platform", "browser", "last_seen_at", "revoked_at")
    search_fields = ("user__phone", "user__email", "device_name")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "entity_type", "entity_id", "user", "ip")
    list_filter = ("action", "entity_type")
    search_fields = ("entity_id", "user__phone")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "activity_type", "description")
    list_filter = ("activity_type",)
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False
