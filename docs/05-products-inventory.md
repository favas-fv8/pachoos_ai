# PACHOOS — Phase 5: Products & Inventory

> Product catalog with categories, subcategories, variants, tags, inventory, search, and filters.

## Backend catalog app (`apps/catalog/`)

### Models
| Model | Key fields |
|---|---|
| `Category` | name, slug, image, is_active |
| `Subcategory` | category FK, name, slug |
| `Product` | subcategory FK, name, slug, description, ingredients, nutritional_info, brand, sku, barcode, base_price, discount_percent, gst_percent, stock_quantity, freshness, is_available, is_featured, avg_rating, times_sold |
| `ProductVariant` | product FK, name, sku, price, discount_percent, stock_quantity, is_active |
| `ProductImage` | product FK, image_url, alt_text, sort_order, is_primary |
| `Tag` | name, slug |
| `ProductTag` | product FK, tag FK (many-to-many via intermediate) |
| `StockMovement` | product FK, variant FK, quantity (signed), reason (sale/purchase/restock/adjustment/return), ref_order_id, created_by |
| `Purchase` | shop FK, supplier, invoice_ref, total_amount |
| `PurchaseItem` | purchase FK, product FK, variant FK, quantity, unit_cost, total |

### API endpoints (`/api/v1/catalog/`)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/categories/` | public | List active categories |
| GET | `/subcategories/` | public | List subcategories (filter by `category` slug) |
| GET | `/products/` | public | List products with search (`q`), filter (`category`, `subcategory`, `freshness`, `min_price`, `max_price`, `min_rating`, `sort_by`, `available`), paginated |
| GET | `/products/{slug}/` | public | Product detail with variants, images, tags |
| GET | `/products/{slug}/related/` | public | Related products (same subcategory, sorted by popularity) |
| GET | `/tags/` | public | List all tags |
| GET | `/stock-movements/` | staff | Inventory movement log |
| CRUD | `/admin/products/` | staff | Full product CRUD (admin only) |

### Search & filter service (`apps/catalog/services/filter.py`)
- Full-text search across name, description, brand, SKU, tags, subcategory, category.
- Filter by category, subcategory, freshness, price range, rating, availability.
- Sort by popularity, newest, price (asc/desc), discount, rating, name.

### Verified
```
manage.py check      → 0 issues
manage.py seed_catalog → 8 products across 2 categories
GET /api/v1/catalog/products/ → 200 (paginated list)
GET /api/v1/catalog/products/chocolate-cake/ → 200 (detail with variants)
GET /api/v1/catalog/products/?q=cake → 200 (search)
GET /api/v1/catalog/products/?freshness=bakery → 200 (filter)
```

## Frontend product pages (`frontend/src/`)

| File | Description |
|---|---|
| `pages/Shop.tsx` | Product grid with search bar, sort dropdown, freshness filter chips, "in stock only" toggle, debounced API fetch |
| `pages/ProductDetail.tsx` | Product detail with image gallery, variant selector, quantity input, add-to-cart button, trust badges |
| `components/product/ProductCard.tsx` | Card with image, name, rating, price (discounted + original), stock badge, add-to-cart link |

### Product grid features
- Debounced search (300 ms) against `/api/v1/catalog/products/?q=...`
- Sort by popularity/newest/price/discount/rating
- Freshness filter chips (Fresh / Bakery / Fruit)
- "In stock only" toggle
- Skeleton loading placeholders
- Empty state with "Clear filters" link
- Responsive grid: 2 cols mobile → 4 cols desktop

### Product detail features
- Image gallery with primary image
- Variant selector (size/weight pills)
- Quantity input (clamped to stock)
- Add to cart button (disabled when out of stock)
- Trust badges (free delivery, secure payment, fresh guarantee)
- Skeleton loading placeholder

## Next phases
- **Phase 6** — Cart & checkout (cart state, delivery rules, coupon/voucher engine, order lifecycle)
- **Phase 7** — Payments (Razorpay, webhooks, refunds, GST invoices)
- **Phase 8** — Wallet cashback, voucher minting, debt ledger