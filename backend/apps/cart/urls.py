"""Cart API routes."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.cart.views import CartViewSet

router = DefaultRouter(trailing_slash=False)
router.register("carts", CartViewSet, basename="cart")

urlpatterns = [
    path("", include(router.urls)),
]