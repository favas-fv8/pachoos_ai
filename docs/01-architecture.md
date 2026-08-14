# PACHOOS — System Architecture (Phase 1)

> Bakery & Fruits Shop — local online ordering platform.
> Design goal: production-grade, secure, scalable to multiple branches.

## 1. Architectural Style

- **Frontend**: React SPA (Vite + TypeScript + Tailwind + Shadcn UI), deployed to Vercel (static).
- **Backend**: Django + Django REST Framework, **single deployable service** with an internal, horizontally-scalable architecture (services / repositories / tasks).
- **API**: REST under `/api/v1/`, JWT (access + refresh), Swagger/OpenAPI docs, versioned.
- **Async**: Celery + Redis for SMS, email, push, invoice PDFs, AI calls, analytics snapshots, and the wallet/voucher auto-mint job.
- **Database**: PostgreSQL 16 (single shared instance; `shop_id` on transactional tables keeps the schema branch-ready for the future without changing the staff model).
- **Staff model (important)**: there are exactly **2 admin users** — `super_admin` and `store_manager` — plus unlimited `customer` users. There are **no per-shop staff accounts** and no staff accounts linked to multiple shops. Products and all backend management are authored **only by the 2 admins**. A single primary `Shop` record holds the business's delivery/payment/GST config; future branches add `Shop` rows for *configuration*, but do **not** create additional admin users.
- **Payments**: Razorpay as the single aggregator covering UPI, Google Pay, PhonePe, Paytm, cards, net banking. Webhook-first verification; never trust the client callback.
- **Maps**: Google Maps Distance Matrix API behind a repository with a mock fallback for development.
- **AI**: OpenAI (ChatGPT) via a thin assistant service; all calls are async, cached, and prompt-injection-hardened.

## 2. High-Level Component Diagram

```
                        ┌─────────────────────────────┐
                        │  Browser  /  Mobile          │
                        │  React SPA (Vercel / CDN)    │
                        └──────────────┬──────────────┘
                                       │ HTTPS + JWT
                        ┌──────────────▼──────────────┐
                        │   Nginx (reverse proxy, TLS) │
                        └──────────────┬──────────────┘
                        ┌──────────────▼──────────────┐
                        │   Gunicorn (Django ASGI/WSGI)│
                        │   - REST /api/v1/*          │
                        │   - Auth (JWT, OTP, OAuth)  │
                        │   - Services layer          │
                        └──────┬───────────┬──────────┘
                               │           │
                ┌──────────────▼──┐   ┌────▼───────────────┐
                │   PostgreSQL     │   │   Redis            │
                │   (primary DB)   │   │  cache, rate-limit │
                │   + backups      │   │  Celery broker/    │
                │                  │   │  result backend    │
                └──────────────────┘   └────┬───────────────┘
                                           │
                              ┌────────────▼─────────────┐
                              │   Celery workers          │
                              │  SMS/Email/Push, PDFs,   │
                              │  AI, wallet mint, stats   │
                              └────────────┬─────────────┘
                                           │
   ┌─────────────┐  ┌──────────────┐  ┌────▼────────────┐  ┌───────────────┐
   │ Razorpay    │  │ Google Maps   │  │ OpenAI          │  │ SMS/Email/Push │
   │ (pay/refund)│  │ Distance API  │  │ (assistant)     │  │ providers      │
   └─────────────┘  └──────────────┘  └─────────────────┘  └───────────────┘
```

## 3. Module / App Layout (Django)

Monolith-deployed, modularly-organized. Each `apps/*` owns its models, serializers, views, services, repositories, tasks, and tests — this is a **modular monolith**, the correct starting point for one shop that may grow.

| App | Responsibility |
|---|---|
| `core` | Settings, health checks, base models, audit logging, rate limiting |
| `accounts` | Users, roles (RBAC), devices, OTP, Google OAuth, sessions |
| `shops` | Shop/branch registry (multi-shop readiness) |
| `catalog` | Categories, subcategories, products, variants, inventory, stock history |
| `cart` | Cart sessions, cart items |
| `orders` | Orders, order items, timeline, tracking, delivery rules |
| `payments` | Razorpay integration, webhooks, refunds, invoices |
| `wallet` | Cashback ledger, voucher pool, voucher redemptions |
| `debt` | Customer pending-debt ledger |
| `rewards` | Coupons, referral, loyalty |
| `reviews` | Reviews, ratings, product questions |
| `notifications` | SMS/Email/Push/WhatsApp channels, templates |
| `ai` | Assistant (customer/admin), recommendations |
| `analytics` | Dashboard stats, cached snapshots, reports |
| `banks` | Bank accounts + consent-based transaction views |
| `delivery` | Google Maps distance, delivery fee rules |

## 4. Cross-Cutting Concerns

### Security (OWASP Top 10 mapping)
- **A01 Broken Access Control** → RBAC via permission classes + `shop_id` scoping; every serializer validates ownership.
- **A02 Crypto Failures** → HTTPS only, TLS 1.2+, Django SECURE_* settings, encrypted secrets via `.env`/Vault, ARGON2 password hashing.
- **A03 Injection** → ORM-only queries (no raw SQL), parameterized everything, allow-listed input validators.
- **A04 Insecure Design** → threat-modeled flows; idempotent webhooks; voucher mint is a transaction.
- **A05 Misconfiguration** → env-driven settings, `DEBUG=False` gated, CSP + security headers, no default credentials.
- **A06 Vulnerable Components** → pinned deps, Dependabot/Renovate, `pip-audit` + `npm audit` in CI.
- **A07 Auth Failures** → JWT short-lived access + rotating refresh tokens, OTP with TTL + max-attempt lockout, brute-force throttling.
- **A08 Integrity Failures** → webhook signature verification (Razorpay HMAC), signed invoice URLs, voucher single-use enforcement in a DB transaction.
- **A09 Logging Failures** → structured JSON logging, audit + activity logs.
- **A10 SSRF** → AI/geocoding calls go through allow-listed hosts; URL fields validated.

### Performance
- Lazy-loaded React routes + image `loading="lazy"`.
- Redis caching for catalog, trending searches, dashboard snapshots.
- Database indexes on every FK + high-traffic columns; `select_related`/`prefetch_related`.
- Pagination on every list endpoint (cursor for feeds, offset for admin).
- Celery for all slow work (PDFs, AI, SMS/email, snapshotting).

### Observability
- Health endpoint `/api/v1/health/` (DB + Redis + Celery ping).
- Structured logs; optional Sentry; Prometheus metrics later.

## 5. API Versioning & Conventions

- All routes under `/api/v1/`.
- REST nouns + verbs; consistent error envelope:
  ```json
  { "error": { "code": "VALIDATION_ERROR", "message": "...", "details": {} } }
  ```
- Swagger at `/api/v1/docs/`, ReDoc at `/api/v1/redoc/`.
- Rate limits: auth endpoints (login/OTP) tight; catalog loose; admin tighter.

## 6. Staff & Multi-Shop Strategy

- **Exactly two admins**: `super_admin` (full control, incl. system settings) and `store_manager` (orders, products, inventory, customers, debts, payments, delivery — no system settings). Both are seeded as fixed, non-deletable staff users.
- **Only the 2 admins** can create/update/delete products, categories, coupons, and inventory. Customers have read access to catalog only.
- A `Shop` registry exists for the business's operating config (name, address, geocode, timings, GSTIN, delivery rules, logo). Staff are bound to this single shop.
- All transactional tables carry `shop_id` for future branch expansion, but adding a branch **never** adds admin/staff accounts — staff is fixed at 2.
- Requests resolve shop via header `X-Shop-Id` (defaults to the primary shop) → enforced in a middleware.

## 7. Deployment Topology

| Component | Target |
|---|---|
| Frontend | Vercel (static, CDN, edge) |
| Backend | Ubuntu VPS / Railway / DO App Platform — Docker image |
| DB | Managed PostgreSQL (auto-backups) or VPS with pgBackRest cron |
| Redis / Celery | Same Docker network or managed Redis |
| CI/CD | GitHub Actions: lint → test → build → push → deploy |

## 8. Tech Decisions & Rationale

| Decision | Why |
|---|---|
| Razorpay single gateway | Covers all listed Indian payment methods via one API + webhooks; less attack surface |
| Voucher-pool wallet | Matches the "cannot spend cashback directly" rule; money-neutral, simple to audit |
| Modular monolith | Right scale for 1 shop now; path to microservices if branches grow |
| Celery + Redis | Async SMS/email/PDF/AI keeps request path fast |
| DRF + JWT | Mature, standard for this stack; refresh rotation for security |
| S3 / Cloudinary (storage adapter) | Uploaded images/videos never hit the app server |
