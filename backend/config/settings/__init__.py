"""Dynamically re-exports settings from the selected environment module.

Django imports ``config.settings`` and reads attributes off it. We therefore
import the environment-specific module (dev/prod) and copy its attributes
(uppercase names) into this package's namespace.

    DJANGO_ENV=dev python manage.py runserver   # default
    DJANGO_ENV=prod python manage.py runserver
"""
import os
from importlib import import_module

_ENV = os.getenv("DJANGO_ENV", "dev").strip().lower()
if _ENV not in {"dev", "prod"}:
    raise ValueError(f"Unsupported DJANGO_ENV={_ENV!r}. Use 'dev' or 'prod'.")

_selected = import_module(f"config.settings.{_ENV}")

for _name in dir(_selected):
    if _name.isupper():
        globals()[_name] = getattr(_selected, _name)
del _name, _selected
