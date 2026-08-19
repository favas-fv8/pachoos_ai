from django.urls import path

from apps.payments.views import (
    AdminBankAccountDetailView,
    AdminBankAccountListCreateView,
    CashfreeOrderView,
    CashfreeVerifyView,
    CashfreeWebhookView,
    CustomerBankAccountDetailView,
    CustomerBankAccountListCreateView,
    DemoPaymentView,
    InvoiceView,
    OrderPaymentStatusView,
    RazorpayOrderView,
    RazorpayWebhookView,
    RefundView,
)

urlpatterns = [
    path("razorpay/order/", RazorpayOrderView.as_view(), name="razorpay-order"),
    path("razorpay/webhook/", RazorpayWebhookView.as_view(), name="razorpay-webhook"),
    # Demo Payment — simulated only, no real charge. Replaceable by a real
    # gateway later without touching the order/cart flow.
    path("demo/confirm/", DemoPaymentView.as_view(), name="demo-payment-confirm"),
    path(
        "order/<uuid:order_id>/status/",
        OrderPaymentStatusView.as_view(),
        name="order-payment-status",
    ),
    # Cashfree PG v2 — Sandbox / Production
    path("cashfree/order/", CashfreeOrderView.as_view(), name="cashfree-order"),
    path("cashfree/verify/", CashfreeVerifyView.as_view(), name="cashfree-verify"),
    path("cashfree/webhook/", CashfreeWebhookView.as_view(), name="cashfree-webhook"),
    path("refund/", RefundView.as_view(), name="refund"),
    path("invoice/<int:order_id>/", InvoiceView.as_view(), name="invoice"),
    # Bank accounts — admin shop payout accounts
    path("bank-accounts/", AdminBankAccountListCreateView.as_view(), name="admin-bank-account-list"),
    path("bank-accounts/<int:pk>/", AdminBankAccountDetailView.as_view(), name="admin-bank-account-detail"),
    # Bank accounts — customer self-managed accounts
    path("my/bank-accounts/", CustomerBankAccountListCreateView.as_view(), name="customer-bank-account-list"),
    path("my/bank-accounts/<int:pk>/", CustomerBankAccountDetailView.as_view(), name="customer-bank-account-detail"),
]
