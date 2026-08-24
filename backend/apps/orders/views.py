"""Orders views — order CRUD, checkout, timeline, delivery."""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cart.models import Cart
from apps.catalog.models import Product, ProductVariant
from apps.core.permissions import IsAdmin
from apps.orders.models import Delivery, Order, OrderItem, OrderTimeline
from apps.orders.serializers import (
    DeliverySerializer,
    OrderListSerializer,
    OrderSerializer,
    OrderTimelineSerializer,
)
from apps.orders.services import (
    _dec,
    _next_order_number,
    calculate_delivery,
    place_order,
    resolve_delivery_distance,
)


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
        try:
            order = place_order(
                cart=cart,
                user=request.user,
                delivery_address_id=data.get("delivery_address_id", 0),
                customer_lat=data.get("customer_lat"),
                customer_lon=data.get("customer_lon"),
                coupon_code=data.get("coupon_code"),
                voucher_code=data.get("voucher_code"),
                payment_method=data.get("payment_method", "upi"),
            )
        except ValueError as e:
            # Empty cart / insufficient stock / invalid coupon — surface the
            # reason instead of an unhandled 500.
            return Response(
                {"error": {"code": "BUSINESS_RULE", "message": str(e)}},
                status=status.HTTP_400_BAD_REQUEST,
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


class DirectOrderView(APIView):
    """Create an order directly from a product selection (bypasses cart).

    POST ``{
        "product_id": int,
        "variant_id": int | null,
        "quantity": int,
        "delivery_address_id": int,
        "customer_lat": float | null,
        "customer_lon": float | null,
        "payment_method": str
    }``

    Creates order + order items directly. No cart involved. The delivery
    distance is computed server-side from the customer coordinates and the
    shop row — a client-supplied distance is never trusted.
    Idempotent for duplicate clicks within 1 minute.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        product_id = request.data.get("product_id")
        variant_id = request.data.get("variant_id")
        quantity = request.data.get("quantity", 1)
        delivery_address_id = request.data.get("delivery_address_id", 0)
        customer_lat = request.data.get("customer_lat")
        customer_lon = request.data.get("customer_lon")
        payment_method = request.data.get("payment_method", "cashfree")

        # ── Validate product ──────────────────────────────────────────────
        if not product_id:
            return Response(
                {"error": {"message": "product_id is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product = Product.objects.get(pk=product_id, is_available=True)
        except (Product.DoesNotExist, ValueError, TypeError):
            return Response(
                {"error": {"message": "Product not found or unavailable."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Validate variant ──────────────────────────────────────────────
        variant = None
        if variant_id:
            try:
                variant = ProductVariant.objects.get(
                    pk=variant_id, product=product, is_active=True
                )
            except (ProductVariant.DoesNotExist, ValueError, TypeError):
                return Response(
                    {"error": {"message": "Variant not found or unavailable."}},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # ── Validate quantity ─────────────────────────────────────────────
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            quantity = 1
        if quantity < 1:
            quantity = 1

        source = variant or product
        if source.stock_quantity < quantity:
            return Response(
                {"error": {"message": f"Insufficient stock. Only {source.stock_quantity} available."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Compute delivery distance (server-side haversine) ─────────────
        shop = request.shop
        if not shop:
            from apps.shops.models import Shop

            shop = Shop.objects.first()
        distance_km = resolve_delivery_distance(customer_lat, customer_lon, shop)

        # ── Deduplicate rapid duplicate clicks ────────────────────────────
        one_minute_ago = timezone.now() - timezone.timedelta(minutes=1)
        existing = (
            Order.objects.filter(
                user=user,
                payment_status="pending",
                created_at__gte=one_minute_ago,
            )
            .filter(items__product=product)
            .filter(items__variant=variant)
            .first()
        )
        if existing:
            return Response(
                OrderSerializer(existing).data,
                status=status.HTTP_200_OK,
            )

        # ── Calculate totals ──────────────────────────────────────────────
        price = float(variant.effective_price if variant else product.effective_price)
        base = float(variant.price if variant else product.base_price)
        qty = quantity
        line_total = round(price * qty, 2)
        base_line = round(base * qty, 2)
        product_discount = round(base_line - line_total, 2)
        gst_pct = float(product.gst_percent or 0)
        tax = round(line_total * gst_pct / 100, 2)

        delivery = calculate_delivery(distance_km)
        subtotal = round(line_total, 2)
        grand_total = round(subtotal + delivery["delivery_charge"] + tax, 2)

        # ── Create order + items atomically ───────────────────────────────
        with transaction.atomic():
            order = Order.objects.create(
                shop=shop,
                user=user,
                order_number=_next_order_number(shop.id),
                subtotal=_dec(subtotal),
                discount_total=_dec(product_discount),
                delivery_charge=_dec(delivery["delivery_charge"]),
                tax_total=_dec(tax),
                grand_total=_dec(grand_total),
                delivery_address_id=delivery_address_id or 0,
                distance_km=(
                    _dec(delivery["distance_km"])
                    if delivery["distance_km"] is not None
                    else None
                ),
                delivery_free=delivery["delivery_free"],
                payment_method=payment_method,
                payment_status="pending",
                cashback_earned=_dec(
                    round(grand_total / 100, 2)
                ),
            )

            OrderItem.objects.create(
                order=order,
                product=product,
                variant=variant,
                product_name=product.name,
                variant_name=variant.name if variant else "",
                quantity=qty,
                unit_price=_dec(price),
                discount=Decimal(str(product.discount_percent)),
                gst_percent=Decimal(str(gst_pct)),
                gst_amount=_dec(tax),
                line_total=_dec(line_total),
            )

            OrderTimeline.objects.create(
                order=order,
                status="pending",
                note="Order placed via Buy Now",
                actor_user=user,
                actor_role=user.role,
            )

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)
