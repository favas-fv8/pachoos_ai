"""Wallet services — cashback credit, redemption, debt."""
import re
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.wallet.models import (
    DebtBillItem,
    DebtBook,
    DebtLedger,
    DebtNote,
    Voucher,
    VoucherRedemption,
    WalletLedger,
)

BUSINESS = settings.BUSINESS

MIN_CASHBACK_REDEEM = Decimal("10.00")


@transaction.atomic
def credit_cashback(order) -> WalletLedger | None:
    """Credit cashback for a completed order. Returns ledger entry or None if zero."""
    cashback_rate = Decimal(str(BUSINESS["CASHBACK_PER_INR"]))
    if cashback_rate <= 0:
        return None

    cashback_amount = (order.grand_total / cashback_rate).quantize(Decimal("0.01"))
    if cashback_amount <= 0:
        return None

    # Get running balance
    last_entry = (
        WalletLedger.objects.filter(user=order.user, shop=order.shop)
        .order_by("-created_at")
        .first()
    )
    current_balance = last_entry.balance_after if last_entry else Decimal("0.00")
    new_balance = current_balance + cashback_amount

    ledger = WalletLedger.objects.create(
        user=order.user,
        shop=order.shop,
        delta=cashback_amount,
        balance_after=new_balance,
        reason="purchase_cashback",
        ref_order=order,
        note=f"Cashback for order #{order.order_number}",
    )

    # Update order cashback fields
    order.cashback_earned = cashback_amount
    order.cashback_credited_at = timezone.now()
    order.save(update_fields=["cashback_earned", "cashback_credited_at"])

    return ledger


@transaction.atomic
def redeem_cashback(user, shop, amount=None) -> WalletLedger:
    """Redeem cashback from the wallet balance.

    ``amount=None`` redeems the full current balance. Redemption is only
    allowed when the balance is at least ``MIN_CASHBACK_REDEEM`` (₹10); a
    custom amount must also be ≥ ₹10 and can never exceed the balance.
    """
    balance = get_wallet_balance(user, shop)
    if balance < MIN_CASHBACK_REDEEM:
        raise ValueError("You need at least ₹10 cashback to redeem.")

    if amount is None:
        redeem_amount = _money(balance)
    else:
        redeem_amount = _money(amount)
        if redeem_amount < MIN_CASHBACK_REDEEM:
            raise ValueError("Minimum redemption amount is ₹10.")
        if redeem_amount > balance:
            raise ValueError("Amount exceeds your available cashback balance.")

    last_entry = (
        WalletLedger.objects.filter(user=user, shop=shop)
        .order_by("-created_at")
        .first()
    )
    current_balance = last_entry.balance_after if last_entry else Decimal("0.00")

    return WalletLedger.objects.create(
        user=user,
        shop=shop,
        delta=-redeem_amount,
        balance_after=current_balance - redeem_amount,
        reason="cashback_redeemed",
        note=f"Cashback redeemed ₹{redeem_amount}",
    )


def get_total_cashback_redeemed(user, shop) -> Decimal:
    """Total cashback redeemed so far (positive number).

    Includes legacy ``voucher_mint`` rows (the old automatic ₹10 redemptions)
    so the total always matches the redemption entries shown in Cashback
    History.
    """
    from django.db.models import Sum

    total = (
        WalletLedger.objects.filter(
            user=user, shop=shop, reason__in=["cashback_redeemed", "voucher_mint"]
        )
        .aggregate(total=Sum("delta"))["total"]
        or Decimal("0.00")
    )
    return -_money(total)


@transaction.atomic
def redeem_voucher(user, voucher_code: str, order) -> Decimal:
    """Redeem a voucher against an order. Returns discount amount or raises ValueError."""
    try:
        voucher = Voucher.objects.get(
            code__iexact=voucher_code,
            user=user,
            status="active",
        )
    except Voucher.DoesNotExist:
        raise ValueError("Invalid or already used voucher.") from None

    if voucher.expires_at and timezone.now() > voucher.expires_at:
        voucher.status = "expired"
        voucher.save(update_fields=["status"])
        raise ValueError("Voucher has expired.")

    discount = min(voucher.amount, order.subtotal)

    voucher.status = "used"
    voucher.used_at = timezone.now()
    voucher.save(update_fields=["status", "used_at"])

    VoucherRedemption.objects.create(
        voucher=voucher,
        order=order,
        user=user,
        amount_used=discount,
    )

    return discount


def _record_audit(actor, action, entity_type, entity_id="", description="",
                  before=None, after=None, request=None):
    """Write the immutable AuditLog + notify the *other* admin(s).

    Lazy import keeps the wallet app decoupled from admin_dashboard at load time
    (admin_dashboard.services imports wallet.models, not wallet.services).
    """
    from apps.admin_dashboard.activity import record_admin_activity

    return record_admin_activity(
        actor, action, entity_type, entity_id, description, before, after, request
    )


def phone_to_digits(value) -> str:
    """Strip everything that is not a digit ('+91 98765 43210' → '919876543210')."""
    return re.sub(r"\D", "", value or "")


def phone_key(value) -> str:
    """Canonical 10-digit key used for dedupe + display comparison.

    Legacy phones stored with a ``+91`` prefix normalize to their last 10
    digits, so new bare 10-digit entries still match old records on the same
    line. An empty/invalid phone yields an empty key (never matched).
    """
    digits = phone_to_digits(value)
    if len(digits) >= 10:
        return digits[-10:]
    return ""


def validate_phone(value) -> str:
    """Return the canonical 10-digit phone or raise ``ValueError``."""
    key = phone_key(value)
    if len(key) != 10:
        raise ValueError("Phone number must be exactly 10 digits (digits only).")
    return key


def validate_email(value) -> str:
    """Return a lowercased, trimmed email or raise ``ValueError``."""
    email = (value or "").strip().lower()
    if not email:
        raise ValueError("Email is required.")
    from django.core.validators import validate_email as dj_validate

    try:
        dj_validate(email)
    except Exception:
        raise ValueError("Enter a valid email address (e.g. name@gmail.com).") from None
    return email


def _offline_duplicate(shop, *, phone="", email="", exclude_pk=None) -> "DebtBook | None":
    """Find an offline book in ``shop`` already using the same phone or email."""
    key = phone_key(phone)
    email = (email or "").strip().lower()
    qs = DebtBook.objects.filter(shop=shop, user__isnull=True)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    for book in qs.only("phone", "email", "pk").iterator():
        if key and key == phone_key(book.phone):
            return book
        if email and book.email and book.email.strip().lower() == email:
            return book
    return None


@transaction.atomic
def get_or_create_debt_book(shop, *, user=None, name="", phone="", email="") -> "DebtBook":
    """Return the DebtBook for a registered (``user``) or offline customer.

    Registered → matched by ``(user, shop)``; offline → matched by the canonical
    phone *or* email against offline books of ``shop`` (avoids duplicate offline
    customer records); otherwise a new book is created. Never creates a login
    account for an offline customer.
    """
    if user is not None:
        book = DebtBook.objects.filter(user=user, shop=shop).first()
        if book:
            return book
        return DebtBook.objects.create(user=user, shop=shop, name=name, phone=phone)

    existing = _offline_duplicate(shop, phone=phone, email=email)
    return existing or DebtBook.objects.create(shop=shop, name=name, phone=phone, email=email)


@transaction.atomic
def link_offline_debt_book(book, user, admin_user, request=None) -> "DebtBook":
    """Safely associate an offline book with a recently-registered customer.

    Guards:
      * the book must not already be linked to a different user,
      * ``user`` must be a customer account (never a staff account),
      * ``user`` must not already own another book in the same shop.
    The ledger rows themselves are untouched (immutable history is preserved).
    """
    if book.user_id is not None and book.user_id != user.id:
        raise ValueError("This Debt Book is already linked to another account.")
    if user.is_staff:
        raise ValueError("Debt books can only be linked to customer accounts.")
    existing = DebtBook.objects.filter(user=user, shop=book.shop).exclude(pk=book.pk).exists()
    if existing:
        raise ValueError("This customer already has a Debt Book in this shop.")

    before = {"linked_user": None, "name": book.name, "phone": book.phone}
    book.user = user
    book.name = ""
    book.phone = ""
    book.save(update_fields=["user", "name", "phone", "updated_at"])
    _record_audit(
        admin_user,
        action="debt.book_linked",
        entity_type="debt_book",
        entity_id=str(book.pk),
        description=f"Linked offline Debt Book to customer {user}",
        before=before,
        after={"linked_user": user.id, "name": "", "phone": ""},
        request=request,
    )
    return book


def _running_balance(book) -> Decimal:
    last = (
        DebtLedger.objects.filter(book=book)
        .order_by("-created_at", "-id")
        .first()
    )
    return last.balance_after if last else Decimal("0.00")


def _line_total(quantity, unit_price: Decimal, discount: Decimal) -> Decimal:
    return (Decimal(str(quantity)) * unit_price - discount).quantize(Decimal("0.01"))


@transaction.atomic
def add_debt_bill(book, *, admin_user, product_name="", quantity=1, unit_price=0,
                  discount=0, note="", reason="", request=None,
                  items=None, amount_paid=0) -> DebtLedger:
    """Add goods taken on credit to a customer's Debt Book.

    Supports both forms:

    * single product — legacy ``product_name``/``quantity``/``unit_price``/
      ``discount`` params (flat row), kept for existing callers/tests;
    * multi product — ``items`` accepts a list of
      ``{product_id?, product_name, quantity, unit, unit_price, discount}``.
      Totals are always recomputed server side — never trusted from the client.

    ``amount_paid`` (optional) is money taken at the counter in the same
    transaction: it is stored on the bill row and mirrored as its own immutable
    ``payment`` ledger entry so the running balance (and thus ``outstanding``)
    already reflects the net amount actually left on credit.
    """
    amount_paid = _money(amount_paid)
    line_items = list(items) if items else None

    if line_items:
        computed = []
        subtotal = Decimal("0.00")
        for item in line_items:
            qty = _money(item.get("quantity") or 1)
            price = _money(item.get("unit_price"))
            disc = _money(item.get("discount"))
            line_total = _line_total(qty, price, disc)
            subtotal += qty * price
            computed.append({
                "product": item.get("product_id"),
                "product_name": (item.get("product_name") or "").strip(),
                "quantity": qty,
                "unit": item.get("unit") if item.get("unit") in ("kg", "count") else "count",
                "unit_price": price,
                "discount": disc,
                "line_total": line_total,
            })
        delta = _money(sum(i["line_total"] for i in computed))
        # Flat row mirrors the whole bill for backward compatibility.
        flat_name = computed[0]["product_name"] or ""
        if len(computed) > 1:
            flat_name = flat_name or "Multiple products"
        flat_qty = 1
        flat_price = delta
        flat_discount = Decimal("0.00")
        product_name = flat_name
    else:
        quantity = quantity or 1
        unit_price = _money(unit_price)
        discount = _money(discount)
        delta = _line_total(quantity, unit_price, discount)
        computed = [{
            "product": None,
            "product_name": product_name,
            "quantity": Decimal(str(quantity)),
            "unit": "count",
            "unit_price": unit_price,
            "discount": discount,
            "line_total": delta,
        }]
        flat_qty = quantity
        flat_price = unit_price
        flat_discount = discount

    prev_balance = _running_balance(book)
    balance_after = prev_balance + delta

    bill = DebtLedger.objects.create(
        book=book,
        user=book.user,
        shop=book.shop,
        entry_type="bill",
        product_name=product_name,
        quantity=flat_qty,
        unit_price=flat_price,
        discount=flat_discount,
        amount_paid=amount_paid,
        prev_balance=prev_balance,
        delta=delta,
        balance_after=balance_after,
        reason=reason,
        note=note,
        updated_by=admin_user,
    )

    for line in computed:
        product = None
        product_id = line.get("product")
        if product_id:
            from apps.catalog.models import Product
            product = Product.objects.filter(pk=product_id).first()
        DebtBillItem.objects.create(
            bill=bill,
            product=product,
            product_name=line["product_name"],
            quantity=line["quantity"],
            unit=line["unit"],
            unit_price=line["unit_price"],
            discount=line["discount"],
            line_total=line["line_total"],
        )

    # Counter payment mirrored as its own immutable ledger row.
    if amount_paid > 0:
        payment_balance_after = balance_after - amount_paid
        payment = DebtLedger.objects.create(
            book=book,
            user=book.user,
            shop=book.shop,
            entry_type="payment",
            prev_balance=balance_after,
            delta=-amount_paid,
            balance_after=payment_balance_after,
            reason="counter_payment",
            note="Paid at counter with bill",
            updated_by=admin_user,
        )
        # Ensure the mirrored payment sorts *after* its bill for running-balance
        # ordering (created_at can collide within the same microsecond; id is a
        # random UUID so it is not a reliable tie-break).
        DebtLedger.objects.filter(pk=payment.pk).update(
            created_at=bill.created_at + timezone.timedelta(microseconds=1)
        )

    _record_audit(
        admin_user,
        action="debt.bill_added",
        entity_type="debt_book",
        entity_id=str(book.pk),
        description=f"Debt bill {product_name or ''} ₹{delta} for {book.display_name}".strip(),
        before={"balance_before": str(prev_balance)},
        after={"balance_after": str(balance_after)},
        request=request,
    )
    return bill


@transaction.atomic
def record_payment(book, *, admin_user, amount, note="", reason="", request=None) -> DebtLedger:
    """Record a payment against a customer's outstanding debt."""
    amount = Decimal(str(amount or 0)).quantize(Decimal("0.01"))
    if amount <= 0:
        raise ValueError("Payment amount must be greater than zero.")
    prev_balance = _running_balance(book)
    delta = -amount
    balance_after = prev_balance + delta

    entry = DebtLedger.objects.create(
        book=book,
        user=book.user,
        shop=book.shop,
        entry_type="payment",
        prev_balance=prev_balance,
        delta=delta,
        balance_after=balance_after,
        reason=reason,
        note=note,
        updated_by=admin_user,
    )
    _record_audit(
        admin_user,
        action="debt.payment_recorded",
        entity_type="debt_book",
        entity_id=str(book.pk),
        description=f"Payment ₹{amount} received from {book.display_name}",
        before={"balance_before": str(prev_balance)},
        after={"balance_after": str(balance_after)},
        request=request,
    )
    return entry


@transaction.atomic
def add_debt_adjustment(book, *, admin_user, amount, note="", reason="", request=None) -> DebtLedger:
    """Append a correction entry (never edits the original immutable row).

    ``amount`` is signed: passes through directly. Historical rows are left
    untouched; the net effect lands in a fresh ``adjustment`` entry.
    """
    amount = Decimal(str(amount or 0)).quantize(Decimal("0.01"))
    prev_balance = _running_balance(book)
    balance_after = prev_balance + amount

    entry = DebtLedger.objects.create(
        book=book,
        user=book.user,
        shop=book.shop,
        entry_type="adjustment",
        prev_balance=prev_balance,
        delta=amount,
        balance_after=balance_after,
        reason=reason,
        note=note,
        updated_by=admin_user,
    )
    _record_audit(
        admin_user,
        action="debt.adjusted",
        entity_type="debt_book",
        entity_id=str(book.pk),
        description=f"Debt adjustment {amount:+} for {book.display_name}",
        before={"balance_before": str(prev_balance)},
        after={"balance_after": str(balance_after)},
        request=request,
    )
    return entry


@transaction.atomic
def update_debt_customer(book, *, admin_user, name=None, phone=None, email=None,
                         request=None) -> "DebtBook":
    """Edit an *offline* Debt Book's contact details.

    Only offline books (``user`` is null) can be renamed/re-contacted — linked
    books take their identity from the registered account. Phone must be exactly
    10 digits; email is validated; both are deduped against the shop's other
    offline books. Returns the updated book.
    """
    if book.user_id is not None:
        raise ValueError("Only offline customers can be edited here.")

    before = {"name": book.name, "phone": book.phone, "email": book.email}
    upd_fields = []
    if name is not None:
        book.name = (name or "").strip()
        upd_fields.append("name")
    if phone is not None:
        new_phone = validate_phone(phone)
        if new_phone != phone_key(book.phone):
            duplicate = _offline_duplicate(
                book.shop, phone=new_phone, exclude_pk=book.pk
            )
            if duplicate:
                raise ValueError("Another offline customer already uses this phone number.")
        book.phone = new_phone
        upd_fields.append("phone")
    if email is not None:
        new_email = validate_email(email)
        existing = book.email and book.email.strip().lower()
        if new_email and new_email != existing:
            duplicate = _offline_duplicate(
                book.shop, email=new_email, exclude_pk=book.pk
            )
            if duplicate:
                raise ValueError("Another offline customer already uses this email.")
        book.email = new_email
        upd_fields.append("email")
    if upd_fields:
        book.save(update_fields=upd_fields + ["updated_at"])
        _record_audit(
            admin_user,
            action="debt.customer_updated",
            entity_type="debt_book",
            entity_id=str(book.pk),
            description=f"Edited offline customer {book.display_name}",
            before={"name": before["name"], "phone": before["phone"], "email": before["email"]},
            after={"name": book.name, "phone": book.phone, "email": book.email},
            request=request,
        )
    return book


@transaction.atomic
def delete_debt_customer(book, *, admin_user, request=None) -> None:
    """Permanently delete an *offline* Debt Book.

    Guard: only offline books with **no ledger history** may be deleted, so real
    financial records (AuditLog, ledger rows, notes) are never destroyed. Raises
    ``ValueError`` when deletion is not safe — the caller returns 409.
    """
    if book.user_id is not None:
        raise ValueError("Registered customers cannot be deleted; unlink instead.")
    if DebtLedger.objects.filter(book=book).exists():
        raise ValueError(
            "This customer has debt history. Delete is disabled to preserve the ledger."
        )

    _record_audit(
        admin_user,
        action="debt.customer_deleted",
        entity_type="debt_book",
        entity_id=str(book.pk),
        description=f"Deleted offline customer {book.display_name}",
        before={"name": book.name, "phone": book.phone, "email": book.email},
        after=None,
        request=request,
    )
    book.delete()


def _money(value) -> Decimal:
    """Normalise a money value to 2-decimal precision (SQLite sums may return
    int-like Decimals that lose trailing zeroes)."""
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def get_debt_book_summary(book) -> dict:
    """Totals for a Debt Book: overall outstanding, amounts added & paid."""
    from django.db.models import Sum

    totals = DebtLedger.objects.filter(book=book).aggregate(
        added=Sum("delta", filter=Q(delta__gt=0)),
        paid=Sum("delta", filter=Q(delta__lt=0)),
    )
    total_added = _money(totals["added"])
    total_paid = -_money(totals["paid"])
    return {
        "outstanding": str(_money(_running_balance(book))),
        "total_added": str(total_added),
        "total_paid": str(total_paid),
    }


@transaction.atomic
def post_debt_note(book, sender, body: str) -> DebtNote:
    """Append a note/chat message to a Debt Book (admin or owning customer)."""
    body = (body or "").strip()
    if not body:
        raise ValueError("Note text cannot be empty.")

    return DebtNote.objects.create(book=book, sender=sender, body=body)


@transaction.atomic
def adjust_debt(user, shop, amount: Decimal, reason: str, admin_user) -> DebtLedger:
    """Legacy entry point — adjust a *registered* customer's debt/credit.

    Use signed ``amount`` (positive adds debt, negative records a payment or
    correction downward). Backed by a DebtBook + immutable ledger row. Kept for
    backwards compatibility with existing callers/tests.
    """
    book = get_or_create_debt_book(shop, user=user)
    amount = Decimal(str(amount or 0)).quantize(Decimal("0.01"))
    if amount.is_zero():
        return add_debt_adjustment(book, admin_user=admin_user, amount=0,
                                   note="Zero adjustment", reason=reason)
    if amount > 0:
        return add_debt_bill(book, admin_user=admin_user, unit_price=amount,
                             quantity=1, reason=reason, note=reason)
    return record_payment(book, admin_user=admin_user, amount=-amount,
                          reason=reason, note=reason)


def get_wallet_balance(user, shop) -> Decimal:
    """Get current cashback balance for a user."""
    from django.db.models import Sum
    return (
        WalletLedger.objects.filter(user=user, shop=shop)
        .aggregate(total=Sum("delta"))["total"]
        or Decimal("0.00")
    )


def get_debt_balance(user, shop) -> Decimal:
    """Get current debt balance for a user (registered customers)."""
    from django.db.models import Sum
    return (
        DebtLedger.objects.filter(user=user, shop=shop)
        .aggregate(total=Sum("delta"))["total"]
        or Decimal("0.00")
    )
