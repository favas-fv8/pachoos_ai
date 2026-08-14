"""Auth serializers — Google auth, email+password sign-in, password
create/change/forgot/reset. No OTPs; recovery uses emailed reset links."""
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

User = get_user_model()

# Strong password policy: 8+ chars, upper, lower, digit, special character.
PASSWORD_MIN_LENGTH = 8
_SPECIAL_RE = re.compile(r"[^A-Za-z0-9]")
EMAIL_RE = r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"


def validate_password_strength(password: str) -> None:
    """Enforce the PACHOOS strong-password policy."""
    checks = [
        (len(password) >= PASSWORD_MIN_LENGTH, f"At least {PASSWORD_MIN_LENGTH} characters."),
        (re.search(r"[A-Z]", password), "At least one uppercase letter."),
        (re.search(r"[a-z]", password), "At least one lowercase letter."),
        (re.search(r"\d", password), "At least one number."),
        (_SPECIAL_RE.search(password), "At least one special character."),
    ]
    errors = [msg for ok, msg in checks if not ok]
    if errors:
        raise serializers.ValidationError(" ".join(errors))

    try:
        validate_password(password)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(" ".join(exc.messages)) from exc


class _PasswordValidatorMixin:
    """Serializer mixin enforcing the strong-password policy on new passwords."""

    def validate_password(self, value):
        validate_password_strength(value)
        return value

    def validate_new_password(self, value):
        validate_password_strength(value)
        return value


class CustomerLoginSerializer(serializers.Serializer):
    """Customer sign-in via registered email + password."""

    email = serializers.EmailField()
    password = serializers.CharField()
    device_name = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")


class CreatePasswordSerializer(_PasswordValidatorMixin, serializers.Serializer):
    """Set the first password on an OAuth-created account (Google first login)."""

    password = serializers.CharField()


class ChangePasswordSerializer(_PasswordValidatorMixin, serializers.Serializer):
    """Change an existing password; requires the current password."""

    current_password = serializers.CharField()
    new_password = serializers.CharField()
    device_name = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")


class ForgotPasswordSerializer(serializers.Serializer):
    """Request a password-reset link by email."""

    email = serializers.EmailField()


class ResetPasswordSerializer(_PasswordValidatorMixin, serializers.Serializer):
    """Confirm a password reset with the emailed uid + token."""

    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField()
