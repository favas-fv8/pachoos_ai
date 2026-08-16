"""Admin dashboard views — stats, charts, reports, customer/order management."""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_dashboard.activity import (
    get_admin_notifications,
    mark_admin_notification_read,
)
from apps.admin_dashboard.services import (
    deactivate_customer,
    get_all_orders,
    get_customer_detail,
    get_customer_list,
    get_dashboard_stats,
    get_low_stock_products,
    get_order_detail,
    get_recent_orders,
    get_revenue_chart,
    get_top_products,
    update_customer,
)
from apps.core.permissions import IsAdmin


class DashboardStatsView(APIView):
    """GET dashboard overview stats."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        shop = getattr(request, "shop", None)
        return Response(get_dashboard_stats(shop))


class RevenueChartView(APIView):
    """GET daily revenue chart data."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        shop = getattr(request, "shop", None)
        days = int(request.query_params.get("days", 30))
        return Response(get_revenue_chart(shop, days))


class TopProductsView(APIView):
    """GET top-selling products."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        shop = getattr(request, "shop", None)
        limit = int(request.query_params.get("limit", 10))
        return Response(get_top_products(shop, limit))


class LowStockView(APIView):
    """GET products running low on stock."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        shop = getattr(request, "shop", None)
        return Response(get_low_stock_products(shop))


class RecentOrdersView(APIView):
    """GET recent orders."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        shop = getattr(request, "shop", None)
        limit = int(request.query_params.get("limit", 20))
        return Response(get_recent_orders(shop, limit))


class CustomerListView(APIView):
    """GET customer list with stats."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        shop = getattr(request, "shop", None)
        limit = int(request.query_params.get("limit", 50))
        return Response(get_customer_list(shop, limit))


class CustomerDetailView(APIView):
    """GET detailed customer info (with the full linked Debt Book), PATCH to
    safely edit profile details, or DELETE to soft-delete the account while
    preserving all financial/debt history."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, customer_id):
        try:
            data = get_customer_detail(customer_id)
        except Exception:
            return Response({"error": "Customer not found."}, status=404)
        return Response(data)

    def patch(self, request, customer_id):
        allowed = {k: v for k, v in request.data.items() if k in ("full_name", "phone", "email", "is_active")}
        if not allowed:
            return Response(
                {"error": "No editable fields provided."},
                status=400,
            )
        try:
            user = update_customer(customer_id, admin_user=request.user,
                                   request=request, **allowed)
        except ValueError as e:
            return Response({"error": {"message": str(e)}}, status=400)
        data = get_customer_detail(user.id)
        return Response(data)

    def delete(self, request, customer_id):
        try:
            deactivate_customer(customer_id, admin_user=request.user, request=request)
        except ValueError as e:
            return Response({"error": {"message": str(e)}}, status=400)
        return Response({"message": "Customer deleted."}, status=204)


class AllOrdersView(APIView):
    """GET all orders with optional status filter."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        shop = getattr(request, "shop", None)
        status_filter = request.query_params.get("status")
        limit = int(request.query_params.get("limit", 50))
        return Response(get_all_orders(shop, status_filter, limit))


class OrderDetailView(APIView):
    """GET a full admin view of a single order (customer, payment, items,
    timeline, delivery)."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, order_id):
        try:
            data = get_order_detail(order_id)
        except ValueError as e:
            return Response({"error": {"message": str(e)}}, status=404)
        return Response(data)


class AdminNotificationsView(APIView):
    """GET notifications of the *other* admin's activities (shared dashboard)."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        limit = int(request.query_params.get("limit", 50))
        return Response(get_admin_notifications(request.user, limit))


class AdminNotificationReadView(APIView):
    """POST to mark notifications as read (one id, or all when omitted)."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        notification_id = request.data.get("id")
        if notification_id is None:
            return Response({"marked": mark_admin_notification_read(request.user)})
        from apps.admin_dashboard.models import AdminNotification

        qs = AdminNotification.objects.filter(
            id=notification_id, recipient=request.user
        )
        if not qs.exists():
            return Response({"error": "Notification not found."}, status=404)
        qs.update(is_read=True)
        return Response({"marked": 1})
