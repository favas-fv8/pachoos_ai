"""Seed demo catalog data — categories, subcategories, products, variants."""
from django.core.management.base import BaseCommand

from apps.catalog.models import Category, Subcategory, Product, ProductVariant, ProductImage, Tag, ProductTag
from apps.shops.models import Shop


class Command(BaseCommand):
    help = "Seed demo catalog data for PACHOOS."

    def handle(self, *args, **options):
        shop = Shop.objects.filter(slug="pachoos").first()
        if not shop:
            self.stdout.write(self.style.ERROR("No primary shop found — run seed_demo first."))
            return

        self.stdout.write(self.style.NOTICE(f"Seeding catalog for shop: {shop.name}"))

        # --- Categories ---
        bakery, _ = Category.objects.get_or_create(
            slug="bakery",
            defaults={"name": "Bakery", "is_active": True},
        )
        fruits, _ = Category.objects.get_or_create(
            slug="fruits",
            defaults={"name": "Fruits", "is_active": True},
        )

        # --- Subcategories ---
        cakes, _ = Subcategory.objects.get_or_create(
            category=bakery, slug="cakes", defaults={"name": "Cakes"}
        )
        bread, _ = Subcategory.objects.get_or_create(
            category=bakery, slug="bread", defaults={"name": "Bread"}
        )
        cookies, _ = Subcategory.objects.get_or_create(
            category=bakery, slug="cookies", defaults={"name": "Cookies"}
        )
        apples, _ = Subcategory.objects.get_or_create(
            category=fruits, slug="apples", defaults={"name": "Apples"}
        )
        mangoes, _ = Subcategory.objects.get_or_create(
            category=fruits, slug="mangoes", defaults={"name": "Mangoes"}
        )
        grapes, _ = Subcategory.objects.get_or_create(
            category=fruits, slug="grapes", defaults={"name": "Grapes"}
        )

        # --- Tags ---
        fresh_tag, _ = Tag.objects.get_or_create(slug="fresh", defaults={"name": "Fresh"})
        seasonal_tag, _ = Tag.objects.get_or_create(slug="seasonal", defaults={"name": "Seasonal"})
        organic_tag, _ = Tag.objects.get_or_create(slug="organic", defaults={"name": "Organic"})
        best_seller_tag, _ = Tag.objects.get_or_create(slug="best-seller", defaults={"name": "Best Seller"})

        # --- Products ---
        def make_product(subcategory, name, slug, base_price, discount=0, freshness="fresh",
                         stock=50, is_available=True, is_featured=False, tags=None):
            product, _ = Product.objects.get_or_create(
                slug=slug,
                defaults={
                    "subcategory": subcategory,
                    "name": name,
                    "base_price": base_price,
                    "discount_percent": discount,
                    "freshness": freshness,
                    "stock_quantity": stock,
                    "is_available": is_available,
                    "is_featured": is_featured,
                },
            )
            if not product.sku:
                product.sku = f"SKU-{product.pk}-{slug[:10].upper()}"
                product.save(update_fields=["sku"])
            if tags:
                for tag_slug in tags:
                    tag, _ = Tag.objects.get_or_create(slug=tag_slug)
                    ProductTag.objects.get_or_create(product=product, tag=tag)
            return product

        def make_variant(product, name, price, stock, sku=""):
            ProductVariant.objects.get_or_create(
                product=product,
                name=name,
                defaults={
                    "price": price,
                    "stock_quantity": stock,
                    "sku": sku or f"{product.sku}-{name.lower().replace(' ', '-')}",
                },
            )

        # Bakery products
        chocolate_cake = make_product(
            cakes, "Chocolate Cake", "chocolate-cake", 399.00, discount=10,
            freshness="bakery", stock=20, is_featured=True, tags=["fresh", "best-seller"],
        )
        make_variant(chocolate_cake, "500g", 399.00, 10, "CAKE-CHOC-500")
        make_variant(chocolate_cake, "1kg", 749.00, 5, "CAKE-CHOC-1KG")
        make_variant(chocolate_cake, "2kg", 1399.00, 3, "CAKE-CHOC-2KG")

        vanilla_cake = make_product(
            cakes, "Vanilla Sponge Cake", "vanilla-sponge-cake", 299.00, discount=5,
            freshness="bakery", stock=15, tags=["fresh"],
        )
        make_variant(vanilla_cake, "500g", 299.00, 8, "CAKE-VAN-500")
        make_variant(vanilla_cake, "1kg", 549.00, 4, "CAKE-VAN-1KG")

        croissant = make_product(
            bread, "Butter Croissant", "butter-croissant", 45.00,
            freshness="bakery", stock=40, tags=["fresh", "best-seller"],
        )
        make_variant(croissant, "Each", 45.00, 30, "BREAD-CROIS-EACH")
        make_variant(croissant, "Pack of 6", 250.00, 10, "BREAD-CROIS-6PK")

        sourdough = make_product(
            bread, "Sourdough Loaf", "sourdough-loaf", 120.00,
            freshness="bakery", stock=25, tags=["fresh", "organic"],
        )
        make_variant(sourdough, "500g", 120.00, 12, "BREAD-SD-500")
        make_variant(sourdough, "1kg", 220.00, 6, "BREAD-SD-1KG")

        chocolate_chip = make_product(
            cookies, "Chocolate Chip Cookies", "chocolate-chip-cookies", 199.00, discount=15,
            freshness="bakery", stock=30, tags=["fresh"],
        )
        make_variant(chocolate_chip, "250g", 199.00, 15, "COOK-CC-250")
        make_variant(chocolate_chip, "500g", 349.00, 8, "COOK-CC-500")

        # Fruit products
        gala_apple = make_product(
            apples, "Gala Apples", "gala-apples", 199.00, discount=0,
            freshness="fresh", stock=100, tags=["fresh", "organic"],
        )
        make_variant(gala_apple, "1 kg", 199.00, 40, "FRUIT-GALA-1KG")
        make_variant(gala_apple, "500 g", 110.00, 20, "FRUIT-GALA-500")

        alphonso_mango = make_product(
            mangoes, "Alphonso Mango", "alphonso-mango", 299.00, discount=10,
            freshness="fresh", stock=60, is_featured=True, tags=["fresh", "seasonal", "best-seller"],
        )
        make_variant(alphonso_mango, "1 kg", 299.00, 25, "FRUIT-ALPH-1KG")
        make_variant(alphonso_mango, "500 g", 169.00, 15, "FRUIT-ALPH-500")

        red_grapes = make_product(
            grapes, "Red Grapes", "red-grapes", 149.00, discount=0,
            freshness="fresh", stock=50, tags=["fresh", "organic"],
        )
        make_variant(red_grapes, "1 kg", 149.00, 20, "FRUIT-RED-1KG")
        make_variant(red_grapes, "500 g", 85.00, 10, "FRUIT-RED-500")

        # Product images (placeholder URLs)
        for product in Product.objects.all():
            ProductImage.objects.get_or_create(
                product=product,
                defaults={
                    "image_url": f"https://pachoos-cdn.example.com/products/{product.slug}.jpg",
                    "alt_text": product.name,
                    "is_primary": True,
                },
            )

        self.stdout.write(self.style.SUCCESS(f"Seeded {Product.objects.count()} products across {Category.objects.count()} categories."))