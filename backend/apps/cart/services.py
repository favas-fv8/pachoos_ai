"""Cart services — server-side pricing, totals and stock validation.

Every money value the cart / checkout pages show is recomputed here (and again
in :func:`apps.orders.services.place_order`) — frontend totals are never
trusted. Product/variant discount is applied **exactly once** via
``effective_price``; ``discount_percent`` on a cart line is never re-applied
(this was the old double-discount bug).
"""
from typing import Any

from apps.cart.models import Cart, CartItem
from apps.orders.services import (
    apply_coupon,
    apply_voucher,
    calculate_delivery,
)


def item_base_price(item: CartItem) -> float:
    """List (pre-discount) price of a cart line."""
    return float(item.variant.price if item.variant else item.product.base_price)


def compute_cart_summary(
    cart: Cart,
    *,
    coupon_code: str | None = None,
    voucher_code: str | None = None,
    distance_km: float | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Compute the full server-side cart summary (never trusts the client).

    Returns item breakdown, subtotal (effective prices), product discount,
    coupon/voucher discounts, GST (per product rate), delivery and grand total.
    Raises ``ValueError`` for invalid/expired coupon or voucher codes.
    """
    items = list(cart.items.select_related("product", "variant"))

    base_subtotal = 0.0
    subtotal = 0.0
    product_discount = 0.0
    tax = 0.0
    line_items = []

    for item in items:
        price = item.effective_price
        base = item_base_price(item)
        qty = item.quantity
        line = round(price * qty, 2)
        base_line = round(base * qty, 2)
        base_subtotal += base_line
        subtotal += line
        product_discount += base_line - line
        gst_pct = float(item.product.gst_percent or 0)
        tax += round(line * gst_pct / 100, 2)

        line_items.append(
            {
                "id": item.id,
                "product": item.product_id,
                "variant": item.variant_id,
                "product_name": item.product.name,
                "product_slug": item.product.slug,
                "variant_name": item.variant.name if item.variant else "",
                "quantity": qty,
                "unit": item.product.stock_unit or "count",
                "unit_price": round(price, 2),
                "base_price": round(base, 2),
                "discount_percent": (
                    float(item.variant.discount_percent)
                    if item.variant
                    else float(item.product.discount_percent)
                ),
                "line_total": line,
                "image_url": _primary_image_url(item.product),
            }
        )

    subtotal = round(subtotal, 2)
    product_discount = round(product_discount, 2)
    tax = round(tax, 2)

    delivery = calculate_delivery(subtotal, distance_km)

    coupon_discount = 0.0
    coupon_id = None
    if coupon_code and user_id:
        result = apply_coupon(subtotal, coupon_code, user_id)
        coupon_discount = result["discount"]
        coupon_id = result["coupon"].id if result["coupon"] else None

    voucher_discount = 0.0
    voucher_id = None
    if voucher_code and user_id:
        result = apply_voucher(subtotal - coupon_discount, voucher_code, user_id)
        voucher_discount = result["discount"]
        voucher_id = result["voucher"].id if result["voucher"] else None

    grand_total = round(
        max(
            0.0,
            subtotal - coupon_discount - voucher_discount
            + delivery["delivery_charge"]
            + tax,
        ),
        2,
    )

    return {
        "items": line_items,
        "item_count": len(line_items),
        "subtotal": subtotal,
        "base_subtotal": round(base_subtotal, 2),
        "product_discount": product_discount,
        "coupon_discount": coupon_discount,
        "coupon_id": coupon_id,
        "voucher_discount": voucher_discount,
        "voucher_id": voucher_id,
        "discount_total": round(product_discount + coupon_discount + voucher_discount, 2),
        "delivery_charge": delivery["delivery_charge"],
        "delivery_free": delivery["delivery_free"],
        "distance_km": delivery["distance_km"],
        "tax_total": tax,
        "grand_total": grand_total,
    }


def _primary_image_url(product) -> str | None:
    img = product.images.filter(is_primary=True).first() or product.images.first()
    return img.resolved_url if img else None
