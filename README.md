# PACHOOS — Bakery & Fruit Ordering Platform

A production-oriented local ordering platform for a bakery and fruit business, designed with a modular architecture that can support additional branches as the product evolves.

## Product Scope

PACHOOS is being developed as a complete commerce platform covering customer ordering, inventory, payments, wallets, vouchers, debt tracking, AI assistance, administration, testing, and deployment.

## Technology Stack

- **Frontend:** React, Vite, TypeScript, Tailwind CSS, Redux Toolkit, TanStack Query, React Router
- **UI & Motion:** shadcn/MUI, Framer Motion
- **Backend:** Django, Django REST Framework, Celery, Redis, JWT
- **Data:** PostgreSQL
- **Storage:** S3 / Cloudinary
- **Payments:** Razorpay
- **Location:** Google Maps distance services
- **AI:** OpenAI integration
- **Delivery:** Docker, Nginx, Gunicorn, GitHub Actions, Vercel

## Development Roadmap

| Phase | Area | Status |
|---:|---|:---:|
| 1 | Architecture, requirements, ER diagram, wireframes | Complete |
| 2 | Backend foundation | Complete |
| 3 | Frontend foundation | Complete |
| 4 | Authentication | Complete |
| 5 | Products & inventory | Complete |
| 6 | Orders & cart | Complete |
| 7 | Payments & invoices | Next |
| 8 | Wallet, vouchers & debts | Planned |
| 9 | AI assistant & recommendations | Planned |
| 10 | Admin dashboard | Planned |
| 11 | Testing | Planned |
| 12 | Deployment & CI/CD | Planned |
| 13 | Documentation | Planned |

The detailed phase documents are maintained under `docs/`.

## Documentation

- `docs/01-architecture.md` — system architecture
- `docs/02-requirements.md` — product requirements
- `docs/03-database-schema.md` — database / ER design
- `docs/04-wireframes.md` — UX and wireframes
- `docs/05-backend-foundation.md` — backend foundation
- `docs/06-frontend-foundation.md` — frontend foundation
- `docs/07-auth.md` — authentication
- `docs/05-products-inventory.md` — products and inventory
- `docs/06-orders-cart.md` — orders and cart

## Project Status

Core architecture, backend/frontend foundations, authentication, product/inventory, and order/cart phases are marked complete in the project documentation. Payments are the next tracked phase, followed by wallet/debt features, AI capabilities, administration, testing, deployment, and final documentation.

## Development Approach

The project uses phased delivery: each phase is documented and reviewed before moving to the next stage. This keeps architecture, product requirements, implementation, and operational concerns aligned as the platform grows.

## Security & Configuration

Secrets and environment-specific configuration should be supplied through deployment environment variables. Payment credentials, AI keys, database passwords, storage credentials, and other sensitive values must never be committed to the repository.

## License

No license file is currently defined in the repository. Please contact the repository owner for reuse or licensing questions.
