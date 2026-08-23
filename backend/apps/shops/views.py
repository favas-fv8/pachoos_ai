"""Shop views — shop configuration API (admin-only)."""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdmin
from apps.shops.serializers import ShopLocationSerializer


class ShopLocationView(APIView):
    """GET/PATCH the active shop's location (latitude/longitude).

    The shop is resolved by ``ShopContextMiddleware`` (``X-Shop-Id`` header
    override, else the first active shop row). Coordinates are stored on the
    existing ``Shop.lat`` / ``Shop.lng`` DecimalFields.
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        shop = getattr(request, "shop", None)
        if not shop:
            return Response(
                {"error": {"message": "No active shop found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ShopLocationSerializer(shop).data)

    def patch(self, request):
        shop = getattr(request, "shop", None)
        if not shop:
            return Response(
                {"error": {"message": "No active shop found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = ShopLocationSerializer(shop, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
