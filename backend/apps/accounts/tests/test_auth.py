"""Tests for the PACHOOS authentication module.

Covers Google OAuth (create-if-not-exists primary auth), email+password login,
password create/change/forgot/reset (link-based, no OTPs), session invalidation,
admin sign-in, strong-password policy, and regressions for the existing auth
architecture (JWT refresh, me, device security emails).
"""

import re

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts import firebase

User = get_user_model()

GOOGLE_EMAIL = "sandeep@gmail.com"
GOOGLE_SUB = "google-sub-123"
PASSWORD = "StrongPass1!"
NEW_PASSWORD = "NewStrongPass1!"

GOOGLE_URL = "/api/v1/auth/google/"
LOGIN_URL = "/api/v1/auth/customer/login/"
CREATE_URL = "/api/v1/auth/password/create/"
CHANGE_URL = "/api/v1/auth/password/change/"
FORGOT_URL = "/api/v1/auth/password/forgot/"
RESET_URL = "/api/v1/auth/password/reset/"
ADMIN_LOGIN_URL = "/api/v1/auth/admin/login/"
ME_URL = "/api/v1/auth/me/"


@pytest.fixture
def api():
    return APIClient()


def _google_claims(**overrides):
    claims = {
        "sub": GOOGLE_SUB,
        "email": GOOGLE_EMAIL,
        "name": "Sandeep",
        "iss": "https://securetoken.google.com/project",
        "aud": "project",
        "exp": 9999999999,
    }
    claims.update(overrides)
    return claims


@pytest.fixture
def mock_firebase(monkeypatch):
    """Route Firebase verification through a controllable claim set (or error)."""

    def _set(claims=None, error=None):
        def _verify(token):
            if error is not None:
                raise error
            return claims

        monkeypatch.setattr(firebase, "verify_id_token", _verify)

    return _set


def _customer(email=GOOGLE_EMAIL, password=None, google_sub=GOOGLE_SUB):
    return User.objects.create_user(
        phone=None,
        email=email,
        google_sub=google_sub,
        full_name="Sandeep",
        role="customer",
        password=password,
    )


def _extract_reset_token():
    """Pull uid+token out of the last reset-link email body."""
    body = mail.outbox[-1].body
    match = re.search(r"reset-password\?uid=([^&\s]+)&token=([^&\s]+)", body)
    assert match, f"reset link not found in email body: {body!r}"
    return match.group(1), match.group(2)


# ---------------------------------------------------------------------------
# Continue with Google — primary auth (create-if-not-exists)
# ---------------------------------------------------------------------------
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@pytest.mark.django_db
def test_google_first_login_creates_account(api, mock_firebase):
    mock_firebase(_google_claims())
    resp = api.post(GOOGLE_URL, {"token": "firebase-id-token", "device_name": "test"}, format="json")

    assert resp.status_code == 200
    assert resp.data["access"]
    assert resp.data["refresh"]
    assert resp.data["password_required"] is True
    assert resp.data["user"]["email"] == GOOGLE_EMAIL
    assert resp.data["user"]["role"] == "customer"
    assert resp.data["user"]["has_password"] is False
    assert User.objects.filter(email=GOOGLE_EMAIL, google_sub=GOOGLE_SUB).exists()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@pytest.mark.django_db
def test_welcome_email_sent_only_after_password_creation(api, mock_firebase):
    mock_firebase(_google_claims())
    api.post(GOOGLE_URL, {"token": "t"}, format="json")
    # Account is not complete until a password is created → no welcome email yet.
    assert "Welcome to PACHOOS" not in {m.subject for m in mail.outbox}

    user = User.objects.get(email=GOOGLE_EMAIL)
    api.force_authenticate(user=user)
    api.post(CREATE_URL, {"password": PASSWORD}, format="json")
    assert "Welcome to PACHOOS" in {m.subject for m in mail.outbox}


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@pytest.mark.django_db
def test_welcome_email_confirms_creation_datetime_and_no_password(api, mock_firebase):
    mock_firebase(_google_claims())
    api.post(GOOGLE_URL, {"token": "t"}, format="json")
    user = User.objects.get(email=GOOGLE_EMAIL)
    api.force_authenticate(user=user)
    api.post(CREATE_URL, {"password": PASSWORD}, format="json")

    welcome = next(m for m in mail.outbox if m.subject == "Welcome to PACHOOS")
    assert "created successfully" in welcome.body.lower()
    # The account creation date/time is included (e.g. "07 August 2026 at 05:30 PM").
    assert re.search(r"\d{2} [A-Z][a-z]+ \d{4} at \d{2}:\d{2}", welcome.body)
    # The password is never included in the email.
    assert PASSWORD not in f"{welcome.subject}\n{welcome.body}"


@pytest.mark.django_db
def test_google_existing_user_requires_password(api, mock_firebase):
    _customer(password=PASSWORD)
    mock_firebase(_google_claims())

    resp = api.post(GOOGLE_URL, {"token": "firebase-id-token"}, format="json")
    assert resp.status_code == 200
    assert resp.data["password_challenge"] is True
    assert resp.data["email"] == GOOGLE_EMAIL
    assert "access" not in resp.data

    # Password verification (existing customer login endpoint) completes sign-in.
    login = api.post(LOGIN_URL, {"email": GOOGLE_EMAIL, "password": PASSWORD}, format="json")
    assert login.status_code == 200
    assert login.data["access"]
    assert login.data["user"]["has_password"] is True


@pytest.mark.django_db
def test_google_existing_account_without_password_gets_password_setup(api, mock_firebase):
    """An account that never completed password setup must still create one."""
    _customer(password=None)
    mock_firebase(_google_claims())

    resp = api.post(GOOGLE_URL, {"token": "t"}, format="json")
    assert resp.status_code == 200
    assert resp.data["password_required"] is True
    assert resp.data["access"]
    assert resp.data["user"]["has_password"] is False


@pytest.mark.django_db
def test_google_links_sub_on_signin(api, mock_firebase):
    """User shares the Google email but has no google_sub yet → linked on sign-in."""
    user = _customer(password=PASSWORD, google_sub=None)
    mock_firebase(_google_claims())

    resp = api.post(GOOGLE_URL, {"token": "firebase-id-token"}, format="json")
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.google_sub == GOOGLE_SUB


@pytest.mark.django_db
def test_google_requires_email_claim(api, mock_firebase):
    mock_firebase(_google_claims(email=None))
    resp = api.post(GOOGLE_URL, {"token": "t"}, format="json")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "AUTH_FAILED"


@pytest.mark.django_db
def test_google_rejects_missing_token(api):
    resp = api.post(GOOGLE_URL, {}, format="json")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_google_rejects_bad_token(api, mock_firebase):
    from apps.core.exceptions import BusinessRuleError

    mock_firebase(error=BusinessRuleError("Verification failed.", code="AUTH_FAILED"))
    resp = api.post(GOOGLE_URL, {"token": "not-a-real-token"}, format="json")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "AUTH_FAILED"


# ---------------------------------------------------------------------------
# Customer Sign In — email + password
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_login_email_password_after_google(api, mock_firebase):
    mock_firebase(_google_claims())
    api.post(GOOGLE_URL, {"token": "t"}, format="json")
    user = User.objects.get(email=GOOGLE_EMAIL)
    user.set_password(PASSWORD)
    user.save(update_fields=["password"])

    resp = api.post(LOGIN_URL, {"email": GOOGLE_EMAIL, "password": PASSWORD}, format="json")
    assert resp.status_code == 200
    assert resp.data["access"]
    assert resp.data["user"]["email"] == GOOGLE_EMAIL
    assert resp.data["user"]["role"] == "customer"


@pytest.mark.django_db
def test_login_rejects_wrong_password(api):
    _customer(password=PASSWORD)
    resp = api.post(LOGIN_URL, {"email": GOOGLE_EMAIL, "password": "WrongPass1!"}, format="json")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "AUTH_FAILED"


@pytest.mark.django_db
def test_login_rejects_admin_via_customer_endpoint(api, admin_user):
    resp = api.post(
        LOGIN_URL,
        {"email": "admin@pachoos.com", "password": "adminpass123"},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "FORBIDDEN"


@pytest.mark.django_db
def test_login_unknown_account(api):
    resp = api.post(LOGIN_URL, {"email": "nobody@gmail.com", "password": PASSWORD}, format="json")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "AUTH_FAILED"


# ---------------------------------------------------------------------------
# Create password (Google first-login completion)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_create_password_sets_first_password(api):
    user = _customer()
    api.force_authenticate(user=user)

    resp = api.post(CREATE_URL, {"password": PASSWORD}, format="json")
    assert resp.status_code == 200
    assert resp.data["has_password"] is True
    user.refresh_from_db()
    assert user.has_usable_password()
    assert user.check_password(PASSWORD)


@pytest.mark.django_db
def test_create_password_requires_auth(api):
    assert api.post(CREATE_URL, {"password": PASSWORD}, format="json").status_code == 401


@pytest.mark.django_db
def test_create_password_already_set(api):
    user = _customer(password=PASSWORD)
    api.force_authenticate(user=user)
    resp = api.post(CREATE_URL, {"password": NEW_PASSWORD}, format="json")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "PASSWORD_ALREADY_SET"


@pytest.mark.parametrize(
    "weak_password",
    ["short", "ALLUPPERCASE1!", "alllowercase1!", "NoSpecialChar1", "NoNumbers!", " 12345678A! "],
)
@pytest.mark.django_db
def test_create_password_rejects_weak_passwords(api, weak_password):
    user = _customer()
    api.force_authenticate(user=user)
    resp = api.post(CREATE_URL, {"password": weak_password}, format="json")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Change password (current password required, sessions revoked)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_change_password_requires_current_password(api):
    user = _customer(password=PASSWORD)
    api.force_authenticate(user=user)

    resp = api.post(CHANGE_URL, {"current_password": "WrongPass1!", "new_password": NEW_PASSWORD}, format="json")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "AUTH_FAILED"


@pytest.mark.django_db
def test_change_password_revokes_other_sessions(api):
    _customer(password=PASSWORD)

    login = api.post(LOGIN_URL, {"email": GOOGLE_EMAIL, "password": PASSWORD}, format="json")
    old_refresh = login.data["refresh"]
    assert old_refresh

    user = User.objects.get(email=GOOGLE_EMAIL)
    api.force_authenticate(user=user)
    resp = api.post(
        CHANGE_URL,
        {"current_password": PASSWORD, "new_password": NEW_PASSWORD, "device_name": "test"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["access"]
    assert resp.data["refresh"] != old_refresh
    assert resp.data["user"]["has_password"] is True

    # The pre-change session is revoked.
    revoked = api.post("/api/v1/auth/token/refresh/", {"refresh": old_refresh}, format="json")
    assert revoked.status_code == 400
    assert revoked.data["error"]["code"] == "AUTH_FAILED"

    # Old password fails, new one works.
    assert api.post(LOGIN_URL, {"email": GOOGLE_EMAIL, "password": PASSWORD}, format="json").status_code == 400
    assert api.post(LOGIN_URL, {"email": GOOGLE_EMAIL, "password": NEW_PASSWORD}, format="json").status_code == 200


# ---------------------------------------------------------------------------
# Forgot password — emailed reset link
# ---------------------------------------------------------------------------
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@pytest.mark.django_db
def test_forgot_password_sends_link(api):
    _customer(password=PASSWORD)

    resp = api.post(FORGOT_URL, {"email": GOOGLE_EMAIL}, format="json")
    assert resp.status_code == 200
    assert len(mail.outbox) == 1
    assert "Reset your PACHOOS password" == mail.outbox[0].subject
    assert "reset-password?uid=" in mail.outbox[0].body


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@pytest.mark.django_db
def test_forgot_password_does_not_leak_unknown_email(api):
    resp = api.post(FORGOT_URL, {"email": "nobody@gmail.com"}, format="json")
    assert resp.status_code == 200
    assert mail.outbox == []


@pytest.mark.django_db
def test_forgot_password_rejects_bad_email(api):
    resp = api.post(FORGOT_URL, {"email": "not-an-email"}, format="json")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Reset password — redeem emailed link
# ---------------------------------------------------------------------------
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@pytest.mark.django_db
def test_reset_password_via_link(api):
    _customer(password=PASSWORD)
    login = api.post(LOGIN_URL, {"email": GOOGLE_EMAIL, "password": PASSWORD}, format="json")
    old_refresh = login.data["refresh"]

    api.post(FORGOT_URL, {"email": GOOGLE_EMAIL}, format="json")
    uid, token = _extract_reset_token()

    resp = api.post(RESET_URL, {"uid": uid, "token": token, "new_password": NEW_PASSWORD}, format="json")
    assert resp.status_code == 200

    # Old session revoked, old password dead, new password works.
    revoked = api.post("/api/v1/auth/token/refresh/", {"refresh": old_refresh}, format="json")
    assert revoked.status_code == 400
    assert api.post(LOGIN_URL, {"email": GOOGLE_EMAIL, "password": PASSWORD}, format="json").status_code == 400
    assert api.post(LOGIN_URL, {"email": GOOGLE_EMAIL, "password": NEW_PASSWORD}, format="json").status_code == 200


@pytest.mark.django_db
def test_reset_password_invalid_token(api):
    _customer(password=PASSWORD)
    resp = api.post(RESET_URL, {"uid": "AA", "token": "bogus", "new_password": NEW_PASSWORD}, format="json")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "RESET_TOKEN_INVALID"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@pytest.mark.django_db
def test_reset_password_rejects_weak_password(api):
    _customer(password=PASSWORD)
    api.post(FORGOT_URL, {"email": GOOGLE_EMAIL}, format="json")
    uid, token = _extract_reset_token()

    resp = api.post(RESET_URL, {"uid": uid, "token": token, "new_password": "weak"}, format="json")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "VALIDATION_ERROR"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@pytest.mark.django_db
def test_reset_password_admin_via_link(api, admin_user):
    """Admin accounts use the same emailed-link reset flow."""
    assert api.post(FORGOT_URL, {"email": "admin@pachoos.com"}, format="json").status_code == 200
    uid, token = _extract_reset_token()

    resp = api.post(
        RESET_URL,
        {"uid": uid, "token": token, "new_password": NEW_PASSWORD},
        format="json",
    )
    assert resp.status_code == 200

    admin_resp = api.post(
        ADMIN_LOGIN_URL,
        {"email": "admin@pachoos.com", "password": NEW_PASSWORD},
        format="json",
    )
    assert admin_resp.status_code == 200


# ---------------------------------------------------------------------------
# Security emails
# ---------------------------------------------------------------------------
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@pytest.mark.django_db
def test_login_new_device_sends_security_email(api):
    _customer(password=PASSWORD)
    resp = api.post(LOGIN_URL, {"email": GOOGLE_EMAIL, "password": PASSWORD}, format="json")
    assert resp.status_code == 200
    assert mail.outbox
    assert "New sign-in to your PACHOOS account" in {m.subject for m in mail.outbox}


# ---------------------------------------------------------------------------
# Admin sign in (regression — must keep working, no self-registration)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_admin_login_still_works(api, admin_user):
    resp = api.post(
        ADMIN_LOGIN_URL,
        {"email": "admin@pachoos.com", "password": "adminpass123"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["access"]
    assert resp.data["user"]["role"] == "super_admin"


@pytest.mark.django_db
def test_admin_login_rejects_bad_credentials(api, admin_user):
    resp = api.post(
        ADMIN_LOGIN_URL,
        {"email": "admin@pachoos.com", "password": "wrong"},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "AUTH_FAILED"


@pytest.mark.django_db
def test_admin_login_rejects_customer(api, user):
    resp = api.post(
        ADMIN_LOGIN_URL,
        {"email": "test@pachoos.com", "password": "testpass123"},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# Google verification failure handling — transient vs. genuinely invalid
# ---------------------------------------------------------------------------
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@pytest.mark.django_db
def test_google_verification_transient_failure_is_retryable_and_no_account_created(
    api, mock_firebase
):
    """A transient Google-side verification failure must surface a clean,
    retryable code without creating any (partial) customer account."""
    from apps.core.exceptions import BusinessRuleError

    mock_firebase(error=BusinessRuleError("boom", code="AUTH_SERVICE_UNAVAILABLE"))
    resp = api.post(GOOGLE_URL, {"token": "firebase-id-token"}, format="json")

    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "AUTH_SERVICE_UNAVAILABLE"
    assert not User.objects.filter(email=GOOGLE_EMAIL).exists()
    assert not User.objects.filter(google_sub=GOOGLE_SUB).exists()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@pytest.mark.django_db
def test_google_verification_invalid_token_never_builds_account(api, mock_firebase):
    """A genuinely invalid/expired Google token is rejected without side effects."""
    from apps.core.exceptions import BusinessRuleError

    mock_firebase(error=BusinessRuleError("…", code="AUTH_FAILED"))
    resp = api.post(GOOGLE_URL, {"token": "forged-token"}, format="json")

    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "AUTH_FAILED"
    assert not User.objects.filter(email=GOOGLE_EMAIL).exists()


def test_firebase_verify_classifies_transient_certificate_failure(monkeypatch):
    """CertificateFetchError (Google key endpoint unreachable) → AUTH_SERVICE_UNAVAILABLE."""
    from firebase_admin._token_gen import CertificateFetchError

    import apps.accounts.firebase as firebase_mod

    monkeypatch.setattr(firebase_mod, "VERIFY_RETRIES", 1)

    def _boom(id_token):
        raise CertificateFetchError("boom", None)

    monkeypatch.setattr(firebase_mod, "_verify_once", _boom)
    from apps.core.exceptions import BusinessRuleError

    with pytest.raises(BusinessRuleError) as exc_info:
        firebase_mod.verify_id_token("some-token")
    assert exc_info.value.code == "AUTH_SERVICE_UNAVAILABLE"


def test_firebase_verify_classifies_invalid_token(monkeypatch):
    """Expired/revoked/malformed tokens must map to AUTH_FAILED, never accepted."""
    from firebase_admin.auth import InvalidIdTokenError

    import apps.accounts.firebase as firebase_mod

    def _boom(id_token):
        raise InvalidIdTokenError("signature verification failed")

    monkeypatch.setattr(firebase_mod, "_verify_once", _boom)
    from apps.core.exceptions import BusinessRuleError

    with pytest.raises(BusinessRuleError) as exc_info:
        firebase_mod.verify_id_token("some-token")
    assert exc_info.value.code == "AUTH_FAILED"


# ---------------------------------------------------------------------------
# Email delivery — content, multipart HTML/plain, brand, account timestamp
# ---------------------------------------------------------------------------
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@pytest.mark.django_db
def test_welcome_email_is_multipart_with_html_and_branding():
    from apps.accounts.email_service import send_registration_email

    user = _customer()
    send_registration_email(user)

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.subject == "Welcome to PACHOOS"
    assert msg.to == [GOOGLE_EMAIL]
    # Contains a text/plain body and a text/html alternate (responsive template).
    html = next(c[0] for c in msg.alternatives if c[1] == "text/html")
    assert "PACHOOS" in html
    assert "Bakery" in html
    assert "<table" in html or "max-width" in html
    assert "created successfully" in msg.body.lower()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@pytest.mark.django_db
def test_reset_and_reset_no_done_notifications_are_sent(api):
    """Forgot-password link email + password-changed notification both go out."""
    _customer(password=PASSWORD)
    api.post(FORGOT_URL, {"email": GOOGLE_EMAIL}, format="json")
    assert "Reset your PACHOOS password" in {m.subject for m in mail.outbox}

    uid, token = _extract_reset_token()
    api.post(RESET_URL, {"uid": uid, "token": token, "new_password": NEW_PASSWORD}, format="json")
    assert "Your PACHOOS password was reset" in {m.subject for m in mail.outbox}


# ---------------------------------------------------------------------------
# Regressions — existing auth infrastructure
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_token_refresh_still_works(api, user):
    from rest_framework_simplejwt.tokens import RefreshToken

    from apps.accounts.auth_service import register_device

    token = RefreshToken.for_user(user)
    register_device(user, "test", "127.0.0.1", "pytest", str(token), notify=False)
    resp = api.post("/api/v1/auth/token/refresh/", {"refresh": str(token)}, format="json")
    assert resp.status_code == 200
    assert resp.data["access"]


@pytest.mark.django_db
def test_me_requires_auth(api):
    assert api.get(ME_URL).status_code == 401
