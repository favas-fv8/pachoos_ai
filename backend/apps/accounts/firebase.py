"""Firebase Auth verification service (Google identity).

The Firebase Admin SDK validates ID tokens issued by Firebase Authentication
(Google sign-in). There is no sandbox path — the service account must be
configured or verification fails loudly.

Credentials are read entirely from environment variables — never hard-coded:
    FIREBASE_CREDENTIALS_PATH   path to a service-account JSON file
    FIREBASE_CREDENTIALS        inline service-account JSON (mutually
                                exclusive with the path above)
    FIREBASE_PROJECT_ID         Firebase project identifier

Verification never bypasses Google: a token must pass the Admin SDK's
cryptographic signature/issuer/audience/expiry checks to be accepted. Failures
are classified so the API can give a safe, retryable message (transient
upstream certificate fetch vs. genuinely invalid/expired tokens) while the
underlying Google error is only ever logged server-side.
"""
import json
import logging
import time
from pathlib import Path

from django.conf import settings

from apps.core.exceptions import BusinessRuleError

logger = logging.getLogger("apps.auth")

_app = None

# The Firebase Admin SDK rejects ID tokens whose ``iat``/``exp`` deviate more
# than this from the server clock. Google's own limit is 0–60s; 60s tolerates
# small clock drift on the server or client without weakening verification.
CLOCK_SKEW_SECONDS = 60

# Retry transient certificate-fetch failures. The Admin SDK must download
# Google's public signing keys over the network on the first verification
# (and on key rotation); brief outages used to surface as spurious
# "Verification failed" for otherwise-valid Google sign-ins.
VERIFY_RETRIES = 2


def _credential():
    """Return the service-account credential (path or dict) from settings."""
    credentials_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", "")
    if credentials_path and Path(credentials_path).exists():
        return credentials_path
    inline = getattr(settings, "FIREBASE_CREDENTIALS", "")
    if inline:
        return json.loads(inline)
    return None


def get_app():
    """Return the lazily-initialised Firebase app for the configured project."""
    global _app
    if _app is not None:
        return _app

    if not getattr(settings, "FIREBASE_PROJECT_ID", ""):
        raise RuntimeError(
            "FIREBASE_PROJECT_ID is not set. Firebase Auth requires the service "
            "account to verify ID tokens."
        )

    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError as exc:  # pragma: no cover - guarded by requirements
        raise RuntimeError("firebase-admin is required when FIREBASE_PROJECT_ID is set.") from exc

    credential = _credential()
    if credential is None:
        raise RuntimeError(
            "Firebase service-account credentials are not configured. Set "
            "FIREBASE_CREDENTIALS_PATH or FIREBASE_CREDENTIALS."
        )

    _app = firebase_admin.initialize_app(
        credential=credentials.Certificate(credential),
        options={"name": "pachoos"},
    )
    logger.info("Firebase Admin SDK initialised for project %s", settings.FIREBASE_PROJECT_ID)
    return _app


def _verify_once(id_token: str) -> dict:
    """Verify one ID token against Google's Firebase Admin SDK."""
    from firebase_admin import auth

    return auth.verify_id_token(
        id_token,
        app=get_app(),
        clock_skew_seconds=CLOCK_SKEW_SECONDS,
    )


def verify_id_token(id_token: str) -> dict:
    """Verify a Firebase ID token and return its decoded claims.

    Only tokens that pass the Admin SDK's signature/issuer/audience/expiry
    checks are accepted — Google identities are never taken on trust.

    Errors are classified so the caller can distinguish a transient upstream
    failure (certificate/key fetch over the network) from a genuinely invalid
    or expired token, and the server log records the concrete cause while the
    client only ever receives a safe, human-readable message.

    Raises ``BusinessRuleError`` (``AUTH_FAILED`` for invalid/expired tokens,
    ``AUTH_SERVICE_UNAVAILABLE`` for transient Google-side failures).
    """
    if not id_token:
        raise BusinessRuleError("Verification token is required.", code="VALIDATION_ERROR")

    # Import here so environments without firebase_admin only pay for it on
    # the first real request, and so tests can monkeypatch the module.
    from firebase_admin._token_gen import CertificateFetchError
    from firebase_admin.auth import InvalidIdTokenError

    last_error: Exception | None = None
    for attempt in range(VERIFY_RETRIES):
        try:
            return _verify_once(id_token)
        except BusinessRuleError:
            raise
        except InvalidIdTokenError as exc:
            # Token is genuinely invalid, expired, or was malformed — a
            # fresh Google sign-in is required; a retry cannot help.
            logger.warning("Firebase ID token rejected (%s): %s", type(exc).__name__, exc)
            raise BusinessRuleError(
                "Google sign-in could not be completed. Please complete the Google sign-in again.",
                code="AUTH_FAILED",
            ) from exc
        except CertificateFetchError as exc:
            # Google's public-key endpoint was unreachable — usually transient.
            last_error = exc
            logger.warning(
                "Firebase certificate fetch failed (attempt %d/%d): %s",
                attempt + 1,
                VERIFY_RETRIES,
                exc,
            )
            if attempt + 1 < VERIFY_RETRIES:
                time.sleep(2.5)
                continue
        except Exception as exc:  # noqa: BLE001
            logger.exception("Firebase token verification failed: %s", exc)
            raise BusinessRuleError(
                "Verification failed. Please complete the Google sign-in again.",
                code="AUTH_FAILED",
            ) from exc

    # All retries exhausted on a transient failure.
    logger.warning("Firebase verification unavailable after %d attempts", VERIFY_RETRIES)
    raise BusinessRuleError(
        "Google sign-in verification is temporarily unavailable. Please try again.",
        code="AUTH_SERVICE_UNAVAILABLE",
    ) from last_error
