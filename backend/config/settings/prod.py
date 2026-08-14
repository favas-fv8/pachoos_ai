"""Production settings — hardened. Fail closed when secrets are missing."""
import os

from .base import *  # noqa: F403
from .base import env

DEBUG = False

# Fail fast if production secrets are absent.
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# --- TLS / security headers -------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

# --- CSP (hardened default; adjust to your asset hosts) ----------------------
CSP_DEFAULT_SRC = ["'self'"]
CSP_SCRIPT_SRC = ["'self'"]
CSP_STYLE_SRC = ["'self'", "'unsafe-inline'"]
CSP_IMG_SRC = ["'self'", "data:", "https:"]
CSP_CONNECT_SRC = ["'self'"]

# --- CORS ---------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")

# --- Brokers / cache ----------------------------------------------------
CELERY_TASK_ALWAYS_EAGER = False
CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND")

# Production structured logging
LOGGING["root"]["handlers"] = ["json_console"]  # noqa: F405
LOGGING["loggers"]["django.request"]["handlers"] = ["json_console"]  # noqa: F405
LOGGING["loggers"]["apps"]["handlers"] = ["json_console"]  # noqa: F405
LOGGING["loggers"]["celery"]["handlers"] = ["json_console"]  # noqa: F405

# Only support JSON in production.
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = (  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
)

# Do not serve the browsable API / debug toolbars in production.
if os.environ.get("ENABLE_ADMIN_API") != "1":
    SPECTACULAR_SETTINGS["SERVE_PUBLIC"] = False  # noqa: F405
    SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = ["rest_framework.permissions.IsAdminUser"]  # noqa: F405
