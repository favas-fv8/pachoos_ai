"""Demo payment service — simulated processing with idempotent confirmation."""
from apps.orders.services import mark_payment_failed, mark_payment_successful
from apps.payments.gateway import get_gateway


def process_demo_payment(order, *, method: str = "demo_upi", simulate: str = "success") -> dict:
    """Run the demo gateway for an order and apply its outcome.

    Idempotent: repeated calls (double-click, page refresh) never create
    duplicate payments, double-deduct stock or double-credit cashback.
    Returns a dict with ``success``, ``message``, ``transaction_id``,
    ``payment`` and ``order``.
    """
    gateway = get_gateway("demo")
    result = gateway.charge(order, method=method, simulate=simulate)

    if result["success"]:
        payment = mark_payment_successful(
            order,
            method=result["method"],
            provider=result["provider"],
            transaction_id=result["transaction_id"],
            is_demo=True,
        )
    else:
        payment = mark_payment_failed(
            order,
            method=result["method"],
            provider=result["provider"],
            transaction_id=result["transaction_id"],
            is_demo=True,
            reason=result["message"],
        )

    return {
        "success": result["success"],
        "message": result["message"],
        "transaction_id": result["transaction_id"],
        "payment": payment,
        "order": order,
    }
