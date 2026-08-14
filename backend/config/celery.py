"""PACHOOS Celery application."""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("pachoos")
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in every app's tasks.py module.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
