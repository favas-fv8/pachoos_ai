"""Payment gateway abstraction — the seam for future real payments.

PACHOOS currently runs a clearly-labelled **Demo Payment** gateway that only
*simulates* a successful (or failed) payment — no real money ever moves. Every
gateway returns the same normalized result dict, so ``apps.payments.services``
and order confirmation stay gateway-agnostic.

To connect a real gateway later (Razorpay / UPI / cards):
  1. implement :class:`PaymentGateway` (see the Razorpay placeholder),
  2. register it in ``_GATEWAYS``,
  3. point the frontend at a real checkout flow and call the same
     ``mark_payment_successful`` / ``mark_payment_failed`` confirmers.
"""
import secrets
import uuid
from abc import ABC, abstractmethod


class PaymentGateway(ABC):
    provider: str = ""

    @abstractmethod
    def charge(self, order, *, method: str, **kwargs) -> dict:
        """Charge an order. Returns a normalized result dict::

            {
                "success": bool,
                "transaction_id": str,
                "method": str,
                "provider": str,
                "message": str,
            }
        """


class DemoPaymentGateway(PaymentGateway):
    """Simulated payment — clearly labelled, never a real charge."""

    provider = "demo"

    DEMO_METHODS = {
        "demo_upi": "Demo UPI",
        "demo_card": "Demo Card",
        "demo_gpay": "Demo GPay",
        "demo_phonepe": "Demo PhonePe",
        "demo_paytm": "Demo Paytm",
        "cod": "Cash on Delivery",
    }

    def charge(self, order, *, method: str = "demo_upi", simulate: str = "success", **kwargs):
        method = method if method in self.DEMO_METHODS else "demo_upi"
        transaction_id = f"DEMO-{secrets.token_hex(6).upper()}"
        if simulate == "fail":
            return {
                "success": False,
                "transaction_id": transaction_id,
                "method": method,
                "provider": self.provider,
                "message": "Simulated payment failed — no money was charged.",
            }
        return {
            "success": True,
            "transaction_id": transaction_id,
            "method": method,
            "provider": self.provider,
            "message": "Simulated payment succeeded (Demo Payment — no real charge).",
        }


class RazorpayGateway(PaymentGateway):
    """Placeholder for the real Razorpay integration (future).

    When Razorpay keys are configured this should create a Razorpay order and
    verify the webhook/checkout payload before returning ``success=True``.
    """

    provider = "razorpay"

    def charge(self, order, *, method: str = "upi", **kwargs):
        raise NotImplementedError("Razorpay gateway is not connected yet.")


class CashfreeGateway(PaymentGateway):
    """Cashfree PG v2 — real payment via Cashfree Sandbox or Production.

    Unlike demo/Razorpay charge(), Cashfree uses a redirect-based checkout:
      1. ``create_order()`` → returns ``payment_session_id``
      2. Frontend redirects user to Cashfree checkout
      3. User pays on Cashfree
      4. Cashfree redirects back → ``verify_payment()`` confirms the order

    The ``charge()`` method is provided for interface completeness but
    raises ``NotImplementedError`` — use ``create_order`` + ``verify_payment``
    instead.
    """

    provider = "cashfree"

    def charge(self, order, *, method: str = "upi", **kwargs):
        raise NotImplementedError(
            "Cashfree uses redirect-based checkout. Use create_order() + verify_payment()."
        )

    # ── Cashfree-specific methods ─────────────────────────────────────────

    @staticmethod
    def _headers() -> dict:
        from django.conf import settings

        return {
            "x-client-id": settings.CF_APP_ID,
            "x-client-secret": settings.CF_SECRET_KEY,
            "x-api-version": settings.CF_API_VERSION,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _base_url() -> str:
        from django.conf import settings

        return settings.CF_API_BASE.rstrip("/")

    def create_order(self, order, customer_email: str = "", customer_phone: str = "") -> dict:
        """Create a Cashfree order and return the payment session ID.

        Each call generates a unique ``order_id`` so that retries after
        FAILED / USER_DROPPED payments receive a fresh ``payment_session_id``
        instead of reusing the stale session from the previous attempt.

        Returns::

            {
                "success": True,
                "cf_order_id": str,          # Cashfree's internal order ID
                "order_id": str,             # The unique merchant order ID we sent
                "payment_session_id": str,
                "order_status": str,
            }

        Raises ``ValueError`` on API failure.
        """
        import requests
        from django.conf import settings

        cashfree_order_id = f"{order.id}-{uuid.uuid4().hex[:8]}"

        url = f"{self._base_url()}/orders"
        payload = {
            "order_id": cashfree_order_id,
            "order_amount": float(order.grand_total),
            "order_currency": "INR",
            "customer_details": {
                "customer_id": str(order.user.id),
                "customer_email": customer_email or f"customer{order.user.id}@pachoos.local",
                "customer_phone": customer_phone or "9999999999",
            },
            "order_meta": {
                "return_url": f"{settings.CF_RETURN_URL}?order_id={order.id}",
            },
        }

        resp = requests.post(url, json=payload, headers=self._headers(), timeout=30)

        if resp.status_code not in (200, 201):
            body = resp.text[:500]
            if resp.status_code == 401:
                raise ValueError(
                    "Cashfree authentication failed. Please verify CF_APP_ID "
                    "and CF_SECRET_KEY in your .env file are correct sandbox "
                    "credentials from the Cashfree Dashboard."
                )
            raise ValueError(
                f"Cashfree order creation failed ({resp.status_code}): {body}"
            )

        data = resp.json()
        return {
            "success": True,
            "cf_order_id": data.get("cf_order_id", ""),
            "order_id": cashfree_order_id,
            "payment_session_id": data.get("payment_session_id", ""),
            "order_status": data.get("order_status", ""),
        }

    def verify_payment(self, order_id: str) -> dict:
        """Fetch the latest order/payment status from Cashfree.

        Makes two API calls:
        1. GET /orders/{order_id} — to get order_status (PAID / ACTIVE / EXPIRED / TERMINATED)
        2. GET /orders/{order_id}/payments — to get payment_status (SUCCESS / FAILED / USER_DROPPED / etc.)

        The Get Order API does NOT include a payments array, so a separate
        call is required to get the actual payment-level status.

        Args:
            order_id: The merchant's order ID (the UUID we sent during
                      ``create_order``), NOT the ``cf_order_id``.

        Returns::

            {
                "success": bool,
                "paid": bool,
                "cf_order_id": str,
                "order_status": str,
                "payment_status": str | None,
                "payment_method": str | None,
                "transaction_id": str | None,
            }
        """
        import requests

        # ── 1. Get order status ──────────────────────────────────────────
        url = f"{self._base_url()}/orders/{order_id}"
        resp = requests.get(url, headers=self._headers(), timeout=30)

        if resp.status_code != 200:
            return {
                "success": False,
                "paid": False,
                "cf_order_id": "",
                "order_status": "UNKNOWN",
                "payment_status": None,
                "payment_method": None,
                "transaction_id": None,
            }

        data = resp.json()
        order_status = data.get("order_status", "")
        cf_order_id = data.get("cf_order_id", "")

        # ── 2. Get payment details (separate endpoint) ───────────────────
        # The Get Order API does not return a payments array.
        # Use the dedicated payments endpoint to get the actual payment status.
        payment_status = None
        payment_method = None
        transaction_id = None

        try:
            payments_url = f"{self._base_url()}/orders/{order_id}/payments"
            payments_resp = requests.get(
                payments_url, headers=self._headers(), timeout=30
            )

            if payments_resp.status_code == 200:
                payments_data = payments_resp.json()
                # Cashfree returns a list of payment objects directly
                if isinstance(payments_data, list) and payments_data:
                    # Take the latest payment (last in the list)
                    latest_payment = payments_data[-1]
                    payment_status = latest_payment.get("payment_status", "")
                    payment_method = normalize_payment_method(
                        latest_payment.get("payment_method", "")
                    )
                    transaction_id = latest_payment.get("cf_payment_id", "")
            else:
                # Payments endpoint may return 404 if no payment attempt yet
                # In that case, payment_status stays None (genuinely pending)
                pass
        except requests.RequestException:
            # If the payments call fails, fall back to order-level status only
            pass

        paid = order_status == "PAID"

        return {
            "success": True,
            "paid": paid,
            "cf_order_id": cf_order_id,
            "order_status": order_status,
            "payment_status": payment_status,
            "payment_method": payment_method,
            "transaction_id": transaction_id,
        }


_GATEWAYS = {
    "demo": DemoPaymentGateway,
    "razorpay": RazorpayGateway,
    "cashfree": CashfreeGateway,
}


KNOWN_PAYMENT_METHODS = {
    "upi",
    "card",
    "netbanking",
    "wallet",
    "emi",
    "cod",
    "demo_upi",
    "demo_card",
    "demo_gpay",
    "demo_phonepe",
    "demo_paytm",
}


def normalize_payment_method(value) -> str:
    """Return a clean, human-readable payment-method token.

    Cashfree PG v2 reports ``payment_method`` as an object keyed by method
    (e.g. ``{"app": {...}}`` or ``{"upi": {...}}``). Storing that in a
    CharField persists its Python repr ("{'app': ...}"), which then leaks
    into order displays. Normalize dicts/lists/legacy repr strings to a
    simple lowercase token; unrecognizable payloads become "online".
    """
    if isinstance(value, dict):
        value = next(iter(value), "")
    elif isinstance(value, (list, tuple)):
        value = normalize_payment_method(value[0]) if value else ""
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if "{" in text or "[" in text or "'" in text or '"' in text:
        return "online"
    return text


def get_gateway(provider: str = "demo") -> PaymentGateway:
    """Return a gateway instance by provider name."""
    cls = _GATEWAYS.get(provider or "demo", DemoPaymentGateway)
    return cls()
