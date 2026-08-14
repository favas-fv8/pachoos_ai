"""Orders serializers."""
from rest_framework import serializers

from apps.orders.models import Order, OrderItem, OrderTimeline, Delivery


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

    class Meta:
        model = Order
        fields = "__all__"


class OrderListSerializer(serializers.ModelSerializer):
    items_count = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display")

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "status_display",
            "grand_total",
            "delivery_charge",
            "delivery_free",
            "created_at",
            "items_count",
        ]

    def get_items_count(self, obj: Order) -> int:
        return obj.items.count()