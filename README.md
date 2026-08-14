# PACHOOS — Bakery & Fruits Shop Platform

Production-grade local ordering platform for a bakery & fruit business. Built to scale to additional branches.

## Stack
- **Frontend**: React · Vite · TypeScript · Tailwind · Shadcn/MUI · Redux Toolkit · TanStack Query · React Router · Framer Motion
- **Backend**: Django · DRF · Celery · Redis · JWT
- **Data / Infra**: PostgreSQL · S3/Cloudinary · Razorpay (pay) · Google Maps Distance · OpenAI
- **Delivery**: Docker · Nginx · Gunicorn · GitHub Actions · Vercel

## Phases
Tracked in `docs/`. Each phase pauses for approval before the next.

| # | Phase | Status |
|---|-------|--------|
| 1 | Architecture, Requirements, ER Diagram, Wireframes | ✅ |
| 2 | Backend foundation | ✅ |
| 3 | Frontend foundation | ✅ |
| 4 | Authentication | ✅ |
| 5 | Products & Inventory | ✅ |
| 6 | Orders & Cart | ✅ |
| 7 | Payments (Razorpay, invoices) | ⏳ next |
| 8 | Wallet & Vouchers + Debts | |
| 9 | AI assistant & recommendations | |
| 10 | Admin dashboard | |
| 11 | Testing | |
| 12 | Deployment (Docker, CI/CD) | |
| 13 | Documentation | |

## Quick links
- [System Architecture](docs/01-architecture.md)
- [Requirements](docs/02-requirements.md)
- [Database / ER Diagram](docs/03-database-schema.md)
- [Wireframes & UX](docs/04-wireframes.md)
- [Backend Foundation (Phase 2)](docs/05-backend-foundation.md)
- [Frontend Foundation (Phase 3)](docs/06-frontend-foundation.md)
- [Authentication (Phase 4)](docs/07-auth.md)
- [Products & Inventory (Phase 5)](docs/05-products-inventory.md)
- [Orders & Cart (Phase 6)](docs/06-orders-cart.md)

(A full `README` — install/run guide — lands in Phase 13.)