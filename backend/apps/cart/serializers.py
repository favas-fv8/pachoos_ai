"""Cart serializers."""
from rest_framework import serializers

from apps.cart.models import Cart, CartItem
from apps.catalog.serializers import ProductListSerializer


class CartItemSerializer(serializers.ModelSerializer):
    product_data = ProductListSerializer(source="product", read_only=True)
    line_total = serializers.ReadOnlyField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product",
            "product_data",
            "variant",
            "quantity",
            "unit_price",
            "discount_percent",
            "line_total",
        ]


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    item_count = serializers.ReadOnlyField(source="item_count")
    subtotal = serializers.ReadOnlyField()

    class Meta:
        model = Cart
        fields = [
            "id",
            "shop",
            "user",
            "items",
            "item_count",
            "subtotal",
            "is_active",
        ]