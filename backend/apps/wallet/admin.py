"""Django admin for wallet models."""
from django.contrib import admin

from apps.wallet.models import (
    DebtBillItem,
    DebtBook,
    DebtLedger,
    DebtNote,
    Voucher,
    VoucherRedemption,
    WalletLedger,
)


@admin.register(WalletLedger)
class WalletLedgerAdmin(admin.ModelAdmin):
    list_display = ("user", "shop", "delta", "balance_after", "reason", "created_at")
    list_filter = ("reason", "shop")
    search_fields = ("user__phone", "user__email", "note")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ("code", "user", "amount", "status", "expires_at", "used_at", "created_at")
    list_filter = ("status", "shop")
    search_fields = ("code", "user__phone", "user__email")
    readonly_fields = ("created_at",)


@admin.register(VoucherRedemption)
class VoucherRedemptionAdmin(admin.ModelAdmin):
    list_display = ("voucher", "order", "user", "amount_used", "redeemed_at")
    search_fields = ("voucher__code", "order__order_number", "user__phone")


@admin.register(DebtLedger)
class DebtLedgerAdmin(admin.ModelAdmin):
    list_display = ("book", "entry_type", "product_name", "delta", "prev_balance",
                    "balance_after", "updated_by", "created_at")
    list_filter = ("entry_type", "shop")
    search_fields = ("book__name", "book__phone", "user__phone", "user__email", "reason", "product_name")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "updated_at", "updated_by")


@admin.register(DebtBook)
class DebtBookAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "phone", "email", "shop", "created_at")
    search_fields = ("name", "phone", "email", "user__phone", "user__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(DebtBillItem)
class DebtBillItemAdmin(admin.ModelAdmin):
    list_display = ("bill", "product_name", "quantity", "unit", "unit_price",
                    "discount", "line_total")
    search_fields = ("product_name", "bill__book__name", "bill__book__phone")


@admin.register(DebtNote)
class DebtNoteAdmin(admin.ModelAdmin):
    list_display = ("book", "sender", "created_at")
    search_fields = ("book__name", "book__phone", "sender__phone", "sender__email", "body")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)
