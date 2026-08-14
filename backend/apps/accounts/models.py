"""Identity models: User (2 admins + customers), Device sessions, audit/activity logs."""
import secrets

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from apps.accounts.managers import UserManager
from apps.core.models import TimeStampedModel, UUIDPrimaryKeyModel


class Role(models.TextChoices):
    SUPER_ADMIN = "super_admin", "Super Admin"
    STORE_MANAGER = "store_manager", "Store Manager"
    CUSTOMER = "customer", "Customer"


STAFF_ROLES = (Role.SUPER_ADMIN, Role.STORE_MANAGER)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    """Platform user.

    Exactly two staff users exist (one super_admin, one store_manager).
    Every other account is a customer.
    """

    phone = models.CharField(max_length=15, unique=True, null=True, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    full_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.CUSTOMER)

    # Staff binding: single primary shop (no per-shop staff accounts).
    shop = models.ForeignKey(
        "shops.Shop", on_delete=models.PROTECT, null=True, blank=True,
        related_name="staff",
    )

    google_sub = models.CharField(max_length=255, unique=True, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    avatar_url = models.URLField(blank=True)

    # Session metadata
    last_login_at = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_login_ua = models.TextField(blank=True)

    # Referral
    referral_code = models.CharField(max_length=12, unique=True, null=True, blank=True)
    referred_by = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="referrals",
    )

    # Django admin flags (super_admin doubles as superuser for the admin site)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["phone"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        return self.full_name or self.phone or self.email or f"User {self.pk}"

    @property
    def is_staff_user(self) -> bool:
        return self.role in STAFF_ROLES

    @property
    def is_customer(self) -> bool:
        return self.role == Role.CUSTOMER

    @classmethod
    def ensure_referral_code(cls, user: "User") -> str:
        if not user.referral_code:
            user.referral_code = "PACH-" + secrets.token_hex(3).upper()
            user.save(update_fields=["referral_code"])
        return user.referral_code

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = "PACH-" + secrets.token_hex(3).upper()
        if self.email:
            self.email = self.email.lower()
        super().save(*args, **kwargs)


class UserDevice(TimeStampedModel):
    """A trusted login session bound to one refresh token."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="devices")
    refresh_token_hash = models.CharField(max_length=64, unique=True)
    device_name = models.CharField(max_length=120, blank=True)
    platform = models.CharField(max_length=60, blank=True)
    browser = models.CharField(max_length=60, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "revoked_at"])]

    def __str__(self):
        return f"{self.user} · {self.device_name or 'device'}"


class AuditLog(UUIDPrimaryKeyModel, TimeStampedModel):
    """Immutable record of admin mutations (OWASP A09 / RBAC traceability)."""

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                             related_name="audit_logs")
    action = models.CharField(max_length=100, db_index=True)
    entity_type = models.CharField(max_length=60, db_index=True)
    entity_id = models.CharField(max_length=60, db_index=True, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.action} {self.entity_type}:{self.entity_id}"


class ActivityLog(UUIDPrimaryKeyModel, TimeStampedModel):
    """Customer-facing history (login, order placed, wallet earned, ...)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="activities")
    activity_type = models.CharField(max_length=60, db_index=True)
    description = models.CharField(max_length=255)
    ref_order_id = models.BigIntegerField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self):
        return f"{self.user} · {self.activity_type}"
