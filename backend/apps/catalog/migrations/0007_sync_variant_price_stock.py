"""Sync variant price/discount/stock to the product-level values.

The admin-defined product price (base_price / discount_percent) and stock are
the single source of truth; variants are size/weight options that share them.
This brings existing rows in line so /shop immediately shows the admin price.
"""
from django.db import migrations


def sync_variants_to_product(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    ProductVariant = apps.get_model("catalog", "ProductVariant")
    for product in Product.objects.all():
        ProductVariant.objects.filter(product=product).update(
            price=product.base_price,
            discount_percent=product.discount_percent,
            stock_quantity=product.stock_quantity,
        )


def unsync(apps, schema_editor):
    # No meaningful reverse: previous per-variant prices are not recoverable.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0006_wishlist"),
    ]

    operations = [
        migrations.RunPython(sync_variants_to_product, unsync),
    ]
