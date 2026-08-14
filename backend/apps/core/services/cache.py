"""Centralized cache helpers with graceful degradation when Redis is absent."""
import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("apps.cache")


def cache_ping() -> bool:
    """Writes + reads a probe key. Returns True if cache is usable."""
    try:
        cache.set("__ping__", 1, timeout=5)
        return cache.get("__ping__") == 1
    except Exception:
        logger.warning("Cache ping failed", exc_info=True)
        return False


def cache_get(key):
    try:
        return cache.get(key)
    except Exception:
        logger.warning("Cache get failed", exc_info=True)
        return None


def cache_set(key, value, timeout=None):
    timeout = timeout or getattr(settings, "CACHE_TTL_DEFAULT", 300)
    try:
        cache.set(key, value, timeout=timeout)
    except Exception:
        logger.warning("Cache set failed", exc_info=True)


def cache_delete(key):
    try:
        cache.delete(key)
    except Exception:
        logger.warning("Cache delete failed", exc_info=True)
