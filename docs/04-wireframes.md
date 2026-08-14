# PACHOOS — Wireframes & UX (Phase 1)

> Design language: minimal, premium, "Apple-grade" polish. Mobile-first, fluid to desktop. Light + dark mode. Framer Motion micro-interactions. WCAG 2.2 AA. Brand tone: warm, fresh, artisan bakery.

## 1. Design Tokens
- **Fonts**: Inter (UI) + a display serif for headings (e.g. "Fraunces") for the grocery/artisan feel.
- **Colors (light)**: BG `#FDFBF7`, surface `#FFFFFF`, primary `#E8762C` (fresh orange), secondary `#3E7C4F` (leaf green), ink `#1F2933`, muted `#6B7280`.
- **Colors (dark)**: BG `#0F1115`, surface `#171A1F`, same accent hues.
- **Radius**: 14px cards, 999px pills. **Shadow**: soft, layered.
- **Spacing**: 4px grid. **Motion**: 120–200 ms ease-out, spring for add-to-cart.

## 2. Navigation Map

```
[Customer App (shop.pachoos.com)]
  Home
   ├ Hero (fresh fruits & bakery rotating)
   ├ Categories grid (Bakery / Fruits / Seasonal)
   ├ Best sellers carousel
   ├ Fresh-arrivals strip
   ├ Seasonal/seasonal-fruits
   └ AI assistant FAB (bottom-right)
  Shop
   ├ Category → Subcategory → Product grid (filters left/bottom-sheet)
   └ Product filters: price/popularity/newest/discount/rating/availability/freshness
  Product Detail
   ├ Image gallery + video, variant selector (500g/1kg/2kg)
   ├ price, discount, GST, stock, freshness badge
   ├ Add to cart, wishlist, share
   ├ Reviews (verified badge, like/report), Q&A
   └ Frequently-bought-together
  Cart       → items, coupon, voucher, wallet note, delivery charge, tax, ETA, checkout
  Checkout   → address (add/select), payment method, place order
  Pay        → Razorpay sheet/hosted
  Account
   ├ Profile, addresses (default flag), devices/sessions
   ├ Orders (status timeline, track, cancel)
   ├ Payments history + invoice download
   ├ Wallet (cashback ledger + vouchers) — read-only balance + minted vouchers
   ├ Voucher history  ├ Debt (view only)
   ├ Wishlist, recently viewed  ├ Reviews
   ├ Referral, loyalty
   └ Logout / logout-all
  Auth      → Login/Register: mobile OTP or Google; dev-mode OTP shown inline
  AI Chat   → floating assistant, contextual answers + quick actions

[Admin (admin.pachoos.com)]  ← only the 2 admins (super_admin, store_manager)
  Dashboard  → KPI cards (today/monthly sales, revenue, orders, customers,
              best sellers, pending, refunds, wallet usage, top customers) + charts
  Orders     → datatable, status stepper, assign delivery, cancel/refund
  Products   → CRUD, variants, images/video, tags, stock, freshness, low-stock alerts
  Inventory  → stock movements, purchases/restock, low-stock, stock history
  Customers  → list, profile, wallet, vouchers, debt management
  Debts      → ledger, add debt / record payment / adjust; audit trail
  Payments   → transactions, refunds(partial), failed/retry
  Wallet     → global cashback stats, voucher issues
  Coupons    → create/manage percent/flat/BOGO
  Bank       → add bank accounts, consent-based txn view, balances
  Reports    → sales/inventory charts, exports
  Store      → shop profile, delivery rules, GSTIN, timings
  AI         → admin assistant (sales/inventory/revenue chat)
  Settings   → super_admin only; store manager: NOT editable (locked)
```

## 2. Key Screen Wireframes (ASCII)

### Home (mobile)
```
┌──────────────────────────────┐
│ PACHOOS  🛒(3)  🔍  ☰        │  header
├──────────────────────────────┤
│  🎠 Hero: "Fresh every day"  │
│     [Order Now]              │
├──────────────────────────────┤
│ CATEGORIES                   │
│ [🍰Bakery] [🍏Fruits] ...     │
├──────────────────────────────┤
│ Best Sellers  →              │
│ ┌────┐ ┌────┐ ┌────┐         │
│ │img │ │img │ │img │         │  ← horizontal carousel
│ ├ ₹399 ├ ₹149 ├ ₹299 │        │
│ └────┘ └────┘ └────┘         │
├──────────────────────────────┤
│ ✨ AI assistant  floats ▸     │
└──────────────────────────────┘
```

### Product Detail
```
┌──────────────────────────────┐
│        [ Main image ]         │
│  [thumb][thumb][video ▶]     │
├──────────────────────────────┤
│ Chocolate Cake          ❤    │
│ ⭐ 4.7 (128)  Fresh  GST 5%  │
│ 500g ₹399 ☑ 1kg ₹749 □ ...   │ ← variant pills
│ [−] 1 [+]                       │
│ ₹399 · Free delivery · 40 min  │
│ Ingredients / Nutrition  ▾    │
│  Frequently bought together:  │
│  [Croissant] + [Juice] = ₹... │
│ ───────────────────────────── │
│ [  Add to Cart  ]  🛒        │ ← sticky CTA
└──────────────────────────────┘
```

### Checkout
```
┌──────────────────────────────┐
│ 1 Delivery  2 Payment         │
│ Address: {delivery_address}   │
│   Free / +₹20 · 40 min · 1.2km│
├──────────────────────────────┤
│ Coupon code  [APPLY]  ✓        │
│ Voucher:  [₹10 - 12AB34CD] ✓  │  ← from wallet, optional
├──────────────────────────────┤
│ Items .......... 3 · ₹748     │
│ Discount ............... −₹50│
│ Delivery ............. FREE │
│ GST (5%) ................. ₹19│
│ Total ................. ₹717 │
├──────────────────────────────┤
│ Pay: 💳 Cards · 📱 UPI(GPay/  │
│  PhonePe/Paytm) · 🏦 NetBank   │
│ [ Pay ₹717 securely ]          │ ← opens Razorpay
└──────────────────────────────┘
```

### Order Timeline
```
┌──────────────────────────────┐
│ Order #PCH-20260803-0012      │
│ ● Pending      ✓ 10:02 ● done │
│ ● Accepted     ✎ 10:05    ●   │
│ ○ Preparing              ○   │
│ ○ Packed                ○     │
│ ○ Out for delivery        ○   │
│ ○ Delivered              ○    │
│               [Track on map]  │
└──────────────────────────────┘
```

### Admin Dashboard
```
┌──────────────────────────────────┐
│ Today ₹4,210 │ Month ₹98,400 │ ..│  ← KPI cards
│ Orders 312  Revenue ...          │
├───────────────┬──────────────────┤
│ Sales (line)  │ Best sellers     │
│ charts        │ (bar list)       │
├───────────────┼──────────────────┤
│ Orders by st. │ Top customers    │
│ (donut)       │ Inventory alerts │
└───────────────┴──────────────────┘
```

## 3. Flow Rules (UX logic)
- **Add to cart** → flying-saucer animation into cart badge; cart badge persists across app reload (persisted cart).
- **Voucher auto-mint** is server-side; UI shows a "🎉 New ₹10 voucher!" toast + notification when the celery job mints one.
- **Cashback** shown as a passive ledger in Account → Wallet; card explains "Redeem into ₹10 vouchers" with a call-to-action to view vouchers.
- **Debt** shown to customer as an unobtrusive banner on Account → "You have ₹240 pending — view details"; admin manages via dedicated screen.
- **Delivery free logic** is computed server-side and echoed with a friendly note in cart.
- **AI assistant** uses quick-reply chips (Timings, Best sellers, Track order) to minimize typing.

## 4. Accessibility & Responsive Checklist
- All interactive elements focusable; visible focus rings; `aria-label`s on icon buttons.
- Lazy-loaded images with `alt`; semantic headings; skip-to-content link.
- WCAG contrast ≥ 4.5:1; both themes tested.
- Keyboard order matches visual order; carousels are scroll containers (not keyboard traps).
- Breakpoints: 375 / 768 / 1024 / 1440; bottom-sheet mobile nav → fixed top nav desktop.