# PACHOOS — Requirements Specification (Phase 1)

## 1. Functional Requirements

### 1.1 Authentication & Accounts
- FR-101 Register via mobile number (OTP verified) or Google OAuth.
- FR-102 Login: mobile+OTP, or Google OAuth.
- FR-103 JWT access token (short-lived) + refresh token (rotating).
- FR-104 Rate limit OTP requests (e.g. 1/min, max 5/hour per number) and block after N failed attempts (lockout 15 min).
- FR-105 Device tracking: register device name/IP/UA on each session; list active sessions; logout single session or all devices.
- FR-106 Roles: exactly two admins — `super_admin` and `store_manager` — plus unlimited `customer`s. No per-shop staff accounts. RBAC enforced on every endpoint.
- FR-107 Profile management (name, email, phone, avatar).
- FR-108 OTP is masked; dev mode logs OTP to console instead of sending SMS.
- FR-109 Product & catalog mutations (products, categories, subcategories, variants, inventory, coupons) are restricted to the 2 admins only; customers have read-only catalog access.

### 1.2 Catalog
- FR-201 Unlimited Categories → Subcategories → Products → Variants.
- FR-202 Product fields: title, slug, description, ingredients, nutritional info, brand, SKU, barcode, GST %, tags, freshness indicator, availability, stock, discount %.
- FR-203 Multiple images + optional video per product.
- FR-204 Variant support (e.g. Chocolate Cake → 500g / 1kg / 2kg) with own price/stock/SKU/barcode.
- FR-205 Inventory: real-time stock, low-stock alert threshold, out-of-stock flagging, automatic deduction on order placement, stock history, purchase history (admin).
- FR-206 Search: global across product/category/brand/tags; autocomplete; AI-powered suggestions; recent + trending searches.
- FR-207 Filters: price, popularity, newest, discount, rating, availability, category, subcategory, freshness (bakery/fruit).

### 1.3 Cart & Checkout
- FR-301 Add/remove/update quantity; validate stock at add and at checkout.
- FR-302 Saved addresses (multiple, default flag) with geocode.
- FR-303 Coupons (percent/flat/BOGO), vouchers (from wallet), wallet notes — combined discount engine.
- FR-304 Delivery rules: free if subtotal ≥ ₹99 AND distance ≤ 2 km; else ₹20. Distance via Google Distance Matrix (mock fallback in dev).
- FR-305 Tax breakdown (GST by product rate) and estimated delivery time shown before payment.
- FR-306 Order placement is transactional: stock check + deduct, voucher consume, coupon mark used, pending payment record.

### 1.4 Orders
- FR-401 Status flow: `pending → accepted → preparing → packed → out_for_delivery → delivered`, plus `cancelled`, `refunded`.
- FR-402 Order timeline events with timestamps (immutable log).
- FR-403 Customer order tracking (list + detail + live status).
- FR-404 Customer can cancel while `pending`/`accepted`; admin can cancel/refund any.
- FR-405 GST invoice PDF generated async after payment success.

### 1.5 Payments (Razorpay)
- FR-501 Create Razorpay Order for checkout; capture payment.
- FR-502 Webhook verification (signature HMAC); idempotent processing; update order status.
- FR-503 Failure handling: mark failed, allow retry (new payment attempt).
- FR-504 Refunds incl. partial refunds with reason, via Razorpay refund API + status sync.
- FR-505 Payment history per customer; invoice downloadable.
- FR-506 All payment methods (UPI, GPay, PhonePe, Paytm, cards, net banking) routed through Razorpay.

### 1.6 Wallet & Vouchers
- FR-601 Every completed purchase ≥ ₹100 earns ₹1 cashback (floor: ₹1 per ₹100; example ₹200 → ₹2).
- FR-602 Cashback is a **ledger balance only — cannot be spent directly**.
- FR-603 When balance ≥ ₹10, an automatic job mints one ₹10 voucher, decrements balance by ₹10 (single transaction, idempotent).
- FR-604 Voucher: single-use, applies to next purchase, cannot convert to cash, has expiry.
- FR-605 Full wallet + voucher usage history for customer and admin.

### 1.7 Customer Debt (Pending Amount)
- FR-701 Customer and admin view outstanding balance.
- FR-702 Only admin updates debt (add debt, record payment, adjust remaining).
- FR-703 Every update writes an immutable ledger entry (debt ledger).

### 1.8 AI
- FR-801 Customer assistant: store timings, products, recommendations, offers, delivery, orders, FAQs.
- FR-802 Admin assistant: sales reports, inventory insights, low stock, best sellers, revenue trends, business suggestions.
- FR-803 Recommendations: frequently-bought-together, recently viewed, similar, popular-nearby, seasonal, fresh, personalized.
- FR-804 AI calls async + cached; answers scoped to authenticated user's own data (no cross-customer leakage).

### 1.9 Admin
- FR-901 Dashboard: today's/monthly sales, revenue, orders, customers, best sellers, inventory, pending orders, refunds, wallet usage, top customers — with charts.
- FR-902 Manage orders, products, inventory, customers, debts, payments, delivery (store_manager).
- FR-903 Bank accounts: add/remove (bank name, account no, IFSC); consent-based transaction/budget view only (never credentials, never scraping).
- FR-904 Store manager: cannot change system settings (RBAC).

### 1.10 Notifications
- FR-1001 SMS/Email/Push/WhatsApp on: order updates, payment success, wallet earned, voucher available, low stock, admin alerts.
- FR-1002 Template-driven; async via Celery; unsubscribe controls.

### 1.11 Reviews & Community
- FR-1101 Reviews with images/videos, star rating, verified-purchase badge.
- FR-1102 Like and report reviews (moderation queue for admin).
- FR-1103 Product questions (Q&A).

### 1.12 Loyalty & Referral
- FR-1201 Wishlist, recently viewed, favorites.
- FR-1202 Referral program (referral code, reward on first completed purchase by invitee).
- FR-1203 Loyalty points (earn/redemption rules admin-configurable).

### 1.13 Multi-Shop
- FR-1301 `Shop` registry for operating config only; all data scoped to `shop_id`; future branches add `Shop` config rows **without** creating additional staff — the admin set remains fixed at 2.

## 2. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-01 | Performance: p95 API < 400 ms (cached catalog), first paint < 2 s on 4G |
| NFR-02 | Availability: 99.9% target; health checks; graceful degradation (mock Maps) |
| NFR-03 | Security: OWASP Top 10; TLS; CSP; audit logs; encrypted secrets |
| NFR-04 | Compliance: PCI-DSS scope minimized (Razorpay hosted); data privacy (India DPDP-ready: consent, deletion) |
| NFR-05 | Accessibility: WCAG 2.2 AA; keyboard nav; screen readers; high contrast; responsive |
| NFR-06 | Maintainability: modular monolith, service layer, repository pattern, PEP8, ESLint/Prettier |
| NFR-07 | Scalability: horizontal worker + web scaling; DB indexed; Redis cache |
| NFR-08 | Reliability: Celery retries with backoff; idempotent webhooks; automatic backups + DR runbook |
| NFR-09 | Localization: ₹ currency, Indian addresses, GST invoices, IN phone format |

## 3. Scope Cut (deliberate, client-pragmatic)
- Single payment aggregator (Razorpay) instead of 6 separate gateway integrations.
- Google/PhonePe/UPI etc. are *payment methods* offered by Razorpay, not separate integrations.
- Bank account **transaction sync** is consent-based via an account aggregator (AA) API when available; without it, admin records balances manually. Never scrapes, never stores credentials.
