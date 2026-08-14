"""Custom API exception handler producing a consistent error envelope.

All errors return:
    {"error": {"code": "...", "message": "...", "details": {...}}}
"""
import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions, status

logger = logging.getLogger("apps.exceptions")


class BusinessError(exceptions.APIException):
    """Base for domain errors carrying a stable machine-readable code."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "BUSINESS_RULE"
    default_detail = "Operation violates a business rule."

    def __init__(self, message=None, code=None, details=None):
        self.detail = message or self.default_detail
        self.code = code or self.default_code
        self.details = details or {}


class BusinessRuleError(BusinessError):
    """Generic business-rule violation (400)."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "BUSINESS_RULE"
    default_detail = "Operation violates a business rule."


class NotFoundError(BusinessError):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "NOT_FOUND"


class PermissionDeniedError(BusinessError):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "FORBIDDEN"


def _extract_field_errors(detail):
    """Fold DRF field errors into {field: [messages]}."""
    out = {}
    if isinstance(detail, dict):
        for key, value in detail.items():
            if isinstance(value, list):
                out[key] = [str(e) for e in value]
            elif isinstance(value, dict):
                out[key] = _extract_field_errors(value)
            else:
                out[key] = str(value)
    elif isinstance(detail, list):
        out["non_field_errors"] = [str(e) for e in detail]
    else:
        out["detail"] = str(detail)
    return out


def api_exception_handler(exc, context):
    from rest_framework.views import exception_handler as drf_handler

    response = drf_handler(exc, context)

    if response is None:
        logger.exception("Unhandled exception", exc_info=True)
        return response

    if isinstance(exc, BusinessError):
        code, message = exc.code, str(exc.detail)
        details = exc.details
    elif isinstance(exc, (exceptions.Throttled,)):
        code, message, details = "RATE_LIMITED", str(exc.detail), {
            "retry_after": getattr(exc, "wait", None),
        }
    elif isinstance(exc, (DjangoValidationError, exceptions.ValidationError)):
        code, message = "VALIDATION_ERROR", "Invalid payload."
        details = _extract_field_errors(exc.detail)
    elif isinstance(exc, exceptions.AuthenticationFailed):
        code, message = "AUTH_FAILED", str(exc.detail)
        details = {}
    elif isinstance(exc, exceptions.NotAuthenticated):
        code, message = "NOT_AUTHENTICATED", str(exc.detail)
        details = {}
    elif isinstance(exc, exceptions.PermissionDenied):
        code, message = "FORBIDDEN", str(exc.detail)
        details = {}
    elif isinstance(exc, exceptions.NotFound):
        code, message = "NOT_FOUND", str(exc.detail)
        details = {}
    elif isinstance(exc, Http404):
        # Django's Http404 (raised by get_object_or_404) has no `.detail`;
        # normalize it to the same NOT_FOUND envelope DRF uses for NotFound.
        code, message = "NOT_FOUND", "Not found."
        details = {}
    else:
        code, message = "ERROR", str(exc.detail)
        details = _extract_field_errors(exc.detail)

    response.data = {
        "error": {"code": code, "message": message, "details": details}
    }
    return response
