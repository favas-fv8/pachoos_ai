"""Access logging middleware — structured request/response logging."""
import logging
import time

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("apps.http")


class StructuredLoggingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request._pachoos_start = time.perf_counter()
        return None

    def process_response(self, request, response):
        duration_ms = (time.perf_counter() - getattr(request, "_pachoos_start", time.perf_counter())) * 1000
        logger.info(
            "http_request",
            extra={
                "request_id": getattr(request, "request_id", ""),
                "method": request.method,
                "path": request.get_full_path(),
                "status": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "user_id": getattr(request.user, "id", None),
                "shop_id": getattr(request, "shop_id", None),
            },
        )
        return response
