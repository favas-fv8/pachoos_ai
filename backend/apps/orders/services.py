"""Order services — delivery rules, coupon/voucher engine, order placement.

Order lifecycle contract (Demo Payment):
  * ``place_order``            — snapshots the cart into an Order + OrderItems,
                                 consumes the coupon/voucher once and clears the
                                 cart. **No stock is deducted and no money is
                                 taken here.**
  * ``mark_payment_successful`` — idempotently confirms a paid payment: creates
                                 the Payment row, marks the order paid/accepted,
                                 deducts stock exactly once, writes the
                                 StockMovement ledger and credits cashback once.
  * ``mark_payment_failed``     — idempotently records a failed attempt; the
                                 order stays pending, stock is untouched.
"""
from decimal import Decimal
from math import asin, cos, isfinite, radians, sin, sqrt
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.cart.models import Cart
from apps.orders.models import Order, OrderItem, OrderTimeline
from apps.payments.models import Payment

BUSINESS = settings.BUSINESS

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two WGS84 points (straight line)."""
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlmb = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def parse_coordinate(value, *, lo: float, hi: float) -> float | None:
    """Coerce a client-supplied coordinate to a finite in-range float.

    Anything missing, malformed, non-finite or out of range becomes ``None``
    so callers can fall back to the "distance undetermined" path.
    """
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number):
        return None
    if number < lo or number > hi:
        return None
    return number


def resolve_delivery_distance(customer_lat, customer_lon, shop) -> float | None:
    """Straight-line km between the customer and the shop, rounded to 2dp.

    Returns ``None`` whenever either side is missing/invalid — the caller then
    applies the standard delivery charge and the UI explains why.
    """
    lat = parse_coordinate(customer_lat, lo=-90.0, hi=90.0)
    lon = parse_coordinate(customer_lon, lo=-180.0, hi=180.0)
    if lat is None or lon is None:
        return None
    if shop is None or shop.lat is None or shop.lng is None:
        return None
    try:
        distance = haversine_km(lat, lon, float(shop.lat), float(shop.lng))
    except (TypeError, ValueError):
        return None
    return round(distance, 2)


def _dec(value) -> Decimal:
    """Coerce a float summary value into a Decimal for model fields, so the
    in-memory attributes are the same type as what the DB stores."""
    return Decimal(str(value))


def calculate_delivery(distance_km: float | None = None) -> dict[str, Any]:
    """Delivery charge by straight-line distance only.

    Free within ``FREE_DELIVERY_MAX_KM``; flat ``DELIVERY_CHARGE`` beyond it.
    When the distance cannot be determined (missing coordinates) the flat
    charge applies — free delivery is never granted on an unknown distance.
    """
    if distance_km is not None and distance_km <= BUSINESS["FREE_DELIVERY_MAX_KM"]:
        return {"delivery_charge": 0.0, "delivery_free": True, "distance_km": distance_km}

    return {
        "delivery_charge": BUSINESS["DELIVERY_CHARGE"],
        "delivery_free": False,
        "distance_km": distance_km,
    }


def calculate_tax(subtotal: float, gst_percent: float = 5.0) -> float:
    """Simple GST calculation (flat rate helper)."""
    return round(subtotal * (gst_percent / 100), 2)


def apply_coupon(subtotal: float, coupon_code: str | None, user_id: int) -> dict[str, Any]:
    """Validate and apply a coupon. Returns discount amount and coupon metadata."""
    if not coupon_code:
        return {"discount": 0, "coupon": None}

    from apps.coupons.models import Coupon, CouponRedemption

    try:
        coupon = Coupon.objects.get(code__iexact=coupon_code, is_active=True)
    except Coupon.DoesNotExist:
        raise ValueError("Invalid coupon code.") from None

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

    from apps.wallet.models import Voucher

    try:
        voucher = Voucher.objects.get(
            code__iexact=voucher_code,
            status="active",
            user_id=user_id,
        )
    except Voucher.DoesNotExist:
        raise ValueError("Invalid or expired voucher.") from None

    if voucher.expires_at and timezone.now() > voucher.expires_at:
        raise ValueError("Voucher has expired.")

    discount = min(float(voucher.amount), subtotal)
    return {"discount": discount, "voucher": voucher}


def _next_order_number(shop_id: int) -> str:
    """Daily-per-shop order number, e.g. PCH-20260814-000001 (fits max_length=32)."""
    today = timezone.now().strftime("%Y%m%d")
    prefix = f"PCH-{today}-"
    count = Order.objects.filter(shop_id=shop_id, order_number__startswith=prefix).count()
    return f"{prefix}{count + 1:06d}"


@transaction.atomic
def place_order(
    cart: Cart,
    user: Any,
    delivery_address_id: int,
    customer_lat: float | None = None,
    customer_lon: float | None = None,
    coupon_code: str | None = None,
    voucher_code: str | None = None,
    payment_method: str = "upi",
) -> Order:
    """Place an order from a cart. Atomic — rolls back on any failure.

    The delivery distance is always computed server-side (haversine between
    the customer coordinates and the shop row) — a client-supplied distance is
    never trusted. Only snapshots the order; stock is deducted and cashback is
    credited when the payment is confirmed (see :func:`mark_payment_successful`).
    """
    if not cart.items.exists():
        raise ValueError("Cart is empty.")

    # Verify stock for every item at order time (soft reservation).
    for item in cart.items.select_related("product", "variant"):
        variant = item.variant or item.product
        if variant.stock_quantity < item.quantity:
            raise ValueError(
                f"Insufficient stock for {variant.name} ({item.quantity} requested, {variant.stock_quantity} available)."
            )

    from apps.cart.services import compute_cart_summary

    totals = compute_cart_summary(
        cart,
        coupon_code=coupon_code,
        voucher_code=voucher_code,
        customer_lat=customer_lat,
        customer_lon=customer_lon,
        user_id=user.id,
    )

    order = Order.objects.create(
        shop=cart.shop,
        user=user,
        order_number=_next_order_number(cart.shop_id),
        subtotal=_dec(totals["subtotal"]),
        discount_total=_dec(totals["discount_total"]),
        delivery_charge=_dec(totals["delivery_charge"]),
        tax_total=_dec(totals["tax_total"]),
        grand_total=_dec(totals["grand_total"]),
        coupon_id=totals["coupon_id"],
        coupon_discount=_dec(totals["coupon_discount"]),
        voucher_id=totals["voucher_id"],
        voucher_discount=_dec(totals["voucher_discount"]),
        delivery_address_id=delivery_address_id,
        distance_km=(
            _dec(totals["distance_km"]) if totals["distance_km"] is not None else None
        ),
        delivery_free=totals["delivery_free"],
        payment_method=payment_method,
        payment_status="pending",
        cashback_earned=_dec(
            round(totals["grand_total"] / BUSINESS["CASHBACK_PER_INR"], 2)
        ),
    )

    # Create order items — snapshot the effective (single-discount) price.
    for item in cart.items.select_related("product", "variant"):
        price = (
            item.variant.effective_price
            if item.variant_id
            else item.product.effective_price
        )
        gst_pct = float(item.product.gst_percent or 0)
        line_total = round(price * item.quantity, 2)
        OrderItem.objects.create(
            order=order,
            product=item.product,
            variant=item.variant if item.variant_id else None,
            product_name=item.product.name,
            variant_name=item.variant.name if item.variant_id else "",
            quantity=item.quantity,
            unit_price=_dec(price),
            discount=item.discount_percent,
            gst_percent=_dec(gst_pct),
            gst_amount=_dec(round(line_total * (gst_pct / 100), 2)),
            line_total=_dec(line_total),
        )

    # Consume coupon / voucher exactly once (order placed = reserved).
    _consume_coupon(totals["coupon_id"], user, order)
    _consume_voucher(order, totals["voucher_id"], totals["voucher_discount"], user)

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
    # Cart enforces one (user, is_active) row per state — purge this user's
    # stale deactivated carts first or flipping this one to is_active=False
    # raises an IntegrityError (500) on every order after the first.
    Cart.objects.filter(user=user, is_active=False).exclude(pk=cart.pk).delete()
    cart.is_active = False
    cart.save(update_fields=["is_active"])

    return order


def _consume_coupon(coupon_id, user, order) -> None:
    if not coupon_id:
        return
    from apps.coupons.models import Coupon, CouponRedemption

    coupon = Coupon.objects.filter(id=coupon_id).first()
    if coupon is None:
        return
    CouponRedemption.objects.create(coupon=coupon, order=order, user=user)
    coupon.used_count = (coupon.used_count or 0) + 1
    coupon.save(update_fields=["used_count"])


def _consume_voucher(order, voucher_id, discount, user) -> None:
    if not voucher_id:
        return
    from apps.wallet.models import Voucher, VoucherRedemption

    voucher = Voucher.objects.filter(id=voucher_id).first()
    if voucher is None:
        return
    voucher.status = "used"
    voucher.used_at = timezone.now()
    voucher.save(update_fields=["status", "used_at"])
    VoucherRedemption.objects.create(
        voucher=voucher,
        order=order,
        user=user,
        amount_used=discount,
    )


# ═════════════════════════════════════════════════════════════════════════════
# Payment confirmation (idempotent — safe on double-click / page refresh)
# ═════════════════════════════════════════════════════════════════════════════


def _paid_payment(order) -> Payment | None:
    return (
        Payment.objects.filter(order=order, status__in=["paid", "captured"]).first()
    )


@transaction.atomic
def mark_payment_successful(
    order: Order,
    *,
    method: str,
    provider: str = "demo",
    transaction_id: str = "",
    is_demo: bool = False,
    razorpay_order_id: str = "",
    razorpay_payment_id: str = "",
    razorpay_signature: str = "",
    note: str = "Payment received",
) -> Payment:
    """Idempotently confirm a successful payment for an order.

    Repeated calls (double-click "Pay Now", page refresh after success, or a
    webhook racing the client confirm) return the existing Payment and never
    double-charge, double-deduct stock or double-credit cashback.
    """
    if order.payment_status == "paid":
        existing = _paid_payment(order)
        if existing:
            return existing

    existing = Payment.objects.filter(order=order).first()
    if existing and existing.status in ("paid", "captured"):
        _apply_paid_order_state(order, existing)
        return existing

    if existing:
        # Upgrade a previously failed/created attempt to paid.
        existing.provider = provider
        existing.is_demo = is_demo
        existing.transaction_id = transaction_id
        existing.method = method
        existing.amount = order.payable_amount
        existing.status = "paid"
        existing.razorpay_order_id = razorpay_order_id or existing.razorpay_order_id
        existing.razorpay_payment_id = razorpay_payment_id or existing.razorpay_payment_id
        existing.razorpay_signature = razorpay_signature or existing.razorpay_signature
        existing.webhook_received_at = timezone.now()
        existing.webhook_verified = True
        existing.raw_response = {
            "provider": provider,
            "transaction_id": transaction_id,
            "method": method,
        }
        existing.save()
        payment = existing
    else:
        payment = Payment.objects.create(
            order=order,
            user=order.user,
            provider=provider,
            is_demo=is_demo,
            transaction_id=transaction_id,
            method=method,
            amount=order.payable_amount,
            status="paid",
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature,
            webhook_received_at=timezone.now(),
            webhook_verified=True,
            raw_response={
                "provider": provider,
                "transaction_id": transaction_id,
                "method": method,
            },
        )

    _apply_paid_order_state(order, payment)

    return payment


def _apply_paid_order_state(order: Order, payment: Payment) -> None:
    """Mark the order paid and apply stock/cashback side effects — once only."""
    order.payment_status = "paid"
    order.payment_method = payment.method
    if order.status == "pending":
        order.status = "accepted"
    order.save(update_fields=["payment_status", "payment_method", "status", "updated_at"])

    if not OrderTimeline.objects.filter(
        order=order, status="accepted", note__startswith="Payment"
    ).exists():
        OrderTimeline.objects.create(
            order=order,
            status="accepted",
            note="Payment received",
        )

    _deduct_stock_for_order(order)

    # Cashback credited exactly once after a successful payment.
    if order.cashback_credited_at is None:
        from apps.wallet.services import credit_cashback

        credit_cashback(order)

    # Deduct the cashback the customer applied to this order — success path
    # only (this function never runs for FAILED / PENDING / USER_DROPPED).
    if order.cashback_used_at is None:
        from apps.wallet.services import redeem_cashback_for_order

        redeem_cashback_for_order(order)


def _deduct_stock_for_order(order: Order) -> None:
    """Decrease stock for every order item and write the StockMovement ledger.

    Guarded by the immutable StockMovement ledger (one ``sale`` row per order),
    so stock is never deducted twice even if confirmation is retried.
    """
    from apps.catalog.models import StockMovement

    if StockMovement.objects.filter(ref_order_id=order.id, reason="sale").exists():
        return

    for item in order.items.select_related("product", "variant"):
        product = item.product
        if product.stock_quantity < item.quantity:
            # Never allow negative stock — surface so the caller can react.
            raise ValueError(
                f"Insufficient stock for {item.product_name} "
                f"({item.quantity} requested, {product.stock_quantity} available)."
            )
        product.stock_quantity -= item.quantity
        product.save(update_fields=["stock_quantity"])
        # Variants mirror the product-level count the admin manages, so
        # /shop and /admin/products stay synchronized after every sale.
        product.variants.update(stock_quantity=product.stock_quantity)

        StockMovement.objects.create(
            product=item.product,
            variant=item.variant if item.variant_id else None,
            quantity=-item.quantity,
            reason="sale",
            ref_order_id=order.id,
            note=f"Order #{order.order_number}",
        )


@transaction.atomic
def mark_payment_failed(
    order: Order,
    *,
    method: str = "upi",
    provider: str = "demo",
    transaction_id: str = "",
    is_demo: bool = True,
    reason: str = "",
) -> Payment | None:
    """Idempotently record a failed payment attempt.

    The order stays pending, stock is untouched and no cashback is credited.
    Returns the Payment row, or ``None`` if the order was already paid.
    """
    if order.payment_status == "paid":
        return None

    payment = Payment.objects.filter(order=order).first()
    if payment is None:
        payment = Payment.objects.create(
            order=order,
            user=order.user,
            provider=provider,
            is_demo=is_demo,
            transaction_id=transaction_id,
            method=method,
            amount=order.grand_total,
            status="failed",
            webhook_received_at=timezone.now(),
            raw_response={"reason": reason},
        )
    elif payment.status in ("paid", "captured"):
        return None
    else:
        payment.status = "failed"
        payment.attempts = (payment.attempts or 0) + 1
        payment.method = method or payment.method
        payment.save(update_fields=["status", "attempts", "method"])

    if order.payment_status == "pending":
        order.payment_status = "failed"
        order.payment_method = payment.method or order.payment_method
        order.save(update_fields=["payment_status", "payment_method"])

    OrderTimeline.objects.create(
        order=order,
        status="pending",
        note=reason or "Payment failed",
    )
    return payment


def record_payment(order: Order, payment_data: dict) -> Payment:
    """Record a successful Razorpay payment (webhook / verification path).

    Idempotent — delegates to :func:`mark_payment_successful`. Kept for the
    future real Razorpay integration; the demo flow uses the demo gateway.
    """
    return mark_payment_successful(
        order,
        method=payment_data.get("method", "upi"),
        provider="razorpay",
        transaction_id=payment_data.get("razorpay_payment_id", ""),
        is_demo=False,
        razorpay_order_id=payment_data.get("razorpay_order_id", ""),
        razorpay_payment_id=payment_data.get("razorpay_payment_id", ""),
        razorpay_signature=payment_data.get("razorpay_signature", ""),
    )
