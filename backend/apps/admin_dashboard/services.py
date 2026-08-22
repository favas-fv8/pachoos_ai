"""Admin dashboard services — stats, reports, inventory alerts."""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from apps.admin_dashboard.activity import record_admin_activity

# Low-stock rule: a product is "low" when its stock is at or below this value
# (applies to both kg and count units). Kept independent from each product's
# admin-configured restock threshold so dashboard alerts follow one consistent
# business rule and update automatically as stock changes.
LOW_STOCK_THRESHOLD = 3


def get_customer_order_stats(user) -> dict:
    """Live order stats for a customer, from their actual order data.

    Shared by the customer list and detail endpoints so both always agree:
    ``order_count`` counts every order placed; ``total_spent`` sums the
    grand totals of orders actually paid.
    """
    from apps.orders.models import Order

    stats = Order.objects.filter(user=user).aggregate(
        order_count=Count("id"),
        total_spent=Sum("grand_total", filter=Q(payment_status="paid")),
    )
    return {
        "order_count": stats["order_count"] or 0,
        "total_spent": str(stats["total_spent"] or Decimal("0.00")),
    }


def get_dashboard_stats(shop=None) -> dict:
    """Get high-level dashboard stats."""
    from apps.accounts.models import User
    from apps.catalog.models import Product
    from apps.orders.models import Order

    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)
    # Current calendar month start (local time) — monthly figures reset
    # automatically when a new month begins. Historical data is untouched.
    month_start = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    order_qs = Order.objects.all()
    if shop:
        order_qs = order_qs.filter(shop=shop)

    # Revenue
    total_revenue = order_qs.filter(
        status__in=["accepted", "preparing", "packed", "out_for_delivery", "delivered"]
    ).aggregate(total=Sum("grand_total"))["total"] or Decimal("0.00")

    # Monthly figures cover ONLY the current calendar month and ONLY orders
    # whose payment actually succeeded — failed / pending / dropped payments
    # never count toward revenue or order volume.
    monthly_revenue = order_qs.filter(
        created_at__gte=month_start,
        payment_status="paid",
    ).aggregate(total=Sum("grand_total"))["total"] or Decimal("0.00")

    weekly_revenue = order_qs.filter(
        created_at__gte=seven_days_ago,
        status__in=["accepted", "preparing", "packed", "out_for_delivery", "delivered"],
    ).aggregate(total=Sum("grand_total"))["total"] or Decimal("0.00")

    # Orders
    total_orders = order_qs.count()
    monthly_orders = order_qs.filter(
        created_at__gte=month_start, payment_status="paid"
    ).count()
    pending_orders = order_qs.filter(status="pending").count()

    # Customers
    # Same predicate as the /admin/customers list (active, non-staff) so both
    # surfaces always show the same count.
    total_customers = User.objects.filter(is_staff=False, is_active=True).count()
    new_customers_month = User.objects.filter(
        is_staff=False, created_at__gte=month_start
    ).count()

    # Products
    total_products = Product.objects.count()
    low_stock_count = Product.objects.filter(
        stock_quantity__lte=LOW_STOCK_THRESHOLD, is_available=True
    ).count()

    # Average order value
    avg_order = order_qs.filter(
        status__in=["accepted", "preparing", "packed", "out_for_delivery", "delivered"],
        created_at__gte=thirty_days_ago,
    ).aggregate(avg=Avg("grand_total"))["avg"] or Decimal("0.00")

    return {
        "revenue": {
            "total": str(total_revenue),
            "monthly": str(monthly_revenue),
            "weekly": str(weekly_revenue),
        },
        "orders": {
            "total": total_orders,
            "monthly": monthly_orders,
            "pending": pending_orders,
        },
        "customers": {
            "total": total_customers,
            "new_this_month": new_customers_month,
        },
        "products": {
            "total": total_products,
            "low_stock": low_stock_count,
        },
        "avg_order_value": str(avg_order),
    }


def get_revenue_chart(shop=None, days: int = 30, month: bool = False) -> list:
    """Get daily revenue data for chart.

    ``month=True`` returns daily revenue for the **current calendar month**
    (resets automatically on the 1st) counting only successfully paid orders —
    the same basis as the Monthly Revenue stat card. Otherwise the historical
    trailing ``days`` window is used unchanged.
    """
    from django.db.models.functions import TruncDate

    from apps.orders.models import Order

    now = timezone.now()

    qs = Order.objects.all()
    if month:
        start = timezone.localtime().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        qs = qs.filter(created_at__gte=start, payment_status="paid")
    else:
        start = now - timedelta(days=days)
        qs = qs.filter(
            created_at__gte=start,
            status__in=["accepted", "preparing", "packed", "out_for_delivery", "delivered"],
        )
    if shop:
        qs = qs.filter(shop=shop)

    daily = (
        qs.annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(revenue=Sum("grand_total"), count=Count("id"))
        .order_by("date")
    )

    return [
        {"date": str(d["date"]), "revenue": str(d["revenue"]), "orders": d["count"]}
        for d in daily
    ]


def get_top_products(shop=None, limit: int = 10) -> list:
    """Get top-selling products."""
    from apps.catalog.models import Product

    products = Product.objects.annotate(
        total_sold=Sum("order_items__quantity"),
        total_revenue=Sum("order_items__line_total"),
    ).filter(
        total_sold__isnull=False,
    ).order_by("-total_sold")[:limit]

    return [
        {
            "id": str(p.id),
            "name": p.name,
            "total_sold": p.total_sold or 0,
            "total_revenue": str(p.total_revenue or 0),
            "avg_rating": str(p.avg_rating),
            "stock_quantity": p.stock_quantity,
        }
        for p in products
    ]


def get_low_stock_products(shop=None) -> list:
    """Get products running low on stock (at or below LOW_STOCK_THRESHOLD)."""
    from apps.catalog.models import Product

    qs = Product.objects.filter(
        is_available=True,
        stock_quantity__lte=LOW_STOCK_THRESHOLD,
    ).order_by("stock_quantity")

    return [
        {
            "id": str(p.id),
            "name": p.name,
            "stock_quantity": p.stock_quantity,
            "stock_unit": p.stock_unit,
        }
        for p in qs
    ]


def get_recent_orders(shop=None, limit: int = 20) -> list:
    """Get recent orders (latest first)."""
    from apps.orders.models import Order

    # Filter BEFORE slicing — Django cannot filter a sliced queryset, and
    # doing so raised TypeError → 500 → "Failed to load dashboard data".
    qs = Order.objects.select_related("user").order_by("-created_at")
    if shop:
        qs = qs.filter(shop=shop)
    return [
        {
            "id": str(o.id),
            "order_number": o.order_number,
            "user_name": o.user.full_name,
            "user_phone": o.user.phone or "",
            "status": o.status,
            "grand_total": str(o.grand_total),
            "created_at": o.created_at.isoformat(),
        }
        for o in qs[:limit]
    ]


def get_customer_list(shop=None, limit: int = 50) -> list:
    """Get customer list with stats. Deleted (soft-deactivated) customers are
    hidden from the list; every financial record stays intact in the database.

    Uses the same stat definitions as :func:`get_customer_order_stats` so the
    list and the detail card always agree."""
    from apps.accounts.models import User

    customers = User.objects.filter(is_staff=False, is_active=True).annotate(
        order_count=Count("orders"),
        total_spent=Sum(
            "orders__grand_total", filter=Q(orders__payment_status="paid")
        ),
    ).order_by("-total_spent")[:limit]

    return [
        {
            "id": c.id,
            "full_name": c.full_name,
            "phone": c.phone or "",
            "email": c.email or "",
            "order_count": c.order_count,
            "total_spent": str(c.total_spent or Decimal("0.00")),
            "date_joined": c.created_at.isoformat(),
        }
        for c in customers
    ]


def get_customer_detail(customer_id: int) -> dict:
    """Get detailed customer info including the *complete linked Debt Book*.

    The Debt Book is the single source of truth for a customer's debt — whether
    it was created as a registered or an offline book later linked to the
    account. Its full serializer output (summary, transactions/bills/payments,
    history and notes) is embedded so admin and customer views always agree.
    """
    from apps.accounts.models import User
    from apps.orders.models import Order
    from apps.wallet.models import DebtBook
    from apps.wallet.serializers import DebtBookDetailSerializer

    user = User.objects.get(id=customer_id)
    orders = Order.objects.filter(user=user).order_by("-created_at")[:20]

    book = DebtBook.objects.filter(user=user).order_by("created_at").first()
    debt_book = DebtBookDetailSerializer(book).data if book else None

    order_stats = get_customer_order_stats(user)

    return {
        "id": user.id,
        "full_name": user.full_name,
        "phone": user.phone or "",
        "email": user.email or "",
        "role": user.role,
        "is_active": user.is_active,
        "date_joined": user.created_at.isoformat(),
        "last_login": user.last_login_at.isoformat() if user.last_login_at else None,
        "order_count": order_stats["order_count"],
        "total_spent": order_stats["total_spent"],
        "total_debt": debt_book["summary"]["outstanding"] if debt_book else "0.00",
        "debt_book_id": str(book.id) if book else None,
        "debt_book": debt_book,
        "orders": [
            {
                "id": str(o.id),
                "order_number": o.order_number,
                "status": o.status,
                "grand_total": str(o.grand_total),
                "created_at": o.created_at.isoformat(),
            }
            for o in orders
        ],
    }


def update_customer(customer_id: int, admin_user, request=None, **fields) -> "User":  # noqa: F821
    """Safely edit a customer's *profile* details (name, phone, email, active).

    Only ``full_name``, ``phone``, ``email`` and ``is_active`` are honoured —
    financial/debt data is never touched here. Phone (10 digits) and email are
    validated and deduped against other accounts before saving. Returns the
    refreshed customer.
    """

    from apps.accounts.models import User
    from apps.wallet.services import validate_email, validate_phone

    try:
        user = User.objects.get(id=customer_id)
    except User.DoesNotExist:
        raise ValueError("Customer not found.") from None

    if user.is_staff:
        raise ValueError("Staff accounts cannot be edited from the customer list.")

    before = {
        "full_name": user.full_name,
        "phone": user.phone,
        "email": user.email,
        "is_active": user.is_active,
    }
    updated = []
    if "full_name" in fields:
        name = (fields["full_name"] or "").strip()
        if not name:
            raise ValueError("Full name cannot be empty.")
        user.full_name = name
        updated.append("full_name")
    if "phone" in fields:
        phone = validate_phone(fields["phone"])
        dup = User.objects.filter(phone__endswith=phone).exclude(pk=user.pk).exists()
        if dup:
            raise ValueError("Another customer already uses this phone number.")
        user.phone = phone
        updated.append("phone")
    if "email" in fields:
        email = validate_email(fields["email"])
        dup = User.objects.filter(email=email).exclude(pk=user.pk).exists()
        if dup:
            raise ValueError("Another customer already uses this email address.")
        user.email = email
        updated.append("email")
    if "is_active" in fields:
        user.is_active = bool(fields["is_active"])
        updated.append("is_active")

    if updated:
        user.save(update_fields=updated + ["updated_at"])
        record_admin_activity(
            admin_user,
            action="customer.updated",
            entity_type="customer",
            entity_id=str(user.id),
            description=f"Edited customer {user.full_name or user.phone or user.email}",
            before={k: before[k] for k in updated},
            after={k: getattr(user, k) for k in updated},
            request=request,
        )
    return user


def deactivate_customer(customer_id: int, admin_user, request=None) -> "User":  # noqa: F821
    """Soft-delete a customer: deactivates the account so it disappears from
    active lists, while *all* financial/debt/order history remains intact and
    is never modified. Returns the deactivated customer.
    """
    from apps.accounts.models import User

    try:
        user = User.objects.get(id=customer_id)
    except User.DoesNotExist:
        raise ValueError("Customer not found.") from None

    if user.is_staff:
        raise ValueError("Staff accounts cannot be deleted.")

    record_admin_activity(
        admin_user,
        action="customer.deleted",
        entity_type="customer",
        entity_id=str(user.id),
        description=f"Deleted customer {user.full_name or user.phone or user.email}",
        before={"is_active": user.is_active,
                "phone": user.phone, "email": user.email},
        after={"is_active": False},
        request=request,
    )
    user.is_active = False
    user.save(update_fields=["is_active", "updated_at"])
    return user


def get_all_orders(shop=None, status_filter=None, limit: int = 50) -> list:
    """Get all orders with optional status filter."""
    from apps.orders.models import Order

    qs = Order.objects.select_related("user").order_by("-created_at")
    if shop:
        qs = qs.filter(shop=shop)
    if status_filter:
        qs = qs.filter(status=status_filter)

    return [
        {
            "id": str(o.id),
            "order_number": o.order_number,
            "user_name": o.user.full_name,
            "user_phone": o.user.phone or "",
            "status": o.status,
            "payment_status": o.payment_status,
            "payment_method": o.payment_method,
            "subtotal": str(o.subtotal),
            "discount_total": str(o.discount_total),
            "delivery_charge": str(o.delivery_charge),
            "tax_total": str(o.tax_total),
            "grand_total": str(o.grand_total),
            "cancellation_reason": o.cancellation_reason or "",
            "created_at": o.created_at.isoformat(),
        }
        for o in qs[:limit]
    ]


def get_order_detail(order_id) -> dict:
    """Get a full admin view of a single order: customer, payment, items,
    timeline and delivery. Every total comes from the order record so admin
    and customer views always agree."""
    from apps.orders.models import Delivery, Order, OrderTimeline
    from apps.payments.models import Payment

    try:
        order = Order.objects.select_related("user").get(id=order_id)
    except (Order.DoesNotExist, ValueError, TypeError):
        raise ValueError("Order not found.") from None

    payment = Payment.objects.filter(order=order).first()

    items = [
        {
            "product_id": str(i.product_id),
            "product_name": i.product.name,
            "variant_id": str(i.variant_id) if i.variant_id else None,
            "variant_name": i.variant.name if i.variant_id else "",
            "quantity": i.quantity,
            "unit_price": str(i.unit_price),
            "line_total": str(i.line_total),
            "tax_percent": str(i.gst_percent),
        }
        for i in order.items.select_related("product", "variant").all()
    ]

    timeline = [
        {
            "status": t.status,
            "note": t.note or "",
            "actor_role": t.actor_role,
            "created_at": t.created_at.isoformat(),
        }
        for t in OrderTimeline.objects.filter(order=order).order_by("created_at")
    ]

    delivery = None
    try:
        d = Delivery.objects.get(order=order)
        delivery = {
            "delivery_address": d.delivery_address,
            "distance_km": str(d.distance_km),
            "charge": str(d.charge),
            "status": d.status,
        }
    except Delivery.DoesNotExist:
        pass

    return {
        "id": str(order.id),
        "order_number": order.order_number,
        "customer": {
            "id": str(order.user.id),
            "full_name": order.user.full_name,
            "phone": order.user.phone or "",
            "email": order.user.email or "",
        },
        "status": order.status,
        "payment": {
            "status": order.payment_status,
            "method": order.payment_method,
            "provider": payment.provider if payment else "",
            "transaction_id": payment.transaction_id if payment else "",
            "is_demo": payment.is_demo if payment else False,
        },
        "totals": {
            "subtotal": str(order.subtotal),
            "discount_total": str(order.discount_total),
            "delivery_charge": str(order.delivery_charge),
            "delivery_free": order.delivery_free,
            "tax_total": str(order.tax_total),
            "grand_total": str(order.grand_total),
        },
        "items": items,
        "timeline": timeline,
        "delivery": delivery,
        "cancellation_reason": order.cancellation_reason or "",
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
    }
