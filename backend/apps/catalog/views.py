"""Catalog views — public product listing/detail + shared admin CRUD.

Both admins (super_admin & store_manager) manage the same catalog through the
`admin/*` endpoints; every mutation is persisted to AuditLog and mirrored to
the other admin as a notification (single source of truth = the database).
"""
from io import BytesIO

from django.conf import settings
from django.db.models import Max, ProtectedError
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from PIL import Image
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.admin_dashboard.activity import record_admin_activity
from apps.catalog.models import (
    Category,
    Product,
    ProductImage,
    StockMovement,
    Subcategory,
    Tag,
)
from apps.catalog.serializers import (
    AdminCategorySerializer,
    AdminProductSerializer,
    AdminSubcategorySerializer,
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    SubcategorySerializer,
    TagSerializer,
)
from apps.catalog.services.filter import apply_filters, apply_search
from apps.core.pagination import StandardPagination
from apps.core.permissions import IsAdmin


def _unique_slug(model, value, exclude_pk=None, field="slug"):
    """Return `value` slugified and made unique against `model`."""
    base = slugify(value) or f"{model.__name__.lower()}-{value}"
    slug = base
    n = 1
    while True:
        qs = model.objects.filter(**{field: slug})
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        if not qs.exists():
            return slug
        n += 1
        slug = f"{base}-{n}"


def _product_snapshot(product) -> dict:
    return {
        "pid": product.pid,
        "name": product.name,
        "base_price": str(product.base_price),
        "stock_quantity": product.stock_quantity,
        "is_available": product.is_available,
    }


def _category_snapshot(category) -> dict:
    return {
        "name": category.name,
        "is_active": category.is_active,
    }


# Image formats + size the catalog uploads accept. The size ceiling mirrors the
# server request-body limit (DATA_UPLOAD_MAX_MEMORY_SIZE in dev/prod settings),
# so the frontend hint and the backend validation agree.
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_IMAGE_SIZE_BYTES = getattr(
    settings, "DATA_UPLOAD_MAX_MEMORY_SIZE", 10 * 1024 * 1024
)
MAX_IMAGE_SIZE_MB = MAX_IMAGE_SIZE_BYTES // (1024 * 1024)


def _validate_uploaded_image(image_file):
    """Validate an uploaded image file (format + size).

    Returns an error dict (or None when valid). Keeps the original file object
    untouched so the caller can still save it.
    """
    if image_file is None:
        return {"code": "IMAGE_REQUIRED", "message": "image file is required."}

    if image_file.size > MAX_IMAGE_SIZE_BYTES:
        size_mb = image_file.size / (1024 * 1024)
        return {
            "code": "IMAGE_SIZE_EXCEEDED",
            "message": (
                f"Image is too large ({size_mb:.1f} MB). "
                f"Maximum size is {MAX_IMAGE_SIZE_MB} MB."
            ),
        }

    fmt = None
    try:
        data = image_file.read()
        img = Image.open(BytesIO(data))
        fmt = img.format
        img.verify()
    except Exception:
        return {
            "code": "INVALID_IMAGE",
            "message": "Invalid image file. Use JPG, JPEG, PNG or WEBP.",
        }
    finally:
        image_file.seek(0)

    if fmt not in ALLOWED_IMAGE_FORMATS:
        return {
            "code": "INVALID_IMAGE_TYPE",
            "message": "Unsupported image format. Use JPG, JPEG, PNG or WEBP.",
        }
    return None


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(is_active=True).order_by("display_order")
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]


class SubcategoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SubcategorySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = Subcategory.objects.filter(is_active=True)
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category__slug=category)
        return qs


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """Public product endpoints: list (with search/filter), detail."""

    queryset = Product.objects.select_related(
        "subcategory", "subcategory__category"
    ).prefetch_related("images", "variants", "product_tags__tag")
    serializer_class = ProductDetailSerializer
    pagination_class = StandardPagination
    permission_classes = [AllowAny]
    filter_backends = []  # manual filter logic in list()

    # Customers reach the detail page through a slug (storefront uses
    # /product/<slug>/); admins and cart/orders still reference the numeric pk.
    # Resolve either so no call site needs to change.
    lookup_field = "pk"
    lookup_url_kwarg = "pk"

    def get_object(self):
        qs = self.get_queryset()
        kwarg = self.kwargs.get(self.lookup_url_kwarg)
        if kwarg is None:
            return super().get_object()
        if str(kwarg).isdigit():
            obj = get_object_or_404(qs, pk=kwarg)
        else:
            obj = get_object_or_404(qs, slug=kwarg)
        self.check_object_permissions(self.request, obj)
        return obj

    def list(self, request):
        qs = self.get_queryset()

        # Search
        query = request.query_params.get("q", "")
        qs = apply_search(qs, query)

        # Filters
        qs = apply_filters(
            qs,
            category=request.query_params.get("category"),
            subcategory=request.query_params.get("subcategory"),
            freshness=request.query_params.get("freshness"),
            min_price=request.query_params.get("min_price"),
            max_price=request.query_params.get("max_price"),
            min_rating=request.query_params.get("min_rating"),
            sort_by=request.query_params.get("sort_by", "popularity"),
            available_only=request.query_params.get("available") == "true",
        )

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def related(self, request, pk=None):
        """Frequently bought together / similar products."""
        product = self.get_object()
        related = (
            Product.objects.filter(subcategory=product.subcategory)
            .exclude(pk=product.pk)
            .filter(is_available=True)
            .order_by("-times_sold")[:8]
        )
        serializer = ProductListSerializer(related, many=True)
        return Response(serializer.data)


class ProductAdminViewSet(viewsets.ModelViewSet):
    """Shared admin CRUD for products (both admins).

    Supports multipart uploads (`image` file) and a dedicated stock action
    that keeps the immutable StockMovement ledger in sync.
    """

    queryset = Product.objects.select_related(
        "subcategory", "subcategory__category"
    ).prefetch_related("images", "variants")
    serializer_class = AdminProductSerializer
    pagination_class = StandardPagination
    permission_classes = [IsAdmin]

    def perform_create(self, serializer):
        product = serializer.save()
        record_admin_activity(
            actor=self.request.user,
            action="product_added",
            entity_type="product",
            entity_id=product.pid,
            description=f"Product added: {product.name}",
            after=_product_snapshot(product),
            request=self.request,
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        before = _product_snapshot(instance)
        response = super().update(request, *args, **kwargs)
        product = self.get_object()

        if before["stock_quantity"] != product.stock_quantity:
            StockMovement.objects.create(
                product=product,
                quantity=product.stock_quantity - before["stock_quantity"],
                reason="adjustment",
                note="Stock changed via product update.",
                created_by=request.user,
            )
            record_admin_activity(
                actor=request.user,
                action="stock_changed",
                entity_type="product",
                entity_id=product.pid,
                description=f"Stock changed for {product.name}: "
                            f"{before['stock_quantity']} → {product.stock_quantity}",
                before={"stock_quantity": before["stock_quantity"]},
                after={"stock_quantity": product.stock_quantity},
                request=request,
            )

        if before["is_available"] != product.is_available:
            record_admin_activity(
                actor=request.user,
                action="product_activated" if product.is_available else "product_deactivated",
                entity_type="product",
                entity_id=product.pid,
                description=f"{'Activated' if product.is_available else 'Deactivated'} product: {product.name}",
                before={"is_available": before["is_available"]},
                after={"is_available": product.is_available},
                request=request,
            )

        record_admin_activity(
            actor=request.user,
            action="product_updated",
            entity_type="product",
            entity_id=product.pid,
            description=f"Product updated: {product.name}",
            before=before,
            after=_product_snapshot(product),
            request=request,
        )
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        before = _product_snapshot(instance)
        try:
            instance.delete()
        except ProtectedError:
            return Response(
                {"error": "Product is referenced by orders/inventory history and cannot be deleted. Deactivate it instead."},
                status=409,
            )
        record_admin_activity(
            actor=request.user,
            action="product_deleted",
            entity_type="product",
            entity_id=before["pid"],
            description=f"Product deleted: {before['name']}",
            before=before,
            request=request,
        )
        return Response(status=204)

    @action(detail=True, methods=["post"])
    def stock(self, request, pk=None):
        """Explicit stock update: POST {quantity, reason?, note?}."""
        product = self.get_object()
        try:
            new_qty = int(request.data.get("quantity"))
        except (TypeError, ValueError):
            return Response({"error": "quantity must be an integer."}, status=400)

        old_qty = product.stock_quantity
        delta = new_qty - old_qty
        if delta == 0:
            return Response({"stock_quantity": product.stock_quantity})

        product.stock_quantity = new_qty
        product.save(update_fields=["stock_quantity", "updated_at"])

        StockMovement.objects.create(
            product=product,
            quantity=delta,
            reason=request.data.get("reason", "adjustment"),
            note=request.data.get("note", ""),
            created_by=request.user,
        )
        record_admin_activity(
            actor=request.user,
            action="stock_changed",
            entity_type="product",
            entity_id=product.pid,
            description=f"Stock changed for {product.name}: {old_qty} → {new_qty}",
            before={"stock_quantity": old_qty},
            after={"stock_quantity": new_qty},
            request=request,
        )
        return Response({"stock_quantity": product.stock_quantity})

    @action(detail=True, methods=["post"], url_path="images")
    def upload_image(self, request, pk=None):
        """Upload a product photo: multipart {image, alt_text?, is_primary?}.

        Replaces the current primary image in place so the product's main photo
        (and its sort_order / display position) is preserved. If the product has
        no image yet, a new ProductImage row is created.
        """
        product = self.get_object()
        image_file = request.FILES.get("image")
        image_url = request.data.get("image_url", "").strip()
        if image_file is None and not image_url:
            return Response({"error": "image file or image_url is required."}, status=400)

        if image_file is not None:
            validation_error = _validate_uploaded_image(image_file)
            if validation_error is not None:
                return Response({"error": validation_error}, status=400)

        target = product.images.filter(is_primary=True).first() or product.images.first()

        if image_file is not None:
            old_name = target.image.name if target and target.image else None
            img = target or ProductImage(product=product)
            img.image = image_file
            img.image_url = ""
            if target is None:
                img.sort_order = (
                    product.images.aggregate(m=Max("sort_order"))["m"] or 0
                ) + 1
            img.alt_text = request.data.get("alt_text", product.name)
            img.save()
            if old_name and old_name != img.image.name:
                img.image.storage.delete(old_name)
        else:
            img = target or ProductImage(product=product)
            img.image_url = image_url
            if target is None:
                img.sort_order = (
                    product.images.aggregate(m=Max("sort_order"))["m"] or 0
                ) + 1
            img.alt_text = request.data.get("alt_text", product.name)
            img.save()

        if request.data.get("is_primary") in (True, "true", "1"):
            product.images.filter(is_primary=True).exclude(pk=img.pk).update(is_primary=False)
            img.is_primary = True
            img.save(update_fields=["is_primary"])

        record_admin_activity(
            actor=request.user,
            action="product_image_updated",
            entity_type="product",
            entity_id=product.pid,
            description=f"Image updated for product: {product.name}",
            request=request,
        )
        from apps.catalog.serializers import ProductImageSerializer

        return Response(ProductImageSerializer(img).data, status=201)

    @action(detail=True, methods=["delete"], url_path="images/(?P<image_id>[^/.]+)")
    def delete_image(self, request, pk=None, image_id=None):
        """Delete one product image."""
        product = self.get_object()
        try:
            img = product.images.get(id=image_id)
        except (ProductImage.DoesNotExist, ValueError):
            return Response({"error": "Image not found."}, status=404)
        img.image.delete(save=False) if img.image else None
        img.delete()
        record_admin_activity(
            actor=request.user,
            action="product_image_updated",
            entity_type="product",
            entity_id=product.pid,
            description=f"Image removed for product: {product.name}",
            request=request,
        )
        return Response(status=204)


class CategoryAdminViewSet(viewsets.ModelViewSet):
    """Shared admin CRUD for categories + category-scoped product management."""

    queryset = Category.objects.prefetch_related("subcategories").order_by(
        "display_order", "name"
    )
    serializer_class = AdminCategorySerializer
    permission_classes = [IsAdmin]
    pagination_class = None  # category lists are small; return a flat array

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data["slug"] = _unique_slug(Category, data.get("name", "category"))
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        record_admin_activity(
            actor=request.user,
            action="category_added",
            entity_type="category",
            entity_id=category.id,
            description=f"Category added: {category.name}",
            after=_category_snapshot(category),
            request=request,
        )
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=201, headers=headers)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        before = _category_snapshot(instance)
        response = super().update(request, *args, **kwargs)
        category = self.get_object()
        if before["is_active"] != category.is_active:
            record_admin_activity(
                actor=request.user,
                action="category_activated" if category.is_active else "category_deactivated",
                entity_type="category",
                entity_id=category.id,
                description=f"{'Activated' if category.is_active else 'Deactivated'} category: {category.name}",
                before={"is_active": before["is_active"]},
                after={"is_active": category.is_active},
                request=request,
            )
        record_admin_activity(
            actor=request.user,
            action="category_updated",
            entity_type="category",
            entity_id=category.id,
            description=f"Category updated: {category.name}",
            before=before,
            after=_category_snapshot(category),
            request=request,
        )
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        category_id = instance.id
        has_products = (
            Subcategory.objects.filter(category=instance)
            .filter(products__isnull=False)
            .exists()
        )
        if has_products:
            return Response(
                {"error": "Category contains products. Deactivate it instead."},
                status=409,
            )
        name = instance.name
        try:
            instance.delete()
        except ProtectedError:
            return Response(
                {"error": "Category is in use and cannot be deleted. Deactivate it instead."},
                status=409,
            )
        record_admin_activity(
            actor=request.user,
            action="category_deleted",
            entity_type="category",
            entity_id=category_id,
            description=f"Category deleted: {name}",
            request=request,
        )
        return Response(status=204)

    @action(detail=True, methods=["get"])
    def products(self, request, pk=None):
        """Products belonging to this category (across its subcategories)."""
        category = self.get_object()
        qs = (
            Product.objects.filter(subcategory__category=category)
            .select_related("subcategory", "subcategory__category")
            .prefetch_related("images", "variants")
            .order_by("-created_at")
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = AdminProductSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @action(detail=True, methods=["post"], url_path="subcategories")
    def add_subcategory(self, request, pk=None):
        category = self.get_object()
        data = request.data.copy()
        data["category"] = category.id
        data["slug"] = _unique_slug(
            Subcategory, data.get("name", "subcategory"), field="slug"
        )
        serializer = AdminSubcategorySerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=201)

    @action(detail=True, methods=["post"], url_path="image")
    def upload_image(self, request, pk=None):
        """Upload a category image: multipart {image}. Replaces any existing one."""
        category = self.get_object()
        image_file = request.FILES.get("image")
        if image_file is None:
            return Response({"error": "image file is required."}, status=400)

        validation_error = _validate_uploaded_image(image_file)
        if validation_error is not None:
            return Response({"error": validation_error}, status=400)

        old_image = category.image
        old_name = old_image.name if old_image else None
        category.image = image_file
        category.save(update_fields=["image", "updated_at"])
        if old_name and old_name != category.image.name:
            category.image.storage.delete(old_name)

        record_admin_activity(
            actor=request.user,
            action="category_image_updated",
            entity_type="category",
            entity_id=category.id,
            description=f"Image updated for category: {category.name}",
            request=request,
        )
        return Response({"image_url": category.resolved_url}, status=200)

    @action(detail=True, methods=["patch", "delete"], url_path="subcategories/(?P<subcategory_id>[^/.]+)")
    def subcategory(self, request, pk=None, subcategory_id=None):
        """Update (PATCH) or delete (DELETE) one subcategory of this category.

        Registered as a single route handling both methods so PATCH/DELETE on
        `subcategories/<id>/` never collide (a prior split into two actions with
        the same URL let the DELETE route shadow PATCH → 405).
        """
        category = self.get_object()
        try:
            sub = category.subcategories.get(id=subcategory_id)
        except (Subcategory.DoesNotExist, ValueError):
            return Response({"error": "Subcategory not found."}, status=404)

        if request.method == "DELETE":
            if sub.products.exists():
                return Response(
                    {"error": "Subcategory contains products and cannot be deleted."},
                    status=409,
                )
            sub.delete()
            return Response(status=204)

        serializer = AdminSubcategorySerializer(sub, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [AllowAny]
    search_fields = ["name"]


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StockMovement.objects.select_related("product", "variant").all()
    serializer_class = None  # use a basic serializer
    permission_classes = [IsAdmin]

    def get_serializer_class(self):
        from rest_framework import serializers

        class StockMovementSerializer(serializers.ModelSerializer):
            class Meta:
                model = StockMovement
                fields = "__all__"

        return StockMovementSerializer
