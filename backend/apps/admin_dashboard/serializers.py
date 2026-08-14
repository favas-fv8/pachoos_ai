"""Admin dashboard serializers."""
from rest_framework import serializers


class DashboardStatsSerializer(serializers.Serializer):
    revenue = serializers.DictField()
    orders = serializers.DictField()
    customers = serializers.DictField()
    products = serializers.DictField()
    avg_order_value = serializers.CharField()


class RevenueChartDataSerializer(serializers.Serializer):
    date = serializers.CharField()
    revenue = serializers.CharField()
    orders = serializers.IntegerField()


class TopProductSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    total_sold = serializers.IntegerField()
    total_revenue = serializers.CharField()
    avg_rating = serializers.CharField()
    stock_quantity = serializers.IntegerField()


class LowStockSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    stock_quantity = serializers.IntegerField()
    low_stock_threshold = serializers.IntegerField()


class RecentOrderSerializer(serializers.Serializer):
    id = serializers.CharField()
    order_number = serializers.CharField()
    user_name = serializers.CharField()
    user_phone = serializers.CharField()
    status = serializers.CharField()
    grand_total = serializers.CharField()
    created_at = serializers.CharField()


class CustomerSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    phone = serializers.CharField()
    email = serializers.CharField()
    order_count = serializers.IntegerField()
    total_spent = serializers.CharField()
    date_joined = serializers.CharField()
