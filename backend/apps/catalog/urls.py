"""Catalog API routes."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.catalog.views import (
    CategoryAdminViewSet,
    CategoryViewSet,
    ProductAdminViewSet,
    ProductViewSet,
    StockMovementViewSet,
    SubcategoryViewSet,
    TagViewSet,
)

router = DefaultRouter(trailing_slash=True)
router.register("categories", CategoryViewSet, basename="category")
router.register("subcategories", SubcategoryViewSet, basename="subcategory")
router.register("products", ProductViewSet, basename="product")
router.register("admin/categories", CategoryAdminViewSet, basename="admin-category")
router.register("admin/products", ProductAdminViewSet, basename="admin-product")
router.register("tags", TagViewSet, basename="tag")
router.register("stock-movements", StockMovementViewSet, basename="stock-movement")

urlpatterns = [
    path("", include(router.urls)),
]
