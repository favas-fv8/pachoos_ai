"""Wallet API routes."""
from django.urls import path

from apps.wallet.views import (
    AdminDebtAdjustView,
    AdminDebtBillView,
    AdminDebtBookDetailView,
    AdminDebtBookLinkView,
    AdminDebtBookListCreateView,
    AdminDebtPaymentView,
    CustomerDebtBookView,
    CustomerDebtNoteView,
    DebtAdjustView,
    DebtBookNotesView,
    DebtHistoryView,
    MintVoucherView,
    RedeemVoucherView,
    VoucherListView,
    WalletBalanceView,
    WalletHistoryView,
)

urlpatterns = [
    path("balance/", WalletBalanceView.as_view(), name="wallet-balance"),
    path("history/", WalletHistoryView.as_view(), name="wallet-history"),
    path("vouchers/", VoucherListView.as_view(), name="voucher-list"),
    path("vouchers/redeem/", RedeemVoucherView.as_view(), name="voucher-redeem"),
    path("vouchers/mint/", MintVoucherView.as_view(), name="voucher-mint"),
    # Admin Debt Book
    path("debt/books/", AdminDebtBookListCreateView.as_view(), name="debt-book-list"),
    path("debt/books/<uuid:book_id>/", AdminDebtBookDetailView.as_view(), name="debt-book-detail"),
    path("debt/books/<uuid:book_id>/bills/", AdminDebtBillView.as_view(), name="debt-book-bill"),
    path("debt/books/<uuid:book_id>/payments/", AdminDebtPaymentView.as_view(), name="debt-book-payment"),
    path("debt/books/<uuid:book_id>/adjustments/", AdminDebtAdjustView.as_view(), name="debt-book-adjust"),
    path("debt/books/<uuid:book_id>/link/", AdminDebtBookLinkView.as_view(), name="debt-book-link"),
    path("debt/books/<uuid:book_id>/notes/", DebtBookNotesView.as_view(), name="debt-book-notes"),
    # Customer Debt Book
    path("my/debt/", CustomerDebtBookView.as_view(), name="customer-debt-book"),
    path("my/debt/notes/", CustomerDebtNoteView.as_view(), name="customer-debt-note"),
    # Legacy debt endpoints (backwards compatible)
    path("debt/adjust/", DebtAdjustView.as_view(), name="debt-adjust"),
    path("debt/history/", DebtHistoryView.as_view(), name="debt-history"),
]
