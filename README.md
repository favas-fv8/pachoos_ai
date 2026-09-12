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

## Screenshots

### Storefront

![Home](docs/screenshots/01-home.png)
![Shop](docs/screenshots/02-shop.png)
![Product Details](docs/screenshots/05-product-detail.png)
![Cart](docs/screenshots/13-cart-after-add-click.png)
![Checkout](docs/screenshots/15-checkout.png)

### Authentication & Customer

![Login](docs/screenshots/08-login.png)
![Authenticated Home](docs/screenshots/11-after-login-home.png)
![Wishlist](docs/screenshots/17-wishlist.png)
![Profile](docs/screenshots/19-account-profile.png)
![Orders](docs/screenshots/20-account-orders.png)
![Wallet](docs/screenshots/22-account-wallet.png)
![Account Settings](docs/screenshots/24-account-settings.png)

### Orders & Payments

![Payment](docs/screenshots/25-payment-for-new-order.png)
![Completed Order](docs/screenshots/26-account-orders-with-order.png)

### Admin Dashboard

![Admin Dashboard](docs/screenshots/28-admin-dashboard.png)
![Product Management](docs/screenshots/29-admin-products.png)
![Order Management](docs/screenshots/30-admin-orders.png)
![Customer Management](docs/screenshots/32-admin-customers.png)

## Video Demo

Watch the full walkthrough recording: [pachoos-full-app-demo-1440x900.webm](docs/recordings/pachoos-full-app-demo-1440x900.webm).

A screen recording covering the storefront, customer account, checkout and payment, and the admin dashboard. The file is a WebM video (~8 MB) and plays locally in any modern browser.

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
- `docs/screenshots/` — captured screenshots of the platform
- `docs/recordings/` — captured screen recordings

## Project Status

Core architecture, backend/frontend foundations, authentication, product/inventory, and order/cart phases are marked complete in the project documentation. Payments are the next tracked phase, followed by wallet/debt features, AI capabilities, administration, testing, deployment, and final documentation.

## Development Approach

The project uses phased delivery: each phase is documented and reviewed before moving to the next stage. This keeps architecture, product requirements, implementation, and operational concerns aligned as the platform grows.

## Security & Configuration

Secrets and environment-specific configuration should be supplied through deployment environment variables. Payment credentials, AI keys, database passwords, storage credentials, and other sensitive values must never be committed to the repository.

## License

No license file is currently defined in the repository. Please contact the repository owner for reuse or licensing questions.