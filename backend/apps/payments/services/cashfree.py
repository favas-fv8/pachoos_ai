"""Cashfree payment service — order creation, verification, and idempotent confirmation."""
import hashlib
import hmac
import logging

from django.conf import settings

from apps.orders.models import Order
from apps.orders.services import mark_payment_failed, mark_payment_successful
from apps.payments.gateway import CashfreeGateway

logger = logging.getLogger("apps.payments")


def _gateway() -> CashfreeGateway:
    return CashfreeGateway()


def initiate_cashfree_payment(
    order: Order,
    customer_email: str = "",
    customer_phone: str = "",
) -> dict:
    """Create a Cashfree order and return the payment session for frontend checkout.

    Returns::

        {
            "success": True,
            "cf_order_id": str,
            "payment_session_id": str,
            "order_status": str,
        }

    Raises ``ValueError`` on failure.
    """
    gw = _gateway()
    result = gw.create_order(order, customer_email=customer_email, customer_phone=customer_phone)
    logger.info(
        "Cashfree order created: cf_order_id=%s order_id=%s status=%s",
        result["cf_order_id"],
        order.id,
        result["order_status"],
    )
    return result


def verify_cashfree_payment(order_id: str) -> dict:
    """Verify payment status with Cashfree API.

    Args:
        order_id: The merchant's order ID (the UUID sent during order creation).

    Returns the raw verification result from the gateway.
    """
    gw = _gateway()
    return gw.verify_payment(order_id)


TERMINAL_PAYMENT_FAILURES = ("FAILED", "USER_DROPPED", "CANCELLED", "VOID")
TERMINAL_ORDER_FAILURES = ("EXPIRED", "TERMINATED")


def confirm_cashfree_payment(order: Order, order_id: str = "") -> dict:
    """Verify with Cashfree and idempotently confirm or fail the order.

    This is the single entry point for both webhook and return-URL flows.
    It is safe to call multiple times (double-click, page refresh, webhook
    racing the return URL).

    Args:
        order: The Order instance.
        order_id: The merchant's order ID to verify with Cashfree.
                  Defaults to ``str(order.id)`` if not provided.

    Returns::

        {
            "success": bool,
            "paid": bool,
            "message": str,
            "payment": Payment | None,
            "order": Order,
            "cf_order_status": str,
            "cf_payment_status": str,
        }
    """
    if not order_id:
        order_id = str(order.id)

    verification = verify_cashfree_payment(order_id)

    cf_order_status = verification.get("order_status", "")
    cf_payment_status = verification.get("payment_status", "")

    if not verification.get("success"):
        logger.warning("Cashfree verification API failed for order_id=%s", order_id)
        return {
            "success": False,
            "paid": False,
            "message": "Unable to verify payment with Cashfree. Please try again.",
            "payment": None,
            "order": order,
            "cf_order_status": "",
            "cf_payment_status": "",
        }

    if verification.get("paid"):
        cf_order_id = verification.get("cf_order_id", "")
        payment = mark_payment_successful(
            order,
            method=verification.get("payment_method") or "upi",
            provider="cashfree",
            transaction_id=verification.get("transaction_id") or cf_order_id,
            is_demo=False,
            razorpay_order_id=cf_order_id,
            razorpay_payment_id=verification.get("transaction_id") or "",
            note="Cashfree payment confirmed",
        )
        logger.info(
            "Cashfree payment confirmed: order_id=%s cf_order_id=%s",
            order_id,
            cf_order_id,
        )
        return {
            "success": True,
            "paid": True,
            "message": "Payment successful.",
            "payment": payment,
            "order": order,
            "cf_order_status": cf_order_status,
            "cf_payment_status": cf_payment_status,
        }

    # Terminal order failure (EXPIRED / TERMINATED)
    if cf_order_status in TERMINAL_ORDER_FAILURES:
        payment = mark_payment_failed(
            order,
            method=verification.get("payment_method") or "upi",
            provider="cashfree",
            transaction_id=order_id,
            is_demo=False,
            reason=f"Cashfree order {cf_order_status}",
        )
        return {
            "success": True,
            "paid": False,
            "message": "Payment was not completed.",
            "payment": payment,
            "order": order,
            "cf_order_status": cf_order_status,
            "cf_payment_status": cf_payment_status,
        }

    # Terminal payment failure (FAILED / USER_DROPPED / CANCELLED / VOID)
    if cf_payment_status in TERMINAL_PAYMENT_FAILURES:
        payment = mark_payment_failed(
            order,
            method=verification.get("payment_method") or "upi",
            provider="cashfree",
            transaction_id=verification.get("transaction_id") or order_id,
            is_demo=False,
            reason=f"Cashfree payment {cf_payment_status}",
        )
        return {
            "success": True,
            "paid": False,
            "message": "Payment was not completed.",
            "payment": payment,
            "order": order,
            "cf_order_status": cf_order_status,
            "cf_payment_status": cf_payment_status,
        }

    # Genuinely pending — not terminal yet
    return {
        "success": True,
        "paid": False,
        "message": "Payment is still processing. Please wait or check back later.",
        "payment": None,
        "order": order,
        "cf_order_status": cf_order_status,
        "cf_payment_status": cf_payment_status,
    }


def verify_cashfree_webhook_signature(request_body: bytes, request_headers: dict) -> bool:
    """Verify the Cashfree webhook signature using the webhook secret.

    Cashfree sends ``x-webhook-signature`` and ``x-webhook-timestamp`` headers.
    The signature is HMAC-SHA256 of ``timestamp + body`` using the secret key.

    In sandbox mode with no webhook secret configured, this returns True.
    """
    webhook_secret = getattr(settings, "CF_WEBHOOK_SECRET", "")
    if not webhook_secret:
        # Sandbox mode — skip verification if no secret is configured
        return True

    signature = request_headers.get("x-webhook-signature", "")
    timestamp = request_headers.get("x-webhook-timestamp", "")

    if not signature or not timestamp:
        return False

    payload = timestamp.encode() + request_body
    expected = hmac.new(
        webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(signature, expected)


def handle_cashfree_webhook(payload: dict, request_body: bytes, request_headers: dict) -> dict:
    """Process a Cashfree webhook event.

    Returns::

        {"handled": bool, "message": str}
    """
    if not verify_cashfree_webhook_signature(request_body, request_headers):
        logger.warning("Cashfree webhook signature verification failed")
        return {"handled": False, "message": "Invalid webhook signature"}

    event_type = payload.get("type", "")
    data = payload.get("object", {})
    cf_order_id = data.get("cf_order_id", "")
    order_id = data.get("order_id", "")
    order_status = data.get("order_status", "")

    logger.info(
        "Cashfree webhook received: type=%s cf_order_id=%s order_id=%s status=%s",
        event_type,
        cf_order_id,
        order_id,
        order_status,
    )

    if not order_id and not cf_order_id:
        return {"handled": False, "message": "No order_id or cf_order_id in webhook payload"}

    # ── Resolve the Order from the webhook identifiers ──────────────────
    from apps.payments.models import Payment

    order = None

    # Method 1: look up via cf_order_id → Payment → Order (most reliable)
    if cf_order_id:
        payment_lookup = Payment.objects.filter(
            razorpay_order_id=cf_order_id, provider="cashfree"
        ).first()
        if payment_lookup:
            order = payment_lookup.order

    # Method 2: order_id is the raw PACHOOS UUID (old / first-attempt format)
    if order is None and order_id:
        try:
            order = Order.objects.get(id=order_id)
        except (Order.DoesNotExist, ValueError, TypeError):
            pass

    # Method 3: order_id is "{uuid}-{suffix}" — strip the suffix
    if order is None and order_id and "-" in order_id:
        try:
            original_id = order_id.rsplit("-", 1)[0]
            order = Order.objects.get(id=original_id)
        except (Order.DoesNotExist, ValueError, TypeError):
            pass

    if order is None:
        logger.warning(
            "Cashfree webhook: Order not found for cf_order_id=%s order_id=%s",
            cf_order_id,
            order_id,
        )
        return {"handled": False, "message": "Order not found"}

    # If already paid, idempotent — just acknowledge
    if order.payment_status == "paid":
        return {"handled": True, "message": "Order already paid"}

    if event_type in ("PAYMENT_SUCCESS_WEBHOOK", "payment.captured"):
        result = confirm_cashfree_payment(order, order_id)
        return {"handled": True, "message": result["message"]}

    if event_type in ("PAYMENT_FAILED_WEBHOOK", "payment.failed"):
        mark_payment_failed(
            order,
            method="upi",
            provider="cashfree",
            transaction_id=cf_order_id,
            is_demo=False,
            reason=f"Cashfree webhook: {event_type}",
        )
        return {"handled": True, "message": "Payment failure recorded"}

    # Other events (e.g., PAYMENT_PENDING_WEBHOOK) — acknowledge but don't act
    return {"handled": True, "message": f"Event {event_type} acknowledged"}
