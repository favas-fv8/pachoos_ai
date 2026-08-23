"""Shop serializers."""
from decimal import Decimal

from rest_framework import serializers

from apps.shops.models import Shop


class ShopLocationSerializer(serializers.ModelSerializer):
    """Read + update the shop's geolocation (``lat``/``lng`` only).

    Address/name fields are read-only context; coordinates must always be
    sent together so the shop never ends up with a half-set position.
    """

    lat = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
        required=False,
        allow_null=True,
        min_value=Decimal("-90"),
        max_value=Decimal("90"),
    )
    lng = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
        required=False,
        allow_null=True,
        min_value=Decimal("-180"),
        max_value=Decimal("180"),
    )

    class Meta:
        model = Shop
        fields = ["id", "name", "address_line1", "city", "state", "lat", "lng"]
        read_only_fields = ["id", "name", "address_line1", "city", "state"]

    def validate(self, attrs):
        if ("lat" in attrs) != ("lng" in attrs):
            raise serializers.ValidationError(
                {"detail": "lat and lng must be sent together."}
            )
        return attrs
