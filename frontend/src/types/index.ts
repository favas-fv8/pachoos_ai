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
  sku: string
  barcode: string | null
  video_url: string
  avg_rating: number | null
  rating_count: number
  times_sold: number
  is_featured: boolean
  primary_image: string | null
  variants: ProductVariant[]
  images: ProductImage[]
  tags: { id: number; name: string; slug: string }[]
  ingredients: string
  nutritional_info: Record<string, unknown> | null
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
