"""Catalog serializers — products, variants, categories, tags."""
from django.db.models import Count
from rest_framework import serializers

from apps.catalog.models import (
    Category,
    Product,
    ProductImage,
    ProductVariant,
    Subcategory,
    Tag,
)


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]


class CategorySerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "image_url", "description", "is_active"]

    def get_image_url(self, obj: Category) -> str:
        return obj.resolved_url


class SubcategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Subcategory
        fields = ["id", "category", "name", "slug", "image_url", "is_active"]


class ProductImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ["id", "image_url", "alt_text", "sort_order", "is_primary"]

    def get_image_url(self, obj: ProductImage) -> str:
        return obj.resolved_url


class ProductVariantSerializer(serializers.ModelSerializer):
    effective_price = serializers.ReadOnlyField()

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "name",
            "sku",
            "barcode",
            "price",
            "discount_percent",
            "effective_price",
            "stock_quantity",
            "is_active",
        ]


class ProductListSerializer(serializers.ModelSerializer):
    effective_price = serializers.ReadOnlyField()
    avg_rating = serializers.DecimalField(
        max_digits=2, decimal_places=1, coerce_to_string=False
    )
    subcategory_name = serializers.CharField(
        source="subcategory.name", read_only=True
    )
    category_name = serializers.CharField(
        source="subcategory.category.name", read_only=True
    )
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "slug",
            "name",
            "description",
            "subcategory",
            "subcategory_name",
            "category_name",
            "base_price",
            "effective_price",
            "discount_percent",
            "gst_percent",
            "stock_quantity",
            "freshness",
            "is_available",
            "brand",
            "avg_rating",
            "rating_count",
            "times_sold",
            "is_featured",
            "primary_image",
        ]

    def get_primary_image(self, obj: Product) -> str | None:
        img = obj.images.filter(is_primary=True).first() or obj.images.first()
        return img.resolved_url if img else None


class ProductDetailSerializer(serializers.ModelSerializer):
    effective_price = serializers.ReadOnlyField()
    avg_rating = serializers.DecimalField(
        max_digits=2, decimal_places=1, coerce_to_string=False
    )
    subcategory_name = serializers.CharField(
        source="subcategory.name", read_only=True
    )
    category_name = serializers.CharField(
        source="subcategory.category.name", read_only=True
    )
    variants = ProductVariantSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    tags = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "pid",
            "slug",
            "name",
            "description",
            "ingredients",
            "nutritional_info",
            "subcategory",
            "subcategory_name",
            "category_name",
            "base_price",
            "effective_price",
            "discount_percent",
            "gst_percent",
            "stock_quantity",
            "stock_unit",
            "freshness",
            "is_available",
            "brand",
            "sku",
            "barcode",
            "video_url",
            "avg_rating",
            "rating_count",
            "times_sold",
            "is_featured",
            "variants",
            "images",
            "tags",
        ]

    def get_tags(self, obj: Product) -> list[dict]:
        return [{"id": pt.tag.id, "name": pt.tag.name, "slug": pt.tag.slug} for pt in obj.product_tags.all()]


class AdminCategorySerializer(serializers.ModelSerializer):
    """Full category payload for the admin catalog (includes nested data)."""

    product_count = serializers.SerializerMethodField()
    subcategories = SubcategorySerializer(many=True, read_only=True)
    is_active = serializers.BooleanField(default=True, required=False)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "image_url",
            "display_order",
            "is_active",
            "product_count",
            "subcategories",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_image_url(self, obj: Category) -> str:
        return obj.resolved_url

    def get_product_count(self, obj: Category) -> int:
        return obj.subcategories.aggregate(total=Count("products"))["total"] or 0


class AdminSubcategorySerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(default=True, required=False)

    class Meta:
        model = Subcategory
        fields = ["id", "category", "name", "slug", "image_url", "display_order", "is_active"]
        extra_kwargs = {"category": {"required": False}}


class AdminProductSerializer(serializers.ModelSerializer):
    """Write-friendly payload for the admin product catalog.

    Pricing maps to the existing customer-facing model: `base_price` is the
    real/list price and `selling_price` is the discounted price customers pay
    (derived from base_price × discount_percent). The admin UI sends
    base_price + discount_percent; selling_price is read-only.
    """

    subcategory_name = serializers.CharField(source="subcategory.name", read_only=True)
    category = serializers.IntegerField(source="subcategory.category_id", read_only=True)
    category_name = serializers.CharField(source="subcategory.category.name", read_only=True)
    selling_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True, source="effective_price"
    )
    is_available = serializers.BooleanField(default=True, required=False)
    images = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "pid",
            "name",
            "slug",
            "description",
            "subcategory",
            "subcategory_name",
            "category",
            "category_name",
            "base_price",
            "selling_price",
            "discount_percent",
            "gst_percent",
            "stock_quantity",
            "stock_unit",
            "low_stock_threshold",
            "freshness",
            "is_available",
            "brand",
            "sku",
            "images",
            "variants",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["slug", "created_at", "updated_at"]
