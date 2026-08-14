"""Cart views — cart CRUD for authenticated users."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.cart.models import Cart, CartItem
from apps.cart.serializers import CartSerializer, CartItemSerializer
from apps.catalog.models import Product, ProductVariant
from apps.core.permissions import IsAdminOrReadOnly


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

    @action(detail=True, methods=["post"])
    def add_item(self, request, pk=None):
        """Add a product variant to the cart."""
        cart = self.get_object()
        product_id = request.data.get("product_id")
        variant_id = request.data.get("variant_id")
        quantity = int(request.data.get("quantity", 1))

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

        # Check stock
        available = variant.stock_quantity if variant else product.stock_quantity
        if available < quantity:
            return Response(
                {"error": f"Only {available} in stock."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get or create cart item
        price = variant.effective_price if variant else product.effective_price
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            variant=variant,
            defaults={
                "quantity": quantity,
                "unit_price": price,
                "discount_percent": product.discount_percent,
            },
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save(update_fields=["quantity"])

        serializer = CartItemSerializer(cart_item)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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