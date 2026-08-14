# PACHOOS — Phase 2: Backend Foundation

> Django modular-monolith scaffold, layered settings, custom user, observability, service/repository pattern, seeding.

## What was built

### Project layout
```
backend/
├── manage.py
├── pyproject.toml            # ruff (PEP8-ish) + pytest config
├── requirements.txt          # runtime deps (pinned)
├── requirements-dev.txt      # dev tooling
├── .env.example              # env template (copy to .env)
├── .gitignore
├── config/
│   ├── __init__.py           # loads Celery app
│   ├── celery.py             # Celery app (autodiscover tasks)
│   ├── urls.py               # root routes: /, /health/, /api/v1/, /admin/
│   ├── wsgi.py / asgi.py
│   └── settings/
│       ├── __init__.py       # selects dev|prod via DJANGO_ENV, re-exports attrs
│       ├── base.py           # shared settings, DRF, JWT, logging, business rules
│       ├── dev.py            # zero-infra defaults (SQLite + eager Celery)
│       └── prod.py           # hardened: TLS, CSP, JSON logs, strict secrets
└── apps/
    ├── __init__.py
    ├── core/                 # infrastructure
    │   ├── apps.py, models.py        # TimeStamped / UUIDPK / SoftDelete mixins
    │   ├── permissions.py            # RBAC: IsAdmin / IsSuperAdmin / IsAdminOrReadOnly
    │   ├── exceptions.py             # consistent {error:{code,message,details}} envelope
    │   ├── pagination.py             # StandardPagination (count/page/num_pages/…)
    │   ├── views.py                  # /health/ (DB + Redis ping)
    │   ├── urls.py                   # /api/v1/schema|docs|redoc
    │   ├── logging_formatters.py     # JSON log formatter
    │   ├── middleware/               # RequestID, ShopContext, StructuredLogging
    │   ├── services/                 # BaseService + audit() helper + cache helpers
    │   ├── repositories/base.py      # BaseRepository (data access abstraction)
    │   └── management/commands/seed_demo.py
    ├── accounts/             # custom User (2 admins + customers), devices, audit/activity logs
    │   ├── managers.py, models.py, admin.py
    └── shops/                # Shop registry (operating config; single shop today)
        ├── models.py, admin.py
```

### Custom User (accounts.User)
- `role`: `super_admin | store_manager | customer` — exactly **2 staff rows** enforced by `seed_demo` and RBAC permissions.
- Phone-based auth (`USERNAME_FIELD = "phone"`), optional email, Google `google_sub` support.
- OTP state columns (secret, sent_at, attempts, locked_until) ready for Phase 4.
- `UserDevice` rows keyed by hashed refresh token → device tracking + "logout all" (Phase 4).
- `AuditLog` (immutable) + `ActivityLog` (customer-facing) models.

### RBAC (already enforced at the permission layer)
- `IsAdmin` → both admins; `IsSuperAdmin` → super_admin only; `IsAdminOrReadOnly` → authenticated users read, only the 2 admins mutate; `IsCustomer` → customers only.
- These are applied per-view from Phase 4 onward; nothing customer-writable in admin areas.

### Layered settings & 12-factor
- `DJANGO_ENV=dev|prod` selects the module; secrets via `.env` (never committed).
- **Dev runs with zero infra**: SQLite fallback, in-memory eager Celery. PostgreSQL via `DATABASE_URL` when present.
- **Prod fails closed**: missing `DJANGO_SECRET_KEY`/`ALLOWED_HOSTS` raise; TLS/HSTS/CSP headers; JSON-only rendering; admin-only Swagger.

### Observability & health
- `/health/` verifies DB + Redis cache, returns `{status, checks, version, environment}`.
- Request-ID middleware + structured JSON logging (prod) / console (dev).
- Audit + activity logs wired.

## Verified in this phase
```
manage.py check                -> no issues
manage.py makemigrations       -> accounts/shops 0001_initial
manage.py migrate              -> OK
manage.py seed_demo            -> primary shop + exactly 2 admins (idempotent)
GET /health/                   -> 200 {"status":"ok", ...}
GET /api/v1/schema/            -> 200
GET /api/v1/docs/              -> 200 (Swagger)
ruff check apps config         -> all passed
```

## Run locally
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```
Open `http://127.0.0.1:8000/health/` and `http://127.0.0.1:8000/api/v1/docs/`.

## Coming next
- **Phase 3** — Frontend foundation (Vite + React + TS scaffold, design system).
- **Phase 4** — Authentication: OTP (SMS/console sandbox), Google OAuth, JWT refresh rotation, devices, RBAC enforcement on endpoints.