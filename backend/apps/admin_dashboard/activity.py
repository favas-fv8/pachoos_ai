"""Cross-admin activity recording + notifications.

Every admin mutation in the shared dashboard is:
  1. Persisted to the immutable AuditLog (traceability / RBAC),
  2. Mirrored to the *other* admin as an AdminNotification so each admin
     sees the other's product/category/stock/status changes after refresh.
"""
from apps.admin_dashboard.models import AdminNotification
from apps.core.services.audit import audit


def record_admin_activity(actor, action, entity_type, entity_id="", description="",
                          before=None, after=None, request=None):
    """Record an admin mutation to AuditLog + notify the other admin(s)."""
    ip = None
    ua = ""
    if request is not None:
        ip = getattr(request, "client_ip", None) or getattr(request, "META", {}).get("REMOTE_ADDR")
        ua = request.META.get("HTTP_USER_AGENT", "")

    audit(
        user_id=actor.id if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
        ip=ip,
        ua=ua,
    )

    if not actor:
        return

    from apps.accounts.models import STAFF_ROLES, User

    other_admins = User.objects.filter(
        role__in=STAFF_ROLES, is_active=True
    ).exclude(pk=actor.pk)
    for admin in other_admins:
        AdminNotification.objects.create(
            recipient=admin,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            description=description,
        )


def get_admin_notifications(user, limit: int = 50) -> dict:
    """Notifications addressed to `user` (i.e. the other admin's activity)."""
    qs = (
        AdminNotification.objects.filter(recipient=user)
        .select_related("actor")
        .order_by("-created_at")
    )
    unread_count = qs.filter(is_read=False).count()
    notifications = [
        {
            "id": str(n.id),
            "action": n.action,
            "entity_type": n.entity_type,
            "entity_id": n.entity_id,
            "description": n.description,
            "actor_name": n.actor.full_name if n.actor else "Admin",
            "actor_role": n.actor.role if n.actor else "",
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
        }
        for n in qs[:limit]
    ]
    return {"results": notifications, "unread_count": unread_count}


def mark_admin_notification_read(user, notification_id=None) -> int:
    """Mark one (or all, when id is None) notifications as read. Returns count."""
    qs = AdminNotification.objects.filter(recipient=user, is_read=False)
    if notification_id is not None:
        qs = qs.filter(id=notification_id)
    return qs.update(is_read=True)
