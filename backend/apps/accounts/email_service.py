"""Transactional email service for account lifecycle + password security.

Every notification goes through :func:`send_transactional_email`, which renders
a shared HTML shell and a plain-text fallback, then sends via Django's
configured ``EMAIL_BACKEND`` (console in dev, SMTP/SES/… in prod). Email
delivery is best-effort: failures are logged, never raised to the caller.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger("apps.email")


def send_transactional_email(
    email: str,
    subject: str,
    paragraphs: list[str],
    *,
    action_url: str | None = None,
    action_text: str | None = None,
    note: str | None = None,
) -> None:
    """Render and send one transactional email."""
    if not email:
        return
    context = {
        "brand": "PACHOOS",
        "subject": subject,
        "paragraphs": paragraphs,
        "action_url": action_url,
        "action_text": action_text,
        "note": note,
    }
    html = render_to_string("accounts/email/base.html", context)
    text = render_to_string("accounts/email/plain.txt", context)
    message = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [email])
    message.attach_alternative(html, "text/html")
    try:
        message.send(fail_silently=False)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to send email to %s (%s)", email, exc)


def _security_note() -> str:
    return "If this wasn't you, reset your password immediately at " + settings.FRONTEND_URL + "/forgot-password"


def send_registration_email(user) -> None:
    """Welcome email sent once account setup completes (Google verified + password).

    Confirms the account was created and is now active, and includes the account
    creation date/time. Never includes the password or other sensitive data.
    """
    subject = "Welcome to PACHOOS"
    created_at = timezone.localtime(user.created_at) if user.created_at else timezone.localtime()
    created_label = created_at.strftime("%d %B %Y at %I:%M %p")
    paragraphs = [
        f"Hi {user.full_name or 'there'},",
        "Your PACHOOS account was created successfully and is now active.",
        f"Account created: {created_label}.",
        "You can sign in with your email and password, or continue with Google, and "
        "start exploring fresh bakery and fruit deliveries from your shop.",
    ]
    send_transactional_email(user.email, subject, paragraphs, action_url=settings.FRONTEND_URL, action_text="Go to PACHOOS")


def send_password_created_email(user) -> None:
    """Confirmation after a user sets their first password."""
    subject = "Your PACHOOS password has been created"
    paragraphs = [
        f"Hi {user.full_name or 'there'},",
        "A password has been set for your PACHOOS account. You can now sign in with your "
        "email and password, or keep using Google.",
    ]
    send_transactional_email(user.email, subject, paragraphs, note=_security_note())


def send_password_changed_email(user) -> None:
    """Confirmation after a user changes their password (all sessions revoked)."""
    subject = "Your PACHOOS password was changed"
    paragraphs = [
        f"Hi {user.full_name or 'there'},",
        "Your PACHOOS password was changed. For your security, all existing sessions "
        "have been signed out — please sign in again with your new password.",
    ]
    send_transactional_email(user.email, subject, paragraphs, note=_security_note())


def send_password_reset_link_email(user, reset_url: str) -> None:
    """Emailed password-reset link (Forgot Password flow)."""
    subject = "Reset your PACHOOS password"
    paragraphs = [
        f"Hi {user.full_name or 'there'},",
        "We received a request to reset your PACHOOS password. Click the button below "
        "to choose a new password. The link expires after 24 hours.",
    ]
    send_transactional_email(
        user.email,
        subject,
        paragraphs,
        action_url=reset_url,
        action_text="Reset password",
        note=_security_note(),
    )


def send_password_reset_done_email(user) -> None:
    """Confirmation after a reset link is redeemed."""
    subject = "Your PACHOOS password was reset"
    paragraphs = [
        f"Hi {user.full_name or 'there'},",
        "Your PACHOOS password was reset successfully. All existing sessions have been "
        "signed out — sign in again with your new password.",
    ]
    send_transactional_email(user.email, subject, paragraphs, note=_security_note())


def send_new_device_email(user, device_name: str, ip: str) -> None:
    """Security notice when a new device signs in to the account."""
    subject = "New sign-in to your PACHOOS account"
    paragraphs = [
        f"Hi {user.full_name or 'there'},",
        "We noticed a sign-in from a new device:",
        f"Device: {device_name or 'Unknown'}  |  IP: {ip or 'Unknown'}",
        "If this was you, no action is needed. Otherwise your account may be at risk.",
    ]
    send_transactional_email(user.email, subject, paragraphs, note=_security_note())
