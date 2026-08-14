from django.contrib import admin

from apps.payments.models import Invoice, Payment, Refund


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["order", "user", "method", "amount", "status", "created_at"]
    list_filter = ["status", "method", "created_at"]
    search_fields = ["razorpay_payment_id", "razorpay_order_id", "order__order_number"]
    readonly_fields = ["created_at", "updated_at", "raw_response"]


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ["payment", "amount", "status", "reason", "created_at"]
    list_filter = ["status", "created_at"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["order", "invoice_number", "grand_total", "generated_at"]
    search_fields = ["invoice_number", "order__order_number"]