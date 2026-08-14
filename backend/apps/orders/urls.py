"""Orders API routes.

The orders app is mounted at ``/api/v1/orders/`` in ``apps/core/urls.py``, so
the order collection, its actions and deliveries are declared relative to that
root (e.g. ``/api/v1/orders/`` for the list, ``/api/v1/orders/<pk>/`` for the
detail). Using ``DefaultRouter`` here plus the ``orders/`` include prefix would
double the prefix to ``/api/v1/orders/orders``, which is not the documented
contract — and worse, ``/api/v1/orders/`` would resolve to the router's api-root
dict instead of the paginated list. Explicit routes keep the contract exact.
"""
from django.urls import path

from apps.orders.views import OrderViewSet, DeliveryViewSet

urlpatterns = [
    path(
        "",
        OrderViewSet.as_view({"get": "list", "post": "create"}),
        name="order-list",
    ),
    path(
        "<uuid:pk>/",
        OrderViewSet.as_view(
            {
                "get": "retrieve",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="order-detail",
    ),
    path(
        "<uuid:pk>/cancel/",
        OrderViewSet.as_view({"post": "cancel"}),
        name="order-cancel",
    ),
    path(
        "<uuid:pk>/timeline/",
        OrderViewSet.as_view({"get": "timeline"}),
        name="order-timeline",
    ),
    path(
        "<uuid:pk>/update_status/",
        OrderViewSet.as_view({"post": "update_status"}),
        name="order-update-status",
    ),
    path(
        "deliveries/",
        DeliveryViewSet.as_view({"get": "list", "post": "create"}),
        name="delivery-list",
    ),
    path(
        "deliveries/<uuid:pk>/",
        DeliveryViewSet.as_view(
            {
                "get": "retrieve",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="delivery-detail",
    ),
]