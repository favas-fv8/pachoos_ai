"""Order services — delivery rules, coupon/voucher engine, order placement."""
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.cart.models import Cart, CartItem
from apps.catalog.models import Product
from apps.orders.models import Order, OrderItem, OrderTimeline, Delivery
from apps.payments.models import Payment
from apps.wallet.models import WalletLedger, Voucher, VoucherRedemption
from apps.coupons.models import Coupon, CouponRedemption

BUSINESS = settings.BUSINESS


def calculate_delivery(
    subtotal: float, distance_km: float | None = None
) -> dict[str, Any]:
    """Calculate delivery charge based on business rules.

    Free if subtotal >= FREE_DELIVERY_MIN_ORDER AND distance <= FREE_DELIVERY_MAX_KM.
    Otherwise DELIVERY_CHARGE.
    """
    if distance_km is None:
        # In dev/testing, assume within free-delivery range.
        distance_km = 1.0

    if subtotal >= BUSINESS["FREE_DELIVERY_MIN_ORDER"] and distance_km <= BUSINESS["FREE_DELIVERY_MAX_KM"]:
        return {"delivery_charge": 0.0, "delivery_free": True, "distance_km": distance_km}

    return {
        "delivery_charge": BUSINESS["DELIVERY_CHARGE"],
        "delivery_free": False,
        "distance_km": distance_km,
    }


def calculate_tax(subtotal: float, gst_percent: float = 5.0) -> float:
    """Simple GST calculation."""
    return round(subtotal * (gst_percent / 100), 2)


def apply_coupon(subtotal: float, coupon_code: str | None, user_id: int) -> dict[str, Any]:
    """Validate and apply a coupon. Returns discount amount and coupon metadata."""
    if not coupon_code:
        return {"discount": 0, "coupon": None}

    try:
        coupon = Coupon.objects.get(code__iexact=coupon_code, is_active=True)
    except Coupon.DoesNotExist:
        raise ValueError("Invalid coupon code.")

    now = timezone.now()
    if coupon.valid_from and now < coupon.valid_from:
        raise ValueError("Coupon not yet valid.")
    if coupon.valid_to and now > coupon.valid_to:
        raise ValueError("Coupon has expired.")
    if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
        raise ValueError("Coupon usage limit reached.")

    # Per-user limit check
    if CouponRedemption.objects.filter(coupon=coupon, user_id=user_id).exists():
        raise ValueError("Coupon already used by this customer.")

    discount = 0.0
    if coupon.kind == "percent":
        discount = round(subtotal * (float(coupon.value) / 100), 2)
        if coupon.max_discount:
            discount = min(discount, float(coupon.max_discount))
    elif coupon.kind == "flat":
        discount = min(float(coupon.value), subtotal)
    elif coupon.kind == "bogo":
        # Buy one get one free — apply to the cheapest eligible item
        discount = round(subtotal / 2, 2)

    return {"discount": discount, "coupon": coupon}


def apply_voucher(subtotal: float, voucher_code: str | None, user_id: int) -> dict[str, Any]:
    """Validate and apply a voucher. Returns discount amount and voucher metadata."""
    if not voucher_code:
        return {"discount": 0, "voucher": None}

    try:
        voucher = Voucher.objects.get(
            code__iexact=voucher_code,
            status="active",
            user_id=user_id,
        )
    except Voucher.DoesNotExist:
        raise ValueError("Invalid or expired voucher.")

    if voucher.expires_at and timezone.now() > voucher.expires_at:
        raise ValueError("Voucher has expired.")

    discount = min(float(voucher.amount), subtotal)
    return {"discount": discount, "voucher": voucher}


@transaction.atomic
def place_order(
    cart: Cart,
    user: Any,
    delivery_address_id: int,
    distance_km: float | None = None,
    coupon_code: str | None = None,
    voucher_code: str | None = None,
    payment_method: str = "upi",
) -> Order:
    """Place an order from a cart. Atomic — rolls back on any failure."""
    if not cart.items.filter(is_active=True).exists():
        raise ValueError("Cart is empty.")

    # Verify stock for every item
    for item in cart.items.filter(is_active=True):
        variant = item.variant or item.product
        if variant.stock_quantity < item.quantity:
            raise ValueError(
                f"Insufficient stock for {variant.name} ({item.quantity} requested, {variant.stock_quantity} available)."
            )

    # Calculate totals
    subtotal = cart.subtotal
    delivery = calculate_delivery(subtotal, distance_km or 1.0)
    tax = calculate_tax(subtotal)

    coupon_discount = 0.0
    coupon = None
    if coupon_code:
        result = apply_coupon(subtotal, coupon_code, user.id)
        coupon_discount = result["discount"]
        coupon = result["coupon"]

    voucher_discount = 0.0
    voucher = None
    if voucher_code:
        result = apply_voucher(subtotal - coupon_discount, voucher_code, user.id)
        voucher_discount = result["discount"]
        voucher = result["voucher"]

    grand_total = max(
        0,
        subtotal - coupon_discount - voucher_discount + delivery["delivery_charge"] + tax,
    )

    # Create order — include sequence to avoid collision per user per day
    today = timezone.now().strftime('%Y%m%d')
    base_prefix = f"PCH-{today}-{user.id:04d}"
    existing_count = Order.objects.filter(
        order_number__startswith=base_prefix
    ).count()
    order_number = f"{base_prefix}-{existing_count + 1:02d}"
    order = Order.objects.create(
        shop=cart.shop,
        user=user,
        order_number=order_number,
        subtotal=subtotal,
        discount_total=coupon_discount + voucher_discount,
        delivery_charge=delivery["delivery_charge"],
        tax_total=tax,
        grand_total=grand_total,
        coupon_id=coupon.id if coupon else None,
        coupon_discount=coupon_discount,
        voucher_id=voucher.id if voucher else None,
        voucher_discount=voucher_discount,
        delivery_address_id=delivery_address_id,
        distance_km=delivery["distance_km"],
        delivery_free=delivery["delivery_free"],
        cashback_earned=round(grand_total / BUSINESS["CASHBACK_PER_INR"], 2),
    )

    # Create order items and deduct stock
    for item in cart.items.filter(is_active=True):
        variant = item.variant or item.product
        price = (
            variant.effective_price
            if variant
            else item.product.effective_price
        )
        discount_pct = item.discount_percent
        gst_pct = float(item.product.gst_percent) if hasattr(item.product, "gst_percent") else 0
        gst_amt = round((price * item.quantity) * (gst_pct / 100), 2)
        line_total = round(price * item.quantity - (price * item.quantity * (discount_pct / 100)), 2)

        OrderItem.objects.create(
            order=order,
            product=item.product,
            variant=variant if variant != item.product else None,
            product_name=item.product.name,
            variant_name=variant.name if variant and variant != item.product else "",
            quantity=item.quantity,
            unit_price=price,
            discount=discount_pct,
            gst_percent=gst_pct,
            gst_amount=gst_amt,
            line_total=line_total,
        )

        # Deduct stock — only from the actual inventory source
        if variant != item.product:
            variant.stock_quantity -= item.quantity
            variant.save(update_fields=["stock_quantity"])
        else:
            item.product.stock_quantity -= item.quantity
            item.product.save(update_fields=["stock_quantity"])

        # Stock movement
        from apps.catalog.models import StockMovement
        StockMovement.objects.create(
            product=item.product,
            variant=variant if variant != item.product else None,
            quantity=-item.quantity,
            reason="sale",
            ref_order_id=order.id,
            note=f"Order #{order.order_number}",
        )

    # Record timeline
    OrderTimeline.objects.create(
        order=order,
        status="pending",
        note="Order placed",
        actor_user=user,
        actor_role=user.role,
    )

    # Clear cart
    cart.items.all().delete()
    cart.is_active = False
    cart.save(update_fields=["is_active"])

    return order


@transaction.atomic
def record_payment(order: Order, payment_data: dict) -> Payment:
    """Record a payment for an order."""
    payment = Payment.objects.create(
        order=order,
        user=order.user,
        razorpay_order_id=payment_data.get("razorpay_order_id", ""),
        razorpay_payment_id=payment_data.get("razorpay_payment_id", ""),
        razorpay_signature=payment_data.get("razorpay_signature", ""),
        method=payment_data.get("method", "upi"),
        amount=order.grand_total,
        status="captured" if payment_data.get("status") == "authorized" else "created",
        webhook_received_at=timezone.now(),
        webhook_verified=True,
        raw_response=payment_data,
    )

    # Update order status
    order.status = "accepted"
    order.save(update_fields=["status"])

    # Record timeline
    OrderTimeline.objects.create(
        order=order,
        status="accepted",
        note="Payment received",
    )

    # Credit cashback and auto-mint voucher
    from apps.wallet.services import credit_cashback
    credit_cashback(order)

    # Trigger async voucher minting (eager in dev mode)
    from apps.wallet.tasks import mint_voucher_for_user
    mint_voucher_for_user.delay(order.user.id, order.shop_id)

    return payment