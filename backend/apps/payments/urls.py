from django.urls import path

from apps.payments.views import (
    AdminBankAccountDetailView,
    AdminBankAccountListCreateView,
    CustomerBankAccountDetailView,
    CustomerBankAccountListCreateView,
    InvoiceView,
    RazorpayOrderView,
    RazorpayWebhookView,
    RefundView,
)

urlpatterns = [
    path("razorpay/order/", RazorpayOrderView.as_view(), name="razorpay-order"),
    path("razorpay/webhook/", RazorpayWebhookView.as_view(), name="razorpay-webhook"),
    path("refund/", RefundView.as_view(), name="refund"),
    path("invoice/<int:order_id>/", InvoiceView.as_view(), name="invoice"),
    # Bank accounts — admin shop payout accounts
    path("bank-accounts/", AdminBankAccountListCreateView.as_view(), name="admin-bank-account-list"),
    path("bank-accounts/<int:pk>/", AdminBankAccountDetailView.as_view(), name="admin-bank-account-detail"),
    # Bank accounts — customer self-managed accounts
    path("my/bank-accounts/", CustomerBankAccountListCreateView.as_view(), name="customer-bank-account-list"),
    path("my/bank-accounts/<int:pk>/", CustomerBankAccountDetailView.as_view(), name="customer-bank-account-detail"),
]