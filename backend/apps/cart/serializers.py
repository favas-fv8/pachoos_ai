"""Cart serializers."""
from rest_framework import serializers

from apps.cart.models import Cart, CartItem
from apps.catalog.serializers import ProductListSerializer, ProductVariantSerializer


class CartItemSerializer(serializers.ModelSerializer):
    product_data = ProductListSerializer(source="product", read_only=True)
    variant_data = ProductVariantSerializer(source="variant", read_only=True)
    line_total = serializers.ReadOnlyField()
    effective_price = serializers.ReadOnlyField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product",
            "product_data",
            "variant",
            "variant_data",
            "quantity",
            "unit_price",
            "discount_percent",
            "effective_price",
            "line_total",
        ]


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    item_count = serializers.ReadOnlyField()
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
        read_only_fields = ["shop", "user", "is_active"]
