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


_GATEWAYS = {
    "demo": DemoPaymentGateway,
    "razorpay": RazorpayGateway,
}


def get_gateway(provider: str = "demo") -> PaymentGateway:
    """Return a gateway instance by provider name."""
    cls = _GATEWAYS.get(provider or "demo", DemoPaymentGateway)
    return cls()
