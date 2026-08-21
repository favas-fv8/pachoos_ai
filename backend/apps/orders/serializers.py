"""Orders serializers."""
from rest_framework import serializers

from apps.orders.models import Delivery, Order, OrderItem, OrderTimeline
from apps.payments.gateway import normalize_payment_method


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = "__all__"


class OrderTimelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderTimeline
        fields = "__all__"


class DeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = Delivery
        fields = "__all__"


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    timeline = OrderTimelineSerializer(many=True, read_only=True)
    delivery = DeliverySerializer(read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    user_phone = serializers.CharField(source="user.phone", read_only=True, default="")
    user_email = serializers.CharField(source="user.email", read_only=True, default="")
    payment_method = serializers.SerializerMethodField()
    cashback_earned = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = "__all__"

    def get_payment_method(self, obj: Order) -> str:
        return normalize_payment_method(obj.payment_method)

    def get_cashback_earned(self, obj: Order) -> str:
        # ``cashback_earned`` snapshots the potential cashback at checkout;
        # it is only actually earned once payment succeeds. Unsuccessful /
        # unfinished orders must always report ₹0.
        return str(obj.cashback_earned) if obj.payment_status == "paid" else "0.00"


class OrderListSerializer(serializers.ModelSerializer):
    items_count = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display")
    payment_status_display = serializers.CharField(
        source="get_payment_status_display", read_only=True
    )
    payment_method = serializers.SerializerMethodField()
    cashback_earned = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "status_display",
            "payment_status",
            "payment_status_display",
            "payment_method",
            "cashback_earned",
            "grand_total",
            "subtotal",
            "discount_total",
            "delivery_charge",
            "tax_total",
            "delivery_free",
            "created_at",
            "items_count",
        ]

    def get_items_count(self, obj: Order) -> int:
        return obj.items.count()

    def get_payment_method(self, obj: Order) -> str:
        return normalize_payment_method(obj.payment_method)

    def get_cashback_earned(self, obj: Order) -> str:
        # Cashback is earned only on successful payment — see OrderSerializer.
        return str(obj.cashback_earned) if obj.payment_status == "paid" else "0.00"
