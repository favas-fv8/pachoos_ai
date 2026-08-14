"""Permission classes implementing the fixed 2-admin RBAC model.

Roles: super_admin, store_manager, customer.
Customers never write to catalog/inventory/coupon/debt/bank resources.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

STAFF_ROLES = {"super_admin", "store_manager"}


class IsCustomer(BasePermission):
    """Authenticated customers only (role == customer)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == "customer")


class IsAdmin(BasePermission):
    """Both admin roles (super_admin and store_manager)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in STAFF_ROLES)


class IsSuperAdmin(BasePermission):
    """super_admin only (system settings, staff, other admins)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == "super_admin")


class IsAdminOrReadOnly(BasePermission):
    """Any authenticated user reads; only the 2 admins mutate."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.role in STAFF_ROLES
