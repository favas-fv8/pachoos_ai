"""Loads the celery app so `celery -A config worker` works."""
from config.celery import app as celery_app

__all__ = ("celery_app",)
