"""Catalog serializers — products, variants, categories, tags."""
from django.db.models import Count, ProtectedError
from django.utils.text import slugify
from rest_framework import serializers

from apps.catalog.models import (
    Category,
    Product,
    ProductImage,
    ProductTag,
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


class AdminProductVariantSerializer(serializers.ModelSerializer):
    """Writable variant payload for the admin product form.

    DB-level unique validators are disabled so existing rows can be edited
    in place (a unique check against the whole table would reject a variant's
    own current SKU during an update). Uniqueness is re-checked in
    ``AdminProductSerializer.validate`` before saving.
    """

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
        extra_kwargs = {
            "sku": {"validators": []},
            "barcode": {"validators": []},
        }


class AdminTagField(serializers.ListField):
    """A product's tags as objects on read; tag-name strings on write.

    Read → ``[{id, name, slug}, ...]``; Write → list of tag names. Missing
    tags are auto-created in ``AdminProductSerializer`` when saving.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("child", serializers.CharField(allow_blank=False))
        kwargs.setdefault("required", False)
        super().__init__(*args, **kwargs)

    def to_representation(self, value):
        return [
            {"id": pt.tag_id, "name": pt.tag.name, "slug": pt.tag.slug}
            for pt in value.all()
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

    The full product record the customer sees is manageable here too:
    ingredients, nutritional info, brand, SKU, freshness, variants (size/weight)
    and tags are all writable. Variants and tags are synced against the
    existing ``ProductVariant`` / ``Tag`` / ``ProductTag`` models on save.
    """

    subcategory_name = serializers.CharField(source="subcategory.name", read_only=True)
    category = serializers.IntegerField(source="subcategory.category_id", read_only=True)
    category_name = serializers.CharField(source="subcategory.category.name", read_only=True)
    selling_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True, source="effective_price"
    )
    is_available = serializers.BooleanField(default=True, required=False)
    images = ProductImageSerializer(many=True, read_only=True)
    variants = AdminProductVariantSerializer(many=True, required=False)
    tags = AdminTagField(source="product_tags")
    ingredients = serializers.CharField(required=False, allow_blank=True)
    nutritional_info = serializers.JSONField(required=False, allow_null=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "pid",
            "name",
            "slug",
            "description",
            "ingredients",
            "nutritional_info",
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
            "tags",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["slug", "created_at", "updated_at"]
        extra_kwargs = {
            "sku": {"validators": []},
        }

    def validate_nutritional_info(self, value):
        if value is None or isinstance(value, dict):
            return value
        raise serializers.ValidationError("Nutritional info must be a JSON object.")

    def validate_sku(self, value):
        value = (value or "").strip()
        if not value:
            return ""
        qs = Product.objects.filter(sku=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A product with this SKU already exists.")
        return value

    def validate_variants(self, variants):
        skus = [v.get("sku") for v in variants if v.get("sku")]
        dupes = {sku for sku in skus if skus.count(sku) > 1}
        if dupes:
            raise serializers.ValidationError(
                "Variant SKUs must be unique within the product."
            )
        submitted_ids = [v.get("id") for v in variants if v.get("id")]
        for sku in skus:
            existing = ProductVariant.objects.filter(sku=sku)
            if submitted_ids:
                existing = existing.exclude(id__in=submitted_ids)
            if existing.exists():
                raise serializers.ValidationError(f"Variant SKU '{sku}' is already in use.")
        return variants

    def create(self, validated_data):
        variants_data = validated_data.pop("variants", [])
        tags = validated_data.pop("product_tags", [])
        product = Product.objects.create(**validated_data)
        if not product.sku:
            product.sku = self._make_unique_sku(product)
            product.save(update_fields=["sku"])
        if not product.slug:
            product.slug = self._make_unique_slug(product)
            product.save(update_fields=["slug"])
        self._sync_variants(product, variants_data)
        self._sync_tags(product, tags)
        return product

    def update(self, instance, validated_data):
        variants_data = validated_data.pop("variants", None)
        tags = validated_data.pop("product_tags", None)
        instance = super().update(instance, validated_data)
        if not instance.sku:
            instance.sku = self._make_unique_sku(instance)
            instance.save(update_fields=["sku"])
        if not instance.slug:
            instance.slug = self._make_unique_slug(instance)
            instance.save(update_fields=["slug"])
        if variants_data is not None:
            self._sync_variants(instance, variants_data)
        if tags is not None:
            self._sync_tags(instance, tags)
        return instance

    @staticmethod
    def _make_unique_sku(product: Product) -> str:
        base = f"SKU-{product.pk}"
        sku = base
        n = 1
        while Product.objects.filter(sku=sku).exists():
            n += 1
            sku = f"{base}-{n}"
        return sku

    @staticmethod
    def _make_unique_slug(product: Product) -> str:
        base = slugify(product.name) or f"product-{product.pk}"
        slug = base
        n = 1
        while Product.objects.filter(slug=slug).exists():
            n += 1
            slug = f"{base}-{n}"
        return slug

    @staticmethod
    def _get_or_create_tag(name: str) -> Tag:
        existing = Tag.objects.filter(name__iexact=name).first()
        if existing:
            return existing
        base = slugify(name) or f"tag-{name}"
        slug = base
        n = 1
        while Tag.objects.filter(slug=slug).exists():
            n += 1
            slug = f"{base}-{n}"
        return Tag.objects.create(name=name, slug=slug)

    @classmethod
    def _sync_variants(cls, product: Product, variants_data):
        submitted_ids = set()
        for data in variants_data:
            data = dict(data)
            variant_id = data.pop("id", None)
            if variant_id:
                variant = product.variants.filter(pk=variant_id).first()
                if variant:
                    for field, value in data.items():
                        setattr(variant, field, value)
                    variant.save()
                    submitted_ids.add(variant_id)
                    continue
            created = ProductVariant.objects.create(product=product, **data)
            submitted_ids.add(created.id)
        for variant in product.variants.all():
            if variant.id not in submitted_ids:
                try:
                    variant.delete()
                except ProtectedError:
                    pass

    @classmethod
    def _sync_tags(cls, product: Product, tag_names):
        product.product_tags.all().delete()
        for name in tag_names:
            tag = cls._get_or_create_tag(name)
            ProductTag.objects.get_or_create(product=product, tag=tag)
