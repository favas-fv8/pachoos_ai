"""Admin dashboard API routes."""
from django.urls import path

from apps.admin_dashboard.views import (
    AdminNotificationReadView,
    AdminNotificationsView,
    AllOrdersView,
    CustomerDetailView,
    CustomerListView,
    DashboardStatsView,
    LowStockView,
    RecentOrdersView,
    RevenueChartView,
    TopProductsView,
)

urlpatterns = [
    path("stats/", DashboardStatsView.as_view(), name="admin-stats"),
    path("revenue-chart/", RevenueChartView.as_view(), name="admin-revenue-chart"),
    path("top-products/", TopProductsView.as_view(), name="admin-top-products"),
    path("low-stock/", LowStockView.as_view(), name="admin-low-stock"),
    path("recent-orders/", RecentOrdersView.as_view(), name="admin-recent-orders"),
    path("all-orders/", AllOrdersView.as_view(), name="admin-all-orders"),
    path("customers/", CustomerListView.as_view(), name="admin-customers"),
    path("customers/<int:customer_id>/", CustomerDetailView.as_view(), name="admin-customer-detail"),
    path("notifications/", AdminNotificationsView.as_view(), name="admin-notifications"),
    path("notifications/read/", AdminNotificationReadView.as_view(), name="admin-notifications-read"),
]
