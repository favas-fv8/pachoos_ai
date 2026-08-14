"""Tests for the Debt Book — admin management, customer read-only view,
offline customers, notes/chat, linking and immutable audit history.

Also covers the multi-product bill engine (DebtBillItem), customer contact
validations (10-digit phone, Gmail/email, dedupe), edit/delete of offline
customers, and the guarantee that existing ledger history is never altered.
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.wallet.models import (
    DebtBillItem,
    DebtBook,
    DebtLedger,
    DebtNote,
)
from apps.wallet.services import (
    add_debt_adjustment,
    add_debt_bill,
    delete_debt_customer,
    get_debt_book_summary,
    get_or_create_debt_book,
    link_offline_debt_book,
    post_debt_note,
    record_payment,
    update_debt_customer,
)

User = get_user_model()


@pytest.fixture
def customer2(db):
    return User.objects.create_user(
        phone="+919876543222",
        email="customer2@pachoos.com",
        password="testpass123",
        full_name="Second Customer",
        role="customer",
    )


@pytest.fixture
def manager(db):
    return User.objects.create_user(
        phone="+919876543233",
        email="manager@pachoos.com",
        password="adminpass123",
        full_name="Store Manager",
        role="store_manager",
        is_staff=True,
    )


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def customer_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def other_customer_client(customer2):
    client = APIClient()
    client.force_authenticate(user=customer2)
    return client


@pytest.fixture
def registered_book(shop, user):
    return get_or_create_debt_book(shop, user=user, name="Test User", phone="+919876543210")


@pytest.fixture
def offline_book(shop, admin_user):
    book = get_or_create_debt_book(shop, name="Offline Walk-In", phone="+919000000000")
    add_debt_bill(book, admin_user=admin_user, product_name="Bread", quantity=2,
                  unit_price=40, note="Walk-in credit")
    return book


@pytest.fixture
def products(db, shop):
    from apps.catalog.models import Category, Product, Subcategory

    category = Category.objects.create(name="Bakery", slug="bakery")
    sub = Subcategory.objects.create(category=category, name="Cakes", slug="cakes")
    cake = Product.objects.create(
        subcategory=sub, name="Chocolate Cake", slug="chocolate-cake",
        base_price=200, stock_unit="count", sku="SKU-CAKE",
    )
    flour = Product.objects.create(
        subcategory=sub, name="Flour", slug="flour", base_price=50, stock_unit="kg",
        sku="SKU-FLOUR",
    )
    return {"cake": cake, "flour": flour}


@pytest.mark.django_db
class TestDebtBookService:
    def test_add_bill_updates_balances(self, registered_book, admin_user):
        entry = add_debt_bill(
            registered_book, admin_user=admin_user,
            product_name="Cake", quantity=2, unit_price=150, discount=20, note="Birthday cake",
        )
        assert entry.entry_type == "bill"
        assert entry.delta == Decimal("280.00")
        assert entry.balance_after == Decimal("280.00")
        assert entry.prev_balance == Decimal("0.00")
        summary = get_debt_book_summary(registered_book)
        assert summary["total_added"] == "280.00"
        assert summary["outstanding"] == "280.00"

    def test_payment_reduces_balance(self, registered_book, admin_user):
        add_debt_bill(registered_book, admin_user=admin_user, unit_price=100, note="")
        entry = record_payment(registered_book, admin_user=admin_user, amount=40, note="Cash")
        assert entry.delta == Decimal("-40.00")
        assert entry.balance_after == Decimal("60.00")
        assert entry.prev_balance == Decimal("100.00")
        assert get_debt_book_summary(registered_book)["total_paid"] == "40.00"

    def test_payment_must_be_positive(self, registered_book, admin_user):
        with pytest.raises(ValueError):
            record_payment(registered_book, admin_user=admin_user, amount=0)

    def test_adjustment_keeps_history_immutable(self, registered_book, admin_user):
        first = add_debt_bill(registered_book, admin_user=admin_user, unit_price=100, note="")
        correction = add_debt_adjustment(
            registered_book, admin_user=admin_user, amount=Decimal("-25.00")
        )
        assert correction.delta == Decimal("-25.00")
        assert correction.balance_after == Decimal("75.00")
        # The historical row is untouched.
        first.refresh_from_db()
        assert first.delta == Decimal("100.00")
        assert first.balance_after == Decimal("100.00")
        assert DebtLedger.objects.filter(book=registered_book).count() == 2

    def test_offline_book_has_no_user(self, offline_book):
        assert offline_book.is_offline is True
        assert offline_book.display_name == "Offline Walk-In"

    def test_notes_chronological(self, registered_book, admin_user, user):
        post_debt_note(registered_book, admin_user, "Please clear by Friday.")
        post_debt_note(registered_book, user, "Will pay on Saturday.")
        notes = list(DebtNote.objects.filter(book=registered_book))
        assert notes[0].body == "Please clear by Friday."
        assert notes[1].body == "Will pay on Saturday."
        assert notes[0].sender == admin_user
        assert notes[1].sender == user

    def test_link_offline_book(self, offline_book, customer2, admin_user):
        link_offline_debt_book(offline_book, customer2, admin_user)
        offline_book.refresh_from_db()
        assert offline_book.user == customer2
        assert offline_book.is_offline is False
        # Ledger entries preserved under the same book.
        assert offline_book.entries.count() == 1

    def test_link_rejects_staff_or_double_link(self, offline_book, admin_user, manager, customer2, shop):
        with pytest.raises(ValueError):
            link_offline_debt_book(offline_book, manager, admin_user)
        link_offline_debt_book(offline_book, customer2, admin_user)
        other = get_or_create_debt_book(shop, name="Other", phone="+919111111111")
        with pytest.raises(ValueError):
            link_offline_debt_book(other, customer2, admin_user)

    def test_mutations_write_audit_log(self, registered_book, admin_user):
        add_debt_bill(registered_book, admin_user=admin_user, unit_price=100, note="")
        record_payment(registered_book, admin_user=admin_user, amount=50, note="")
        from apps.accounts.models import AuditLog

        logs = list(AuditLog.objects.filter(entity_type="debt_book").order_by("created_at"))
        assert [log.action for log in logs] == ["debt.bill_added", "debt.payment_recorded"]
        assert logs[0].after["balance_after"] == "100.00"
        assert logs[1].after["balance_after"] == "50.00"


@pytest.mark.django_db
class TestDebtBillItemsAndMultiProduct:
    def test_multi_product_bill_creates_items(self, registered_book, admin_user, products):
        bill = add_debt_bill(
            registered_book, admin_user=admin_user, items=[
                {"product_id": products["cake"].id, "product_name": "Chocolate Cake",
                 "quantity": 2, "unit": "count", "unit_price": 200, "discount": 20},
                {"product": products["flour"].id, "product_name": "Flour",
                 "quantity": 3, "unit": "kg", "unit_price": 50, "discount": 0},
            ],
        )
        assert bill.entry_type == "bill"
        assert bill.delta == Decimal("530.00")          # (400-20) + (150) = 530
        assert bill.balance_after == Decimal("530.00")
        assert bill.amount_paid == Decimal("0.00")
        items = list(DebtBillItem.objects.filter(bill=bill).order_by("created_at"))
        assert len(items) == 2
        assert items[0].product == products["cake"]
        assert items[0].line_total == Decimal("380.00")
        assert items[1].unit == "kg"
        assert items[1].line_total == Decimal("150.00")
        assert get_debt_book_summary(registered_book)["outstanding"] == "530.00"

    def test_multi_product_with_counter_payment(self, registered_book, admin_user):
        bill = add_debt_bill(
            registered_book, admin_user=admin_user, items=[
                {"product_name": "Cake", "quantity": 1, "unit": "count",
                 "unit_price": 300, "discount": 0},
            ],
            amount_paid=100,
        )
        bill.refresh_from_db()
        assert bill.amount_paid == Decimal("100.00")
        # Bill deposit + counter-payment = two immutable ledger rows.
        rows = list(DebtLedger.objects.filter(book=registered_book).order_by("prev_balance"))
        assert [r.entry_type for r in rows] == ["bill", "payment"]
        assert rows[1].delta == Decimal("-100.00")
        assert rows[1].balance_after == Decimal("200.00")
        assert get_debt_book_summary(registered_book)["outstanding"] == "200.00"

    def test_single_product_backfill_shape(self, registered_book, admin_user, products):
        """Legacy single-product bill still gets one DebtBillItem (flat row)."""
        entry = add_debt_bill(registered_book, admin_user=admin_user,
                              product_name="Bread", quantity=2, unit_price=40)
        assert entry.quantity == 2
        assert entry.delta == Decimal("80.00")
        assert DebtBillItem.objects.filter(bill=entry).count() == 1

    def test_bill_preserves_running_balance_chains(self, registered_book, admin_user):
        first = add_debt_bill(registered_book, admin_user=admin_user, unit_price=100, note="")
        second = add_debt_bill(
            registered_book, admin_user=admin_user,
            items=[{"product_name": "X", "quantity": 1, "unit": "count",
                    "unit_price": 50, "discount": 10}],
        )
        assert second.delta == Decimal("40.00")
        assert second.prev_balance == Decimal("100.00")
        assert second.balance_after == Decimal("140.00")
        first.refresh_from_db()
        assert first.balance_after == Decimal("100.00")

    def test_multi_product_totals_recomputed_server_side(self, registered_book, admin_user):
        """Client-supplied line totals are ignored entirely."""
        bill = add_debt_bill(
            registered_book, admin_user=admin_user, items=[
                {"product_name": "A", "quantity": 2, "unit": "count",
                 "unit_price": 100, "discount": 0},
                {"product_name": "B", "quantity": 3, "unit": "kg",
                 "unit_price": 50, "discount": 20},
            ],
        )
        assert bill.delta == Decimal("330.00")          # 200 + 130
        assert bill.final_amount == Decimal("330.00")


@pytest.mark.django_db
class TestOfflineCustomerValidationAndEdits:
    def test_get_or_create_dedupes_by_phone_key(self, shop, offline_book):
        # Legacy "+91" prefix normalizes to the same key as a bare 10-digit number.
        dup = get_or_create_debt_book(shop, name="Dup", phone="9000000000")
        assert dup.pk == offline_book.pk
        assert dup.name == "Offline Walk-In"

    def test_get_or_create_dedupes_by_email(self, shop):
        first = get_or_create_debt_book(shop, name="A", phone="9812345670", email="walkink@gmail.com")
        dup = get_or_create_debt_book(shop, name="B", phone="9999999999", email="walkink@GMAIL.com")
        assert dup.pk == first.pk
        assert get_or_create_debt_book(shop, name="C", phone="9612345670").pk != first.pk

    def test_create_rejects_bad_phone(self, admin_client, shop):
        res = admin_client.post("/api/v1/wallet/debt/books/", {"name": "Bad", "phone": "abc"})
        assert res.status_code == 400
        assert "phone" in res.data
        res2 = admin_client.post("/api/v1/wallet/debt/books/", {"name": "Bad", "phone": "9876543"})
        assert res2.status_code == 400

    def test_create_rejects_bad_email(self, admin_client, shop):
        res = admin_client.post(
            "/api/v1/wallet/debt/books/",
            {"name": "Bad", "phone": "9876543210", "email": "not-an-email"},
        )
        assert res.status_code == 400
        assert "email" in res.data

    def test_create_normalizes_phone_to_10_digits(self, admin_client, shop):
        res = admin_client.post(
            "/api/v1/wallet/debt/books/",
            {"name": "Walk-In", "phone": "+91 98765 43210"},
        )
        assert res.status_code == 201
        assert res.data["phone"] == "9876543210"

    def test_edit_offline_customer(self, admin_client, shop, admin_user):
        book = get_or_create_debt_book(shop, name="Old",
                                       phone="9870000000", email="old@gmail.com")
        res = admin_client.patch(
            f"/api/v1/wallet/debt/books/{book.id}/",
            {"name": "New Name", "phone": "9871111111", "email": "new@gmail.com"},
        )
        assert res.status_code == 200
        book.refresh_from_db()
        assert book.name == "New Name"
        assert book.phone == "9871111111"
        assert book.email == "new@gmail.com"

    def test_edit_conflicts_on_duplicate(self, admin_client, shop):
        get_or_create_debt_book(shop, name="A", phone="9810000000", email="a@gmail.com")
        book_b = get_or_create_debt_book(shop, name="B", phone="9820000000", email="b@gmail.com")
        res = admin_client.patch(f"/api/v1/wallet/debt/books/{book_b.id}/", {"phone": "9810000000"})
        assert res.status_code == 400
        res2 = admin_client.patch(f"/api/v1/wallet/debt/books/{book_b.id}/", {"email": "a@GMAIL.com"})
        assert res2.status_code == 400

    def test_cannot_edit_registered_book(self, admin_client, registered_book):
        res = admin_client.patch(
            f"/api/v1/wallet/debt/books/{registered_book.id}/", {"name": "Hack"}
        )
        assert res.status_code == 400

    def test_delete_empty_offline_book(self, admin_client, shop):
        book = get_or_create_debt_book(shop, name="Transient", phone="9890000000")
        res = admin_client.delete(f"/api/v1/wallet/debt/books/{book.id}/")
        assert res.status_code == 204
        assert DebtBook.objects.filter(pk=book.pk).exists() is False

    def test_delete_blocked_when_history_exists(self, admin_client, offline_book):
        # offline_book has one bill → ledger history must be preserved.
        res = admin_client.delete(f"/api/v1/wallet/debt/books/{offline_book.id}/")
        assert res.status_code == 409
        assert DebtBook.objects.filter(pk=offline_book.pk).exists() is True
        # And the bill/ledger is untouched.
        assert offline_book.entries.count() == 1

    def test_delete_blocked_for_registered(self, admin_client, registered_book):
        res = admin_client.delete(f"/api/v1/wallet/debt/books/{registered_book.id}/")
        assert res.status_code == 409

    def test_update_and_delete_write_audit(self, shop, admin_user):
        book = get_or_create_debt_book(shop, name="Ed", phone="9800000000")
        update_debt_customer(book, admin_user=admin_user, name="Edw", phone="9811111111")
        delete_debt_customer(book, admin_user=admin_user)
        from apps.accounts.models import AuditLog

        actions = list(AuditLog.objects.filter(entity_type="debt_book").values_list("action", flat=True))
        assert "debt.customer_updated" in actions
        assert "debt.customer_deleted" in actions


@pytest.mark.django_db
class TestSerializedBillDisplay:
    def test_detail_includes_items_and_totals(self, admin_client, registered_book, admin_user):
        add_debt_bill(
            registered_book, admin_user=admin_user, items=[
                {"product_name": "Cake", "quantity": 2, "unit": "count",
                 "unit_price": 100, "discount": 10},
                {"product_name": "Flour", "quantity": 3, "unit": "kg",
                 "unit_price": 50, "discount": 0},
            ],
            amount_paid=50, note="Festive order",
        )
        res = admin_client.get(f"/api/v1/wallet/debt/books/{registered_book.id}/")
        assert res.status_code == 200
        bill = next(e for e in res.data["entries"] if e["entry_type"] == "bill")
        assert len(bill["items"]) == 2
        assert bill["subtotal"] == "350.00"          # 200 + 150 (gross)
        assert bill["discount_total"] == "10.00"
        assert bill["line_total"] == "340.00"         # delta (net)
        assert bill["amount_paid"] == "50.00"
        assert bill["bill_remaining"] == "290.00"     # 340 − 50
        assert res.data["summary"]["outstanding"] == "290.00"


@pytest.mark.django_db
class TestAdminDebtBookAPI:
    def test_list_shows_registered_and_offline(self, admin_client, registered_book, offline_book, shop):
        res = admin_client.get("/api/v1/wallet/debt/books/")
        assert res.status_code == 200
        ids = {b["id"] for b in res.data}
        assert ids == {str(registered_book.id), str(offline_book.id)}
        offline = next(b for b in res.data if b["is_offline"])
        assert offline["outstanding"] == "80.00"

    def test_list_search(self, admin_client, registered_book, offline_book, shop):
        res = admin_client.get("/api/v1/wallet/debt/books/?q=Offline")
        assert res.status_code == 200
        assert len(res.data) == 1
        assert res.data[0]["display_name"] == "Offline Walk-In"

    def test_create_offline_book(self, admin_client, shop):
        res = admin_client.post("/api/v1/wallet/debt/books/", {"name": "New Walk-In", "phone": "+919555000000"})
        assert res.status_code == 201
        assert res.data["is_offline"] is True
        assert res.data["summary"]["outstanding"] == "0.00"

    def test_add_bill_then_payment_then_detail(self, admin_client, registered_book, shop):
        bill = admin_client.post(
            f"/api/v1/wallet/debt/books/{registered_book.id}/bills/",
            {"product_name": "Burger", "quantity": 3, "unit_price": 60, "discount": 10, "note": "Lunch credit"},
        )
        assert bill.status_code == 201
        assert bill.data["delta"] == "170.00"
        assert bill.data["remaining"] == "170.00"

        pay = admin_client.post(
            f"/api/v1/wallet/debt/books/{registered_book.id}/payments/",
            {"amount": 70, "note": "Partial payment"},
        )
        assert pay.status_code == 201
        assert pay.data["amount_paid"] == "70.00"
        assert pay.data["remaining"] == "100.00"

        detail = admin_client.get(f"/api/v1/wallet/debt/books/{registered_book.id}/")
        assert detail.status_code == 200
        assert detail.data["summary"] == {
            "outstanding": "100.00",
            "total_added": "170.00",
            "total_paid": "70.00",
        }
        assert len(detail.data["entries"]) == 2

    def test_admin_can_add_note(self, admin_client, registered_book):
        res = admin_client.post(
            f"/api/v1/wallet/debt/books/{registered_book.id}/notes/", {"body": "Reminder about balance."}
        )
        assert res.status_code == 201
        notes = admin_client.get(f"/api/v1/wallet/debt/books/{registered_book.id}/notes/")
        assert len(notes.data) == 1
        assert notes.data[0]["sender_role"] == "super_admin"

    def test_admin_can_link_offline_book(self, admin_client, offline_book, customer2):
        res = admin_client.post(
            f"/api/v1/wallet/debt/books/{offline_book.id}/link/", {"user_id": customer2.id}
        )
        assert res.status_code == 200
        assert res.data["is_offline"] is False
        assert offline_book.entries.count() == 1


@pytest.mark.django_db
class TestCustomerDebtBookAPI:
    def test_customer_sees_own_book(self, customer_client, registered_book, admin_user):
        add_debt_bill(registered_book, admin_user=admin_user, product_name="Chicken roll", unit_price=200, note="")
        res = customer_client.get("/api/v1/wallet/my/debt/")
        assert res.status_code == 200
        assert res.data["summary"]["outstanding"] == "200.00"
        assert len(res.data["entries"]) == 1
        assert res.data["entries"][0]["product_name"] == "Chicken roll"

    def test_customer_cannot_see_others(self, other_customer_client, admin_user, shop, user):
        book = get_or_create_debt_book(shop, user=user)
        add_debt_bill(book, admin_user=admin_user, unit_price=500, note="")
        res = other_customer_client.get("/api/v1/wallet/my/debt/")
        assert res.status_code == 200
        assert res.data["id"] is None
        assert res.data["entries"] == []

    def test_customer_cannot_mutate_money(self, customer_client, registered_book, shop):
        res = customer_client.post(
            f"/api/v1/wallet/debt/books/{registered_book.id}/bills/",
            {"product_name": "Hack", "unit_price": 1},
        )
        assert res.status_code == 403
        assert customer_client.get("/api/v1/wallet/debt/books/").status_code == 403

    def test_customer_can_reply_note(self, customer_client, registered_book, admin_user):
        res = customer_client.post("/api/v1/wallet/my/debt/notes/", {"body": "Will visit the shop tomorrow."})
        assert res.status_code == 201
        assert res.data["sender_role"] == "customer"

    def test_anonymous_cannot_access_any_debt(self, shop, user):
        client = APIClient()
        assert client.get("/api/v1/wallet/debt/books/").status_code == 401
        assert client.get("/api/v1/wallet/my/debt/").status_code == 401


@pytest.mark.django_db
class TestBothAdminsConsistency:
    def test_other_admin_notified_on_mutation(self, registered_book, admin_user, manager):
        add_debt_bill(registered_book, admin_user=admin_user, unit_price=100, note="")
        from apps.admin_dashboard.models import AdminNotification

        note = AdminNotification.objects.filter(
            recipient=manager, action="debt.bill_added", entity_type="debt_book"
        ).first()
        assert note is not None
        assert note.entity_id == str(registered_book.id)

    def test_same_latest_data_for_both(self, admin_client, registered_book, admin_user, manager):
        add_debt_bill(registered_book, admin_user=admin_user, unit_price=100, note="")
        manager_client = APIClient()
        manager_client.force_authenticate(user=manager)
        res = manager_client.get(f"/api/v1/wallet/debt/books/{registered_book.id}/")
        assert res.status_code == 200
        admin_data = admin_client.get(f"/api/v1/wallet/debt/books/{registered_book.id}/").data
        assert admin_data["summary"] == res.data["summary"]