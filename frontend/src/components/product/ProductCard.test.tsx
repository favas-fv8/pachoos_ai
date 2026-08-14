import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ProductCard } from '@/components/product/ProductCard'
import type { Product } from '@/types'

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: 1,
    slug: 'chocolate-cake',
    name: 'Chocolate Cake',
    description: '',
    subcategory: 1,
    subcategory_name: 'Cakes',
    category_name: 'Bakery',
    base_price: 250,
    effective_price: 225,
    discount_percent: 10,
    gst_percent: 5,
    stock_quantity: 50,
    freshness: 'fresh',
    is_available: true,
    brand: '',
    sku: 'CC-001',
    barcode: null,
    video_url: '',
    avg_rating: 4.5,
    rating_count: 12,
    times_sold: 100,
    is_featured: false,
    primary_image: null,
    variants: [],
    images: [],
    tags: [],
    ingredients: '',
    nutritional_info: null,
    ...overrides,
  }
}

function renderCard(product: Product) {
  return render(
    <MemoryRouter>
      <ProductCard product={product} />
    </MemoryRouter>,
  )
}

describe('ProductCard rating display', () => {
  it('renders a valid numeric rating with review count', () => {
    renderCard(makeProduct({ avg_rating: 4.5, rating_count: 12 }))
    expect(screen.getByText('4.5 (12)')).toBeInTheDocument()
  })

  it('renders a 4.0 rating as 4.0', () => {
    renderCard(makeProduct({ avg_rating: 4, rating_count: 3 }))
    expect(screen.getByText('4.0 (3)')).toBeInTheDocument()
  })

  it('coerces a string rating to a displayed number', () => {
    renderCard(makeProduct({ avg_rating: '4.5' as unknown as number, rating_count: 5 }))
    expect(screen.getByText('4.5 (5)')).toBeInTheDocument()
  })

  it('shows "No ratings" for products with no reviews', () => {
    renderCard(makeProduct({ avg_rating: 0, rating_count: 0 }))
    expect(screen.getByText('No ratings')).toBeInTheDocument()
  })

  it('shows "No ratings" when avg_rating is null', () => {
    renderCard(makeProduct({ avg_rating: null, rating_count: 0 }))
    expect(screen.getByText('No ratings')).toBeInTheDocument()
  })

  it('does not crash when avg_rating is missing', () => {
    renderCard(makeProduct({ avg_rating: undefined as unknown as number }))
    expect(screen.getByText('No ratings')).toBeInTheDocument()
  })
})