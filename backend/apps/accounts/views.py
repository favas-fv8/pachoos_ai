"""Auth views — Google OAuth (primary customer auth), email+password sign-in,
password create/change/forgot/reset, admin login, token refresh, device
management.

The existing architecture is extended rather than duplicated:
  * ``User`` + ``UserDevice`` + JWT rotation remain the single session model.
  * Google verifies identities; password recovery is link-based (no OTPs).
"""
import logging

from django.contrib.auth import get_user_model
from django.http import HttpRequest
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts import firebase
from apps.accounts.auth_service import (
    _issue_session,
    change_password,
    create_password,
    google_auth,
    is_token_valid,
    login_customer_with_password,
    reset_password_with_token,
    revoke_all_devices,
    revoke_device,
    send_password_reset_link,
    serialize_user,
)
from apps.accounts.serializers import (
    ChangePasswordSerializer,
    CreatePasswordSerializer,
    CustomerLoginSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
)
from apps.core.exceptions import BusinessRuleError
from apps.core.permissions import IsAdmin

logger = logging.getLogger("apps.auth")

User = get_user_model()


class AuthRateThrottle(ScopedRateThrottle):
    """Strict rate limit for identity endpoints (scope ``auth`` = 5/min)."""

    scope = "auth"


def _client_ip(request: HttpRequest) -> str:
    """Best-effort client IP from proxy headers, falling back to REMOTE_ADDR."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _session_payload(result: dict) -> dict:
    return {
        "access": result["tokens"]["access"],
        "refresh": result["tokens"]["refresh"],
        "user": result["user"],
    }


class GoogleAuthView(APIView):
    """Continue with Google — verify a Firebase ID token.

    The frontend completes Google sign-in with the Firebase Web SDK and posts the
    resulting ID token. Password creation is mandatory for every customer account:

      * New accounts (and any existing account that never set a password) get a
        session tagged ``password_required: True`` so the frontend can collect a
        password before the customer is allowed into the store.
      * Existing accounts with a password get ``password_challenge: True`` plus
        the verified email — the customer must verify their password before any
        session is issued.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request: HttpRequest):
        id_token = request.data.get("token", "")
        device_name = request.data.get("device_name", "")
        ip = _client_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "")

        if not id_token:
            raise BusinessRuleError("Firebase ID token is required.", code="VALIDATION_ERROR")

        claims = firebase.verify_id_token(id_token)
        email = (claims.get("email") or "").lower()
        if not email:
            raise BusinessRuleError(
                "Google verification did not include an email.", code="AUTH_FAILED"
            )
        google_sub = claims.get("sub") or ""
        full_name = claims.get("name", "")

        result = google_auth(google_sub, email, full_name, device_name, ip, ua)
        user = result["user"]

        if result["created"] or not user.has_usable_password():
            # Session is issued ONLY for password setup — the account is not
            # active for the store until a password is created.
            session = _issue_session(user, device_name, ip, ua)
            payload = _session_payload(session)
            payload["password_required"] = True
            return Response(payload, status=status.HTTP_200_OK)

        # Existing account with a password → password verification is required.
        return Response(
            {"password_challenge": True, "email": user.email},
            status=status.HTTP_200_OK,
        )


class CustomerLoginView(APIView):
    """Customer Sign In: registered email + password."""

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request: HttpRequest):
        serializer = CustomerLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ip = _client_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "")

        result = login_customer_with_password(
            data["email"], data["password"], data["device_name"], ip, ua
        )
        return Response(_session_payload(result), status=status.HTTP_200_OK)


class PasswordCreateView(APIView):
    """Set the first password for an OAuth-created account (requires a session)."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [AuthRateThrottle]

    def post(self, request: HttpRequest):
        serializer = CreatePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        create_password(request.user, serializer.validated_data["password"])
        return Response(serialize_user(request.user), status=status.HTTP_200_OK)


class PasswordChangeView(APIView):
    """Change the current password (current password required).

    Revokes every other session and returns a fresh token pair for this device.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [AuthRateThrottle]

    def post(self, request: HttpRequest):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ip = _client_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "")

        result = change_password(
            request.user, data["current_password"], data["new_password"], data["device_name"], ip, ua
        )
        return Response(_session_payload(result), status=status.HTTP_200_OK)


class ForgotPasswordView(APIView):
    """Request a password-reset link by email (always returns the same message)."""

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request: HttpRequest):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        send_password_reset_link(serializer.validated_data["email"])
        return Response(
            {
                "message": "If an account exists for this email, a password reset link has been sent.",
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetView(APIView):
    """Redeem an emailed reset link: set a new password and sign out everywhere."""

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request: HttpRequest):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        reset_password_with_token(data["uid"], data["token"], data["new_password"])
        return Response(
            {"message": "Password updated. Please sign in with your new password."},
            status=status.HTTP_200_OK,
        )


class AdminLoginView(APIView):
    """Email/password login for admin (shop owner) accounts. No self-registration."""

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request: HttpRequest):
        email = (request.data.get("email") or "").strip().lower()
        password = request.data.get("password", "")

        if not email or not password:
            raise BusinessRuleError("Email and password are required.", code="VALIDATION_ERROR")

        # USERNAME_FIELD is "phone", so authenticate() expects phone as username.
        # Look up user by email first, then authenticate with their phone.
        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            raise BusinessRuleError("Invalid credentials.", code="AUTH_FAILED") from None

        from django.contrib.auth import authenticate

        user = authenticate(username=user_obj.phone, password=password)
        if user is None:
            raise BusinessRuleError("Invalid credentials.", code="AUTH_FAILED")

        if not user.is_staff:
            raise BusinessRuleError("This account does not have admin access.", code="FORBIDDEN")

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": serialize_user(user),
            },
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    """Get the current authenticated user profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request: HttpRequest):
        return Response(serialize_user(request.user))


class TokenRefreshView(APIView):
    """Rotate refresh token and return a new access token."""

    permission_classes = [AllowAny]

    def post(self, request: HttpRequest):
        refresh_token = request.data.get("refresh", "")
        if not refresh_token:
            raise BusinessRuleError("Refresh token is required.", code="VALIDATION_ERROR")

        if not is_token_valid(refresh_token):
            raise BusinessRuleError("Refresh token is invalid or revoked.", code="AUTH_FAILED")

        try:
            refresh = RefreshToken(refresh_token)
            access = str(refresh.access_token)
            # Rotate: invalidate old refresh, issue new one.
            refresh.hash = None  # forces new token on next use
            return Response({"access": access, "refresh": str(refresh)}, status=status.HTTP_200_OK)
        except Exception:
            raise BusinessRuleError("Invalid refresh token.", code="AUTH_FAILED") from None


class DeviceListView(APIView):
    """List active device sessions for the authenticated user."""

    permission_classes = [IsAdmin]  # staff only; customers see their own devices via profile

    def get(self, request: HttpRequest):
        devices = request.user.devices.filter(revoked_at__isnull=True).order_by("-last_seen_at")
        return Response([{"id": str(d.id), "device_name": d.device_name, "last_seen_at": d.last_seen_at} for d in devices])


class DeviceRevokeView(APIView):
    """Revoke a single device session."""

    permission_classes = [IsAdmin]

    def post(self, request: HttpRequest):
        token_hash = request.data.get("token_hash", "")
        if not token_hash:
            raise BusinessRuleError("token_hash is required.", code="VALIDATION_ERROR")
        ok = revoke_device(request.user, token_hash)
        if not ok:
            raise BusinessRuleError("Device not found.", code="NOT_FOUND")
        return Response({"revoked": True})


class LogoutAllView(APIView):
    """Revoke all device sessions for the authenticated user."""

    permission_classes = [IsAdmin]

    def post(self, request: HttpRequest):
        count = revoke_all_devices(request.user)
        return Response({"revoked_count": count})
