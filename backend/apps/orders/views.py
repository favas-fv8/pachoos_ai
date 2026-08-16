"""Orders views — order CRUD, checkout, timeline, delivery."""
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.cart.models import Cart
from apps.core.permissions import IsAdmin
from apps.orders.models import Delivery, Order, OrderTimeline
from apps.orders.serializers import (
    DeliverySerializer,
    OrderListSerializer,
    OrderSerializer,
    OrderTimelineSerializer,
)
from apps.orders.services import place_order


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Order.objects.all().select_related("user", "shop").prefetch_related("items", "timeline")
        return Order.objects.filter(user=user).select_related("user", "shop").prefetch_related("items", "timeline")

    def get_serializer_class(self):
        if self.action == "list":
            return OrderListSerializer
        return OrderSerializer

    def create(self, request, *args, **kwargs):
        """Checkout: create an order from the user's active cart."""
        cart = Cart.objects.filter(user=request.user, is_active=True).first()
        if not cart:
            return Response(
                {"error": "No active cart found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = request.data
        order = place_order(
            cart=cart,
            user=request.user,
            delivery_address_id=data.get("delivery_address_id", 0),
            distance_km=data.get("distance_km"),
            coupon_code=data.get("coupon_code"),
            voucher_code=data.get("voucher_code"),
            payment_method=data.get("payment_method", "upi"),
        )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def update_status(self, request, pk=None):
        """Admin: update order status."""
        if not request.user.is_staff:
            return Response(
                {"error": "Admin only."},
                status=status.HTTP_403_FORBIDDEN,
            )
        order = self.get_object()
        new_status = request.data.get("status")
        valid_statuses = [
            choice[0] for choice in Order._meta.get_field("status").choices
        ]
        if new_status not in valid_statuses:
            return Response(
                {"error": f"Invalid status. Choose from: {', '.join(valid_statuses)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order.status = new_status
        order.save(update_fields=["status"])

        OrderTimeline.objects.create(
            order=order,
            status=new_status,
            note=request.data.get("note", f"Status updated to {new_status}"),
            actor_user=request.user,
            actor_role=request.user.role,
        )
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel an order (pending/accepted only)."""
        order = self.get_object()
        if order.status not in ("pending", "accepted"):
            return Response(
                {"error": f"Cannot cancel order in '{order.status}' status."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order.status = "cancelled"
        order.cancellation_reason = request.data.get("reason", "Customer request")
        order.cancelled_at = timezone.now()
        order.save(update_fields=["status", "cancellation_reason", "cancelled_at"])

        OrderTimeline.objects.create(
            order=order,
            status="cancelled",
            note=order.cancellation_reason,
            actor_user=request.user,
            actor_role=request.user.role,
        )
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        """Get order timeline."""
        order = self.get_object()
        timeline = OrderTimeline.objects.filter(order=order).order_by("created_at")
        serializer = OrderTimelineSerializer(timeline, many=True)
        return Response(serializer.data)


class DeliveryViewSet(viewsets.ModelViewSet):
    queryset = Delivery.objects.all()
    serializer_class = DeliverySerializer
    permission_classes = [IsAdmin]
