"""Audit logging — immutable, tamper-evident record of admin mutations."""
import json
import logging

from django.core.exceptions import ImproperlyConfigured

audit_logger = logging.getLogger("apps.audit")


def audit(user_id, action, entity_type, entity_id, before=None, after=None,
          ip=None, ua=None):
    """Append an audit log entry.

    For DB-backed persistence the model lives in apps.accounts.models.AuditLog;
    this helper is the single call-site used by services so the shape stays
    consistent and easy to replace with a streaming sink later.
    """
    # Inline import avoids a hard dependency cycle at app-load time.
    try:
        from apps.accounts.models import AuditLog
    except (ImportError, ImproperlyConfigured):
        audit_logger.warning("AuditLog unavailable; skipping persist.")
        return None

    return AuditLog.objects.create(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else "",
        before=_serializable(before),
        after=_serializable(after),
        ip=ip,
        user_agent=ua,
    )


def _serializable(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        try:
            json.dumps(value)
            return value
        except TypeError:
            pass
    return json.loads(json.dumps(value, default=str))
