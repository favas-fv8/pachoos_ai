"""Wallet Celery tasks — auto-mint vouchers when cashback >= threshold."""
from celery import shared_task
from django.contrib.auth import get_user_model

from apps.wallet.services import mint_voucher

User = get_user_model()


@shared_task(bind=True, max_retries=2)
def auto_mint_vouchers(self):
    """Check all users and mint vouchers where cashback >= VOUCHER_MINT_AMOUNT.

    Runs periodically via Celery Beat or manually.
    In dev mode (CELERY_TASK_ALWAYS_EAGER=True), runs synchronously.
    """
    from decimal import Decimal

    from django.conf import settings
    from django.db.models import Sum

    from apps.wallet.models import WalletLedger

    mint_amount = Decimal(str(settings.BUSINESS["VOUCHER_MINT_AMOUNT"]))

    # Find users with sufficient balance
    users_with_balance = (
        WalletLedger.objects.values("user_id", "shop_id")
        .annotate(total_balance=Sum("delta"))
        .filter(total_balance__gte=mint_amount)
    )

    minted_count = 0
    for entry in users_with_balance:
        try:
            user = User.objects.get(id=entry["user_id"])
            from apps.shops.models import Shop
            shop = Shop.objects.get(id=entry["shop_id"])
            voucher = mint_voucher(user, shop)
            if voucher:
                minted_count += 1
        except (User.DoesNotExist, Exception):
            continue

    return f"Minted {minted_count} voucher(s)"


@shared_task(bind=True, max_retries=2)
def mint_voucher_for_user(self, user_id: int, shop_id: int):
    """Mint a voucher for a specific user (called after cashback credit)."""
    from decimal import Decimal

    from django.conf import settings
    from django.db.models import Sum

    from apps.shops.models import Shop
    from apps.wallet.models import WalletLedger

    mint_amount = Decimal(str(settings.BUSINESS["VOUCHER_MINT_AMOUNT"]))

    balance = (
        WalletLedger.objects.filter(user_id=user_id, shop_id=shop_id)
        .aggregate(total=Sum("delta"))["total"]
        or Decimal("0.00")
    )

    if balance >= mint_amount:
        try:
            user = User.objects.get(id=user_id)
            shop = Shop.objects.get(id=shop_id)
            voucher = mint_voucher(user, shop)
            if voucher:
                return f"Minted voucher {voucher.code} for user {user_id}"
        except Exception as exc:
            self.retry(exc=exc)

    return f"Insufficient balance for user {user_id}: {balance}"
