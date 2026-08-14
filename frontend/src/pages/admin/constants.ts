export type BadgeVariant =
  | 'default'
  | 'secondary'
  | 'outline'
  | 'success'
  | 'warning'
  | 'danger'
  | 'muted'

/** Order status → Badge variant map (shared across admin pages). */
export const STATUS_COLORS: Record<string, BadgeVariant> = {
  pending: 'warning',
  accepted: 'success',
  preparing: 'secondary',
  packed: 'secondary',
  out_for_delivery: 'secondary',
  delivered: 'success',
  cancelled: 'danger',
}

export const STATUS_OPTIONS = [
  'pending',
  'accepted',
  'preparing',
  'packed',
  'out_for_delivery',
  'delivered',
  'cancelled',
]

/** Stock quantity units for the admin catalog (weight vs piece-based). */
export const STOCK_UNITS = [
  { value: 'kg', label: 'kg' },
  { value: 'count', label: 'count' },
] as const

export const stockUnitLabel = (unit?: string | null): string =>
  unit === 'kg' ? 'kg' : 'count'
