"""Root URL configuration."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.core.views import health

urlpatterns = [
    # Health first, unauthenticated, no versioning.
    path("", health, name="health-root"),
    path("health/", health, name="health"),

    path("api/v1/", include("apps.core.urls")),

    # Admin backend (Django admin for super admin only; RBAC is enforced).
    path("admin/", admin.site.urls),
]

# Serve uploaded product images in dev (S3/Cloudinary in prod).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

