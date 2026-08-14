"""Health check endpoint — DB + cache reachability, version info."""

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.core.services.cache import cache_ping


@require_GET
@never_cache
def health(request):
    checks = {"status": "ok", "checks": {}}
    overall = 200

    # Database
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["checks"]["database"] = "ok"
    except Exception:
        checks["checks"]["database"] = "error"
        overall = 503

    # Redis cache
    try:
        cache_ping()
        checks["checks"]["cache"] = "ok"
    except Exception:
        checks["checks"]["cache"] = "unavailable"
        overall = 503

    checks["status"] = "ok" if overall == 200 else "degraded"
    checks["version"] = getattr(settings, "API_VERSION", "1.0.0")
    checks["environment"] = getattr(settings, "DJANGO_ENV", "dev")

    return JsonResponse(checks, status=overall, content_type="application/json")
