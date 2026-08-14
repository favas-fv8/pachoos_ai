"""Seed the primary shop and the fixed 2-admin staff set.

Usage:
    python manage.py seed_demo

Creates (idempotently):
  - Primary Shop "PACHOOS" with default delivery rules
  - super_admin  user (phone from --super-phone or PACH_ADMIN_PHONE env)
  - store_manager user (phone from --manager-phone or PACH_MANAGER_PHONE env)

Exactly two staff users exist. The command refuses to create a third.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()

DEFAULT_PHONE = "9999999999"
DEFAULT_PASSWORD = "Pachoos@2026"


class Command(BaseCommand):
    help = "Seed the primary shop and exactly 2 admin users."

    def add_arguments(self, parser):
        parser.add_argument("--super-phone", default=os.getenv("PACH_ADMIN_PHONE", DEFAULT_PHONE))
        parser.add_argument("--manager-phone", default=os.getenv("PACH_MANAGER_PHONE", "9999999998"))
        parser.add_argument("--password", default=os.getenv("PACH_ADMIN_PASSWORD", DEFAULT_PASSWORD))

    def handle(self, *args, **opts):
        from apps.shops.models import Shop

        shop, created = Shop.objects.get_or_create(
            slug="pachoos",
            defaults={
                "name": "PACHOOS Bakery & Fruits",
                "tagline": "Fresh every day",
                "city": "",
                "is_primary": True,
                "is_active": True,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created shop: {shop.name}"))
        else:
            shop.is_primary = True
            shop.save(update_fields=["is_primary"])

        existing_staff = User.objects.filter(role__in=["super_admin", "store_manager"]).count()
        if existing_staff >= 2:
            self.stdout.write(self.style.WARNING("2 admins already exist — not creating more."))
            return

        super_user = self._get_or_create_admin(
            role="super_admin", phone=opts["super_phone"],
            password=opts["password"], shop=shop,
        )
        manager_user = self._get_or_create_admin(
            role="store_manager", phone=opts["manager_phone"],
            password=opts["password"], shop=shop,
        )

        self.stdout.write(self.style.SUCCESS(
            f"Admins ready -> super_admin: {super_user.phone} | store_manager: {manager_user.phone}"
        ))
        self.stdout.write(self.style.WARNING(
            f"Dev password for both: {opts['password']} — change immediately in production."
        ))

    def _get_or_create_admin(self, role, phone, password, shop):
        user = User.objects.filter(role=role).first()
        if user:
            return user
        if User.objects.filter(phone=phone).exists():
            raise CommandError(f"Phone {phone} already registered — pass --{role.replace('_', '-')}-phone.")
        user = User.objects.create_user(
            phone=phone,
            email=f"{role}@pachoos.local",
            password=password,
            role=role,
            shop=shop,
            is_verified=True,
            is_staff=True,
            full_name="Super Admin" if role == "super_admin" else "Store Manager",
        )
        if role == "super_admin":
            user.is_superuser = True
            user.save(update_fields=["is_superuser"])
        return user
