"""Admin dashboard models — cross-admin activity notifications.

The platform has exactly two staff users (super_admin + store_manager) that
share a single dashboard. Every catalog/inventory mutation is mirrored to the
*other* admin as a persisted notification so both see each other's work after
any logout/restart (single source of truth is the backend database).
"""
from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class AdminNotification(TimeStampedModel):
    """An activity performed by one admin, delivered to the other admin."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_notifications_acted",
    )
    action = models.CharField(max_length=40, db_index=True)
    entity_type = models.CharField(max_length=40, db_index=True)
    entity_id = models.CharField(max_length=60, blank=True)
    description = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.recipient} <- {self.action} {self.entity_type}"
