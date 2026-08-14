"""Base model mixins used across the platform."""
import uuid

from django.db import models


class TimeStampedModel(models.Model):
    """Adds created_at / updated_at to every inheriting model."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDPrimaryKeyModel(models.Model):
    """UUID PK for externally-visible entities (avoids enumeration)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """Opt-in soft delete: rows are hidden but preserved for ledger integrity."""

    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
