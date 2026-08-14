"""Service layer base — a thin, dependency-injected shell.

Services hold business logic; repositories own the ORM. Views instantiate
services (or get them via a registry) so logic is reusable by views, Celery
tasks, and management commands alike.
"""

from apps.core.repositories.base import BaseRepository


class BaseService:
    repository: type[BaseRepository]

    def __init__(self, repository=None, **deps):
        self.repository = repository or self.repository()
        self.deps = deps

    def get_dependency(self, name):
        return self.deps.get(name)
