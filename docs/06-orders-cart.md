# PACHOOS — Phase 6: Orders & Cart

> Cart management, checkout with delivery rules, coupon/voucher engine, order lifecycle with timeline tracking.

## Backend

### New apps
| App | Purpose |
|---|---|
| `apps/cart/` | Cart model (user or session-scoped), cart items, add/remove/clear |
| `apps/orders/` | Order model (full lifecycle), order items, timeline, delivery, payment, refund |
| `apps/wallet/` | Cashback ledger + voucher pool (stubs for Phase 8 full implementation) |
| `apps/coupons/` | Coupon model (percent/flat/BOGO) + redemption tracking (stubs for Phase 8) |
| `apps/orders/services.py` | Delivery rules, coupon/voucher validation, atomic order placement, payment recording |

### Cart API (`/api/v1/cart/`)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/` | authenticated | Active cart with items |
| POST | `/` | authenticated | Create cart |
| POST | `/{id}/add_item/` | authenticated | Add product variant to cart |
| POST | `/{id}/remove_item/` | authenticated | Remove cart item |
| POST | `/{id}/clear/` | authenticated | Clear all items |

### Orders API (`/api/v1/orders/`)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/` | authenticated | List orders (staff: all) |
| POST | `/` | authenticated | Checkout — creates order from cart |
| GET | `/{id}/` | authenticated | Order detail with items, timeline, delivery |
| PATCH | `/{id}/update_status/` | staff | Update order status |
| POST | `/{id}/cancel/` | authenticated | Cancel order (pending/accepted only) |
| GET | `/{id}/timeline/` | authenticated | Order status timeline |
| GET | `/deliveries/` | staff | Delivery management |
| GET | `/payments/` | staff | Payment records |
| GET | `/refunds/` | staff | Refund records |

### Delivery rules (in `orders/services.py`)
- Free delivery if subtotal ≥ ₹99 AND distance ≤ 2 km.
- Otherwise ₹20 delivery charge.
- Distance is passed from the frontend (Google Maps Distance Matrix in production).

### Coupon/voucher engine (in `orders/services.py`)
- **Coupons**: percent/flat/BOGO, with usage limits, expiry, per-user cap.
- **Vouchers**: ₹10 vouchers minted from cashback, single-use, expires after 60 days.
- Both validated server-side before order placement.

### Order lifecycle
```
pending → accepted → preparing → packed → out_for_delivery → delivered
                                  ↓
                              cancelled / refunded
```
Every status change creates an immutable `OrderTimeline` entry with actor info.

### Frontend
| Page | Description |
|---|---|
| `/checkout` | Delivery address, payment method, coupon/voucher codes, order summary, place order button |
| `/cart` (updated) | Links to checkout, shows cart items with real data |
| `/track/:orderId` | Order tracking with status stepper |

### Verified
```
manage.py check      → 0 issues
manage.py migrate    → cart, orders, wallet, coupons migrations applied
GET /api/v1/cart/    → 200 (requires auth)
GET /api/v1/orders/  → 200 (requires auth)
npm run typecheck    → 0 errors
npm run build        → ✓ 3.72 s, ~138 KB gzip
```

## Next phases
- **Phase 7** — Payments (Razorpay integration, webhook verification, refunds, GST invoices)
- **Phase 8** — Wallet cashback, voucher minting, debt ledger
- **Phase 9** — AI assistant & recommendations