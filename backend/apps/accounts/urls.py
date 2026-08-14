"""Auth routes — Google OAuth, customer email+password login, password
create/change/forgot/reset, admin login, token refresh, device management."""
from django.urls import path

from apps.accounts.views import (
    AdminLoginView,
    CustomerLoginView,
    DeviceListView,
    DeviceRevokeView,
    ForgotPasswordView,
    GoogleAuthView,
    LogoutAllView,
    MeView,
    PasswordChangeView,
    PasswordCreateView,
    PasswordResetView,
    TokenRefreshView,
)

urlpatterns = [
    path("google/", GoogleAuthView.as_view(), name="google-auth"),
    path("customer/login/", CustomerLoginView.as_view(), name="customer-login"),
    path("password/create/", PasswordCreateView.as_view(), name="password-create"),
    path("password/change/", PasswordChangeView.as_view(), name="password-change"),
    path("password/forgot/", ForgotPasswordView.as_view(), name="password-forgot"),
    path("password/reset/", PasswordResetView.as_view(), name="password-reset"),
    path("admin/login/", AdminLoginView.as_view(), name="admin-login"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("devices/", DeviceListView.as_view(), name="device-list"),
    path("devices/revoke/", DeviceRevokeView.as_view(), name="device-revoke"),
    path("devices/revoke-all/", LogoutAllView.as_view(), name="logout-all"),
]
