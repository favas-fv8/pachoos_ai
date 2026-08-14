"""Shop context middleware — resolves the active shop for multi-branch data.

The staff set is fixed at 2 admins; shops exist as *configuration* rows.
Resolved shop is exposed as ``request.shop`` and ``request.shop_id`` and is
used by every queryset to scope data.
"""
from django.utils.deprecation import MiddlewareMixin

from apps.shops.models import Shop


class ShopContextMiddleware(MiddlewareMixin):
    HEADER = "HTTP_X_SHOP_ID"

    def process_request(self, request):
        shop = None
        header_id = request.META.get(self.HEADER)
        if header_id:
            try:
                shop = Shop.objects.filter(pk=header_id, is_active=True).first()
            except (ValueError, TypeError):
                shop = None
        if shop is None:
            shop = Shop.objects.filter(is_active=True).order_by("id").first()
        request.shop = shop
        request.shop_id = shop.id if shop else None
        return None
