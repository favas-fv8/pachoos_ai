export type Role = 'super_admin' | 'store_manager' | 'customer'

export interface User {
  id: number
  phone?: string | null
  email?: string | null
  full_name: string
  role: Role
  avatar_url?: string
  referral_code?: string | null
  is_verified?: boolean
  has_password?: boolean
}

export interface Product {
  id: number
  slug: string
  pid?: string
  name: string
  description: string
  subcategory: number
  subcategory_name: string
  category_name: string
  base_price: number
  effective_price: number
  discount_percent: number
  gst_percent: number
  stock_quantity: number
  stock_unit?: 'kg' | 'count'
  freshness: string
  is_available: boolean
  brand: string
  sku?: string
  barcode?: string | null
  video_url?: string
  avg_rating: number | null
  rating_count: number
  times_sold: number
  is_featured: boolean
  primary_image: string | null
  variants?: ProductVariant[]
  images?: ProductImage[]
  tags?: { id: number; name: string; slug: string }[]
  ingredients?: string
  nutritional_info?: Record<string, unknown> | null
}

export interface ProductVariant {
  id: number
  name: string
  sku: string
  price: number
  discount_percent: number
  effective_price: number
  stock_quantity: number
  is_active: boolean
}

export interface ProductImage {
  id: number
  image_url: string
  alt_text: string
  sort_order: number
  is_primary: boolean
}

export interface ApiErrorBody {
  error?: {
    code?: string
    message?: string
    details?: Record<string, unknown>
  }
}

export interface Paginated<T> {
  count: number
  page: number
  num_pages: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface Address {
  id: number
  label: 'home' | 'office' | 'other'
  line1: string
  line2?: string
  landmark?: string
  city: string
  state: string
  pincode: string
  phone: string
  lat?: number | null
  lng?: number | null
  is_default: boolean
}

export interface Subcategory {
  id: number
  category: number
  name: string
  slug: string
  image_url?: string
  display_order?: number
  is_active?: boolean
}

export interface Category {
  id: number
  name: string
  slug: string
  description: string
  image_url?: string
  display_order: number
  is_active: boolean
  product_count: number
  subcategories: Subcategory[]
  created_at?: string
  updated_at?: string
}

/** Product shape returned by the shared admin catalog endpoints. */
export interface AdminProduct {
  id: number
  pid: string
  name: string
  slug: string
  description: string
  subcategory: number
  subcategory_name: string
  category: number
  category_name: string
  base_price: string
  selling_price: string
  discount_percent: string
  gst_percent: string
  stock_quantity: number
  stock_unit: 'kg' | 'count'
  low_stock_threshold: number
  freshness: string
  is_available: boolean
  brand: string
  sku: string
  ingredients: string
  nutritional_info: Record<string, unknown> | null
  images: ProductImage[]
  variants: ProductVariant[]
  tags: { id: number; name: string; slug: string }[]
  created_at?: string
  updated_at?: string
}

export interface AdminNotification {
  id: number
  action: string
  entity_type: string
  entity_id: string
  description: string
  actor_name: string
  actor_role: string
  is_read: boolean
  created_at: string
}

export interface NotificationsResponse {
  results: AdminNotification[]
  unread_count: number
}

// ── Cart ─────────────────────────────────────────────────────────────────────

export interface WishlistItem {
  id: number
  product: number
  product_name: string
  product_slug: string
  primary_image: string | null
  base_price: number
  effective_price: number
  discount_percent: number
  stock_quantity: number
  is_available: boolean
  category_name: string
  subcategory_name: string
  created_at: string
}

export type StockUnit = 'kg' | 'count'

export interface CartSummaryItem {
  id: number
  product: number
  variant: number | null
  product_name: string
  product_slug: string
  variant_name: string
  quantity: number
  unit: StockUnit
  unit_price: number
  base_price: number
  discount_percent: number
  line_total: number
  image_url: string | null
}

export interface CartSummary {
  items: CartSummaryItem[]
  item_count: number
  subtotal: number
  base_subtotal: number
  product_discount: number
  coupon_discount: number
  coupon_id: number | null
  voucher_discount: number
  voucher_id: number | null
  discount_total: number
  delivery_charge: number
  delivery_free: boolean
  distance_km: number
  tax_total: number
  grand_total: number
}

// ── Orders & payments ────────────────────────────────────────────────────────

export type OrderStatus =
  | 'pending'
  | 'accepted'
  | 'preparing'
  | 'packed'
  | 'out_for_delivery'
  | 'delivered'
  | 'cancelled'
  | 'refunded'

export type PaymentStatus = 'pending' | 'paid' | 'failed' | 'refunded'

export type PaymentMethod =
  | 'upi'
  | 'card'
  | 'netbanking'
  | 'wallet'
  | 'emi'
  | 'demo_upi'
  | 'demo_card'
  | 'demo_gpay'
  | 'demo_phonepe'
  | 'demo_paytm'
  | 'cod'

export interface OrderListItem {
  id: string
  order_number: string
  status: OrderStatus
  status_display: string
  payment_status: PaymentStatus
  payment_status_display: string
  payment_method: PaymentMethod | ''
  grand_total: string
  subtotal: string
  discount_total: string
  delivery_charge: string
  tax_total: string
  delivery_free: boolean
  created_at: string
  items_count: number
}

export interface OrderItem {
  id: string
  product: number
  variant: number | null
  product_name: string
  variant_name: string
  quantity: number
  unit_price: string
  discount: string
  gst_percent: string
  gst_amount: string
  line_total: string
}

export interface OrderTimelineEntry {
  id: string
  order: string
  status: string
  note: string
  actor_role: string
  created_at: string
}

export interface OrderDetail {
  id: string
  order_number: string
  shop: string
  user: number
  user_name: string
  user_phone: string
  user_email: string
  status: OrderStatus
  payment_status: PaymentStatus
  payment_method: PaymentMethod | ''
  subtotal: string
  discount_total: string
  delivery_charge: string
  tax_total: string
  grand_total: string
  coupon_discount: string
  voucher_discount: string
  delivery_free: boolean
  distance_km: string | null
  cashback_earned: string
  cancellation_reason: string
  created_at: string
  updated_at: string
  items: OrderItem[]
  timeline: OrderTimelineEntry[]
}

export interface PaymentStatusResponse {
  order_id: string
  order_number: string
  order_status: OrderStatus
  payment_status: PaymentStatus
  payment_method: PaymentMethod | ''
  amount: string
  transaction_id: string
  created_at: string
}

export interface DemoPaymentConfirmResult {
  success: boolean
  message: string
  transaction_id: string
  payment: {
    id: string
    provider: string
    is_demo: boolean
    transaction_id: string
    method: PaymentMethod
    amount: string
    status: string
  } | null
  order: {
    id: string
    order_number: string
    status: OrderStatus
    payment_status: PaymentStatus
    payment_method: PaymentMethod | ''
    grand_total: string
  }
}

// ── Admin orders ─────────────────────────────────────────────────────────────

export interface AdminOrder {
  id: string
  order_number: string
  user_name: string
  user_phone: string
  status: OrderStatus
  payment_status: PaymentStatus
  payment_method: PaymentMethod | ''
  subtotal: string
  discount_total: string
  delivery_charge: string
  tax_total: string
  grand_total: string
  cancellation_reason: string
  created_at: string
}

export interface AdminOrderDetail {
  id: string
  order_number: string
  customer: {
    id: string
    full_name: string
    phone: string
    email: string
  }
  status: OrderStatus
  payment: {
    status: PaymentStatus
    method: PaymentMethod | ''
    provider: string
    transaction_id: string
    is_demo: boolean
  }
  totals: {
    subtotal: string
    discount_total: string
    delivery_charge: string
    delivery_free: boolean
    tax_total: string
    grand_total: string
  }
  items: {
    product_id: string
    product_name: string
    variant_id: string | null
    variant_name: string
    quantity: number
    unit_price: string
    line_total: string
    tax_percent: string
  }[]
  timeline: {
    status: string
    note: string
    actor_role: string
    created_at: string
  }[]
  delivery: {
    delivery_address: string
    distance_km: string
    charge: string
    status: string
  } | null
  cancellation_reason: string
  created_at: string
  updated_at: string
}
