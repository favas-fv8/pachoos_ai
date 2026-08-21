// Single source of truth for payment-status labels + badge colors.
// Used by /admin/payments, /account/payments and the admin orders table so
// every surface shows the same status name with the same, non-conflicting
// color. Keyed off the authoritative `payment_status` field on the order
// ("paid" is set by the backend when a Cashfree payment succeeds), never off
// the fulfillment status.
import type { BadgeProps } from '@/components/ui/badge'

type Tone = NonNullable<BadgeProps['variant']>

export interface PaymentStatusMeta {
  label: string
  tone: Tone
}

const PAYMENT_STATUS_META: Record<string, PaymentStatusMeta> = {
  paid: { label: 'Success', tone: 'success' },
  pending: { label: 'Processing', tone: 'warning' },
  failed: { label: 'Failed', tone: 'danger' },
  refunded: { label: 'Refunded', tone: 'default' },
}

const IN_PROGRESS: PaymentStatusMeta = { label: 'In Progress', tone: 'secondary' }

export function paymentStatusMeta(
  paymentStatus?: string | null,
  orderStatus?: string | null,
): PaymentStatusMeta {
  const key = (paymentStatus ?? '').toLowerCase()
  if (PAYMENT_STATUS_META[key]) return PAYMENT_STATUS_META[key]
  // No payment recorded yet — an order still sitting at "pending" is simply
  // waiting for payment; anything else without payment info is in progress.
  if (!key && (orderStatus ?? '').toLowerCase() === 'pending') {
    return PAYMENT_STATUS_META.pending
  }
  return IN_PROGRESS
}
