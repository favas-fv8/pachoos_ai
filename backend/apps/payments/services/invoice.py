"""Invoice PDF generation service."""
from django.conf import settings
from django.core.files.base import ContentFile
from pathlib import Path
from datetime import datetime

from apps.orders.models import Order
from apps.payments.models import Invoice


def generate_and_save_invoice(order: Order) -> Invoice:
    """Generate invoice PDF and save to storage."""
    invoice, created = Invoice.objects.get_or_create(
        order=order,
        defaults={
            "invoice_number": f"INV-{order.order_number}",
            "gstin_shop": getattr(settings, "SHOP_GSTIN", ""),
            "gstin_customer": "",
            "base_amount": float(order.subtotal),
            "tax_total": float(order.tax_total),
            "grand_total": float(order.grand_total),
        },
    )

    if created or not invoice.pdf_url:
        # Generate PDF content (simplified for now)
        pdf_content = f"""
INVOICE
======
Invoice Number: {invoice.invoice_number}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Customer: {order.user.full_name}
GSTIN (Shop): {invoice.gstin_shop}

Subtotal: {order.subtotal}
Tax Total: {order.tax_total}
Grand Total: {order.grand_total}

Thank you for your business!
        """.strip()

        # Save to storage
        filename = f"invoices/{invoice.id}.txt"
        if hasattr(settings, "DEFAULT_FILE_STORAGE"):
            from django.core.files.storage import default_storage

            path = default_storage.save(filename, ContentFile(pdf_content.encode()))
            invoice.pdf_url = default_storage.url(path)
        else:
            # Fallback to local file for dev
            upload_dir = Path(settings.MEDIA_ROOT) / "invoices"
            upload_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = upload_dir / f"{invoice.id}.txt"
            pdf_path.write_text(pdf_content)
            invoice.pdf_url = f"/media/invoices/{invoice.id}.txt"

        invoice.generated_at = datetime.now()
        invoice.save(update_fields=["pdf_url", "generated_at"])

    return invoice