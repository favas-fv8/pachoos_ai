"""Shop routes."""
from django.urls import path

from apps.shops.views import ShopLocationView

urlpatterns = [
    path("location/", ShopLocationView.as_view(), name="shop-location"),
]
