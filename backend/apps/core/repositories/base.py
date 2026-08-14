"""Repository pattern — abstracts data access from the service layer.

Keeps querysets in one place (indexing, scoping, select_related) so services
stay focused on business rules and stay unit-testable with fakes.
"""
from django.db import transaction


class BaseRepository:
    model = None

    # --- Queries -----------------------------------------------------------
    def get(self, **filters):
        return self.model.objects.get(**filters)

    def get_or_none(self, **filters):
        try:
            return self.model.objects.get(**filters)
        except self.model.DoesNotExist:
            return None

    def filter(self, **filters):
        return self.model.objects.filter(**filters)

    def exists(self, **filters) -> bool:
        return self.model.objects.filter(**filters).exists()

    def count(self, **filters) -> int:
        return self.model.objects.filter(**filters).count()

    # --- Writes (respecting update_fields for audit-safe saves) -------------
    def create(self, **kwargs):
        return self.model.objects.create(**kwargs)

    @transaction.atomic
    def update(self, instance, **fields):
        for key, value in fields.items():
            setattr(instance, key, value)
        instance.save(update_fields=list(fields.keys()))
        return instance

    def delete(self, instance):
        instance.delete()
        return None
