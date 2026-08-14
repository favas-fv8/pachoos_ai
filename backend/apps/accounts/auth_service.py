"""Auth service layer — Google identity (create-if-not-exists) + password
management, JWT issuance, device registration and session invalidation.

Password recovery is link-based (Django ``PasswordResetTokenGenerator``); there
are no OTPs. Password changes and resets revoke every device session.
"""
import hashlib
import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.email_service import (
    send_new_device_email,
    send_password_changed_email,
    send_password_created_email,
    send_password_reset_done_email,
    send_password_reset_link_email,
    send_registration_email,
)
from apps.accounts.models import User, UserDevice
from apps.core.exceptions import BusinessRuleError
from apps.core.services.audit import audit

logger = logging.getLogger("apps.auth")


def issue_tokens(user: User) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


def register_device(
    user: User, device_name: str, ip: str, ua: str, refresh_token: str, notify: bool = True
) -> UserDevice:
    """Register a device session keyed by hashed refresh token.

    When a brand-new device row is created (and notifications are enabled) a
    security email is sent so the owner notices unknown sign-ins.
    """
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    device, created = UserDevice.objects.update_or_create(
        refresh_token_hash=token_hash,
        defaults={
            "user": user,
            "device_name": device_name,
            "ip_address": ip,
            "user_agent": ua,
            "last_seen_at": timezone.now(),
            "revoked_at": None,
        },
    )
    if created and notify:
        send_new_device_email(user, device_name, ip)
    return device


def _issue_session(user: User, device_name: str, ip: str, ua: str, notify: bool = True) -> dict:
    """Issue a token pair, register the device, and return the payload."""
    tokens = issue_tokens(user)
    register_device(user, device_name, ip, ua, tokens["refresh"], notify=notify)
    return {"user": serialize_user(user), "tokens": tokens}


# ---------------------------------------------------------------------------
# Google OAuth (Continue with Google) — primary customer auth
# ---------------------------------------------------------------------------
def google_identity_or_none(google_sub: str, email: str):
    """Return an existing user bound to the verified Google identity, or None."""
    user = None
    if google_sub:
        user = User.objects.filter(google_sub=google_sub).first()
    if user is None and email:
        user = User.objects.filter(email__iexact=email).first()
    return user


def google_auth(
    google_sub: str, email: str, full_name: str = "", device_name: str = "", ip: str = "", ua: str = ""
) -> dict:
    """Resolve a verified Google identity to a User (auto-creating on first login).

    Password creation is mandatory for every customer account, so this only
    resolves the identity — the caller decides whether to issue a session (for
    password setup) or require password verification.

    Returns ``{"user", "created"}`` — ``created`` is True for brand-new accounts
    that still need to set a password (``has_password`` is False).
    """
    user = google_identity_or_none(google_sub, email)
    created = False

    if user is None:
        user = User.objects.create_user(
            email=email or None,
            google_sub=google_sub or None,
            full_name=full_name,
            role="customer",
            is_verified=True,
        )
        User.ensure_referral_code(user)
        created = True
        audit(
            user_id=user.id,
            action="auth.google_signup",
            entity_type="user",
            entity_id=user.id,
            after={"email": email, "source": "google"},
            ip=ip,
            ua=ua,
        )
        logger.info("Customer account created via Google %s", email)
    elif not user.is_active:
        raise BusinessRuleError("This account has been disabled.", code="FORBIDDEN")

    updates: list[str] = ["last_login_at"]
    user.last_login_at = timezone.now()
    if google_sub and not user.google_sub:
        user.google_sub = google_sub
        updates.append("google_sub")
    if full_name and not user.full_name:
        user.full_name = full_name
        updates.append("full_name")
    user.save(update_fields=updates)

    logger.info("Google identity resolved for %s (created=%s)", email, created)
    return {"user": user, "created": created}


# ---------------------------------------------------------------------------
# Customer sign-in (email + password)
# ---------------------------------------------------------------------------
def login_customer_with_password(
    email: str, password: str, device_name: str = "", ip: str = "", ua: str = ""
) -> dict:
    """Authenticate a customer with a registered email + password."""
    user = User.objects.filter(email__iexact=email).first()
    if user is None or not user.check_password(password):
        raise BusinessRuleError("Invalid credentials.", code="AUTH_FAILED")

    if not user.is_active:
        raise BusinessRuleError("This account has been disabled.", code="FORBIDDEN")

    if not user.is_customer:
        raise BusinessRuleError("Use the admin sign-in for staff accounts.", code="FORBIDDEN")

    user.last_login_at = timezone.now()
    user.save(update_fields=["last_login_at"])
    logger.info("Customer signed in via password for %s", email)
    return _issue_session(user, device_name, ip, ua)


# ---------------------------------------------------------------------------
# Password management
# ---------------------------------------------------------------------------
def create_password(user: User, password: str) -> User:
    """Set the first password on an OAuth-created account (completes signup).

    The account is fully created (Google verified + password set) only after this
    succeeds, which is when the welcome/registration email is sent.
    """
    if user.has_usable_password():
        raise BusinessRuleError(
            "This account already has a password. Use 'Change password' instead.",
            code="PASSWORD_ALREADY_SET",
        )
    user.set_password(password)
    user.save(update_fields=["password"])
    audit(
        user_id=user.id,
        action="auth.password_created",
        entity_type="user",
        entity_id=user.id,
        ua="",
    )
    send_registration_email(user)
    send_password_created_email(user)
    logger.info("Password created for user %s", user.id)
    return user


def change_password(
    user: User, current_password: str, new_password: str, device_name: str = "", ip: str = "", ua: str = ""
) -> dict:
    """Change an existing password; revoke every session and re-issue a fresh
    one for the current device so the user stays signed in here only."""
    if not user.check_password(current_password):
        raise BusinessRuleError("The current password is incorrect.", code="AUTH_FAILED")

    user.set_password(new_password)
    user.save(update_fields=["password"])
    revoked = revoke_all_devices(user)
    audit(
        user_id=user.id,
        action="auth.password_changed",
        entity_type="user",
        entity_id=user.id,
        after={"devices_revoked": revoked},
        ip=ip,
        ua=ua,
    )
    send_password_changed_email(user)
    logger.info("Password changed for user %s (sessions revoked=%d)", user.id, revoked)
    return _issue_session(user, device_name, ip, ua, notify=False)


def send_password_reset_link(email: str) -> None:
    """Email a password-reset link for the account, without leaking existence."""
    user = User.objects.filter(email__iexact=email).first()
    if user is None or not user.is_active:
        logger.info("Password reset link requested for unregistered email %s", email)
        return

    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    reset_url = (
        f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?uid={uid}&token={token}"
    )
    send_password_reset_link_email(user, reset_url)
    audit(
        user_id=user.id,
        action="auth.password_reset_requested",
        entity_type="user",
        entity_id=user.id,
        ua="",
    )
    logger.info("Password reset link emailed to %s", email)


def reset_password_with_token(uid: str, token: str, new_password: str) -> User:
    """Redeem an emailed reset link: set the new password and revoke sessions."""
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist) as exc:
        raise BusinessRuleError(
            "This password reset link is invalid. Please request a new one.",
            code="RESET_TOKEN_INVALID",
        ) from exc

    if not default_token_generator.check_token(user, token):
        raise BusinessRuleError(
            "This password reset link is invalid or has expired. Please request a new one.",
            code="RESET_TOKEN_INVALID",
        )

    user.set_password(new_password)
    user.save(update_fields=["password"])
    revoked = revoke_all_devices(user)
    audit(
        user_id=user.id,
        action="auth.password_reset",
        entity_type="user",
        entity_id=user.id,
        after={"devices_revoked": revoked},
        ua="",
    )
    send_password_reset_done_email(user)
    logger.info("Password reset via link for user %s (sessions revoked=%d)", user.id, revoked)
    return user


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------
def revoke_device(user: User, token_hash: str) -> bool:
    """Revoke a single device session."""
    try:
        device = UserDevice.objects.get(refresh_token_hash=token_hash, user=user)
        device.revoked_at = timezone.now()
        device.save(update_fields=["revoked_at"])
        return True
    except UserDevice.DoesNotExist:
        return False


def revoke_all_devices(user: User) -> int:
    """Revoke every active device session for the user."""
    count = UserDevice.objects.filter(user=user, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )
    return count


def is_token_valid(refresh_token: str) -> bool:
    """Check whether a refresh token belongs to an active, non-revoked device."""
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    return UserDevice.objects.filter(
        refresh_token_hash=token_hash, revoked_at__isnull=True
    ).exists()


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "phone": user.phone,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "avatar_url": user.avatar_url,
        "referral_code": user.referral_code,
        "is_verified": user.is_verified,
        "has_password": user.has_usable_password(),
    }
