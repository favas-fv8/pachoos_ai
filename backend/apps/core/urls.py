"""API root — wires Swagger docs and app route modules under /api/v1/."""
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.core.views import health

urlpatterns = [
    # Health first, unauthenticated, no versioning.
    path("", health, name="health-root"),
    path("health/", health, name="health"),

    # Auth routes (public).
    path("auth/", include("apps.accounts.urls")),

    # Catalog routes (public read, admin write).
    path("catalog/", include("apps.catalog.urls")),

    # Cart routes.
    path("cart/", include("apps.cart.urls")),

    # Orders routes.
    path("orders/", include("apps.orders.urls")),

    # Payments routes.
    path("payments/", include("apps.payments.urls")),

    # Wallet routes.
    path("wallet/", include("apps.wallet.urls")),

    # Shop configuration routes (admin-only).
    path("shops/", include("apps.shops.urls")),

    # AI routes.
    path("ai/", include("apps.ai.urls")),

    # Admin dashboard routes.
    path("admin-dashboard/", include("apps.admin_dashboard.urls")),

    # OpenAPI schema + docs
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
