"""Cart views — cart CRUD, item add/update/remove, server-side summary."""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.cart.models import Cart, CartItem
from apps.cart.serializers import CartItemSerializer, CartSerializer
from apps.cart.services import compute_cart_summary
from apps.catalog.models import Product, ProductVariant


def _effective_price(variant_or_none, product):
    """Effective (single-discount) price for the chosen inventory source."""
    return variant_or_none.effective_price if variant_or_none else product.effective_price


def _discount_percent(variant_or_none, product):
    return (
        float(variant_or_none.discount_percent)
        if variant_or_none
        else float(product.discount_percent)
    )


class CartViewSet(viewsets.ModelViewSet):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Cart.objects.filter(is_active=True)
        return Cart.objects.filter(user=user, is_active=True)

    def get_serializer_context(self):
        return {"request": self.request}

    def perform_create(self, serializer):
        serializer.save(
            user=self.request.user,
            shop=self.request.shop,
        )

    @action(detail=False, methods=["get", "post"])
    def current(self, request):
        """Get (or lazily create) the user's active cart."""
        cart = Cart.objects.filter(user=request.user, is_active=True).first()
        if cart is None:
            cart = Cart.objects.create(
                user=request.user,
                shop=request.shop,
                is_active=True,
            )
        serializer = self.get_serializer(cart)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        """Server-side cart totals (used by the cart + checkout pages).

        Optional query params: coupon_code, voucher_code, distance_km.
        """
        cart = self.get_object()
        raw_distance = request.query_params.get("distance_km")
        try:
            distance_km = float(raw_distance) if raw_distance else None
        except (TypeError, ValueError):
            distance_km = None
        try:
            data = compute_cart_summary(
                cart,
                coupon_code=request.query_params.get("coupon_code"),
                voucher_code=request.query_params.get("voucher_code"),
                distance_km=distance_km,
                user_id=request.user.id,
            )
        except ValueError as e:
            return Response(
                {"error": {"message": str(e)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(data)

    @action(detail=True, methods=["post"])
    def add_item(self, request, pk=None):
        """Add a product/variant to the cart. Effective price stored exactly once."""
        cart = self.get_object()
        product_id = request.data.get("product_id")
        variant_id = request.data.get("variant_id")
        try:
            quantity = int(request.data.get("quantity", 1))
        except (TypeError, ValueError):
            quantity = 1
        if quantity < 1:
            return Response(
                {"error": "Quantity must be at least 1."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not product_id:
            return Response(
                {"error": "product_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product = Product.objects.get(pk=product_id, is_available=True)
        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found or unavailable."},
                status=status.HTTP_404_NOT_FOUND,
            )

        variant = None
        if variant_id:
            try:
                variant = ProductVariant.objects.get(
                    pk=variant_id, product=product, is_active=True
                )
            except ProductVariant.DoesNotExist:
                return Response(
                    {"error": "Variant not found or unavailable."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        source = variant or product
        available = source.stock_quantity
        if available < quantity:
            return Response(
                {"error": f"Only {available} in stock."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        price = _effective_price(variant, product)
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            variant=variant,
            defaults={
                "quantity": quantity,
                "unit_price": price,
                "discount_percent": _discount_percent(variant, product),
            },
        )
        if not created:
            new_qty = cart_item.quantity + quantity
            if new_qty > available:
                return Response(
                    {"error": f"Only {available} in stock."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            cart_item.quantity = new_qty
            cart_item.unit_price = price
            cart_item.discount_percent = _discount_percent(variant, product)
            cart_item.save(update_fields=["quantity", "unit_price", "discount_percent"])

        serializer = CartItemSerializer(cart_item)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def update_item(self, request, pk=None):
        """Set a cart item's quantity (validates stock)."""
        cart = self.get_object()
        item_id = request.data.get("item_id")
        try:
            quantity = int(request.data.get("quantity"))
        except (TypeError, ValueError):
            return Response(
                {"error": "quantity is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if quantity < 1:
            return Response(
                {"error": "Quantity must be at least 1."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            item = CartItem.objects.get(pk=item_id, cart=cart)
        except CartItem.DoesNotExist:
            return Response(
                {"error": "Cart item not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        source = item.variant or item.product
        if quantity > source.stock_quantity:
            return Response(
                {"error": f"Only {source.stock_quantity} in stock."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        item.quantity = quantity
        item.save(update_fields=["quantity"])
        return Response(CartItemSerializer(item).data)

    @action(detail=True, methods=["post"])
    def remove_item(self, request, pk=None):
        """Remove a specific cart item."""
        cart = self.get_object()
        item_id = request.data.get("item_id")
        try:
            item = CartItem.objects.get(pk=item_id, cart=cart)
        except CartItem.DoesNotExist:
            return Response(
                {"error": "Cart item not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        item.delete()
        return Response({"removed": True})

    @action(detail=True, methods=["post"])
    def clear(self, request, pk=None):
        """Clear all items from the cart."""
        cart = self.get_object()
        cart.items.all().delete()
        return Response({"cleared": True})
