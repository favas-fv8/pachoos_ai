# PACHOOS — Phase 3: Frontend Foundation

> React SPA scaffold with Vite, TypeScript, Tailwind CSS v4, Shadcn-style primitives, React Router, TanStack Query, Redux Toolkit, Framer Motion, light/dark theming.

## What was built (`frontend/`)

```
frontend/
├── index.html                      # Entry HTML (root div, theme-color)
├── package.json                    # All runtime + dev deps (pinned)
├── vite.config.ts                  # Vite + @tailwindcss/vite, proxy to Django
├── tsconfig.json                   # Project references (app + node)
├── tsconfig.app.json               # Strict TS for src/
├── tsconfig.node.json              # For vite.config.ts
├── eslint.config.js                # ESLint flat config (React hooks + refresh)
├── pyproject.toml                  # (in backend/) — ruff + pytest
├── .env.example                    # VITE_API_URL, GOOGLE_REDIRECT, RAZORPAY_KEY_ID
├── .gitignore
└── src/
    ├── main.tsx                    # ReactDOM root + providers (Redux, Query, Router)
    ├── App.tsx                     # Top-level component (renders AppRouter)
    ├── vite-env.d.ts               # Vite client types
    ├── index.css                   # Tailwind v4 @theme tokens + dark mode + base styles
    ├── lib/
    │   ├── utils.ts                # cn(), formatINR(), formatDistanceKm(), getInitials()
    │   ├── queryClient.ts          # TanStack Query client (stale 60s, 2 retries)
    │   └── api/
    │       ├── client.ts           # Axios instance: JWT interceptor, 401 refresh loop
    │       └── tokenStore.ts       # localStorage access/refresh token helpers
    ├── store/
    │   ├── index.ts                # Redux Toolkit configureStore
    │   ├── hooks.ts                # typed useAppDispatch / useAppSelector
    │   └── slices/
    │       └── uiSlice.ts          # theme (light/dark), mobileNavOpen, toasts
    ├── router/
    │   └── index.tsx               # createBrowserRouter + AppRouter (Suspense wrapper)
    ├── components/
    │   ├── layout/
    │   │   ├── app-layout.tsx      # Header + Outlet + Footer + MobileNav + Toaster
    │   │   ├── header.tsx          # Sticky header, nav links, theme toggle, cart/account
    │   │   ├── footer.tsx          # Footer with links + copyright
    │   │   ├── logo.tsx            # PACHOOS brand mark (Leaf icon)
    │   │   └── mobile-nav.tsx      # Slide-in drawer (AnimatePresence + motion)
    │   └── ui/                     # Shadcn-style primitives (all built from scratch)
    │       ├── button.tsx          # Button + ButtonLink (variant/size, CVA)
    │       ├── badge.tsx           # Badge (default/secondary/outline/success/warning/danger)
    │       ├── card.tsx            # Card/CardHeader/CardTitle/CardContent/CardFooter
    │       ├── input.tsx           # Styled <input>
    │       ├── skeleton.tsx        # Pulse placeholder
    │       ├── spinner.tsx         # Lucide Loader2 spinner
    │       └── toaster.tsx         # Animated toast stack (AnimatePresence)
    ├── pages/
    │   ├── Home.tsx                # Hero + categories grid + feature strips
    │   ├── Shop.tsx                # Search bar + product grid skeleton (real grid in Phase 5)
    │   ├── Cart.tsx                # Empty-cart state (real cart in Phase 6)
    │   ├── Account.tsx             # Account section grid (profile, wallet, orders, …)
    │   └── Track.tsx               # Order tracking placeholder + status stepper
    └── types/
        └── index.ts                # Shared TS types (User, Address, Paginated, ApiErrorBody)
```

## Design system

| Token | Value |
|---|---|
| Primary | `#E8762C` (fresh orange) |
| Secondary | `#3E7C4F` (leaf green) |
| Background (light) | `#FDFBF7` |
| Surface (light) | `#FFFFFF` |
| Ink | `#1F2933` |
| Muted | `#6B7280` |
| Border | `#E8E2D6` |
| Fonts | Inter (UI) + Fraunces (display) |
| Radius | 0.75rem cards, 999px pills |
| Shadows | soft layered (`shadow-card`, `shadow-pop`) |
| Dark mode | `.dark` class, CSS custom-property override |
| Motion | Framer Motion micro-interactions (120–200 ms ease-out) |
| Accessibility | WCAG 2.2 AA, keyboard nav, screen-reader labels, reduced-motion respect |

## Key wiring

- **TanStack Query** — `queryClient` with 60 s stale time, 2 retries (no retry on 4xx), `refetchOnWindowFocus: false`. Ready for all future data-fetching.
- **Redux Toolkit** — `ui` slice (theme, mobileNavOpen, toasts). Auth/cart slices to be added in later phases.
- **Axios API client** — attaches `Authorization: Bearer <token>` header; on 401 triggers a single refresh attempt via `/api/v1/auth/token/refresh/`; dispatches `pachoos:unauthorized` custom event on permanent failure.
- **React Router v6** — lazy-loaded routes with `Suspense` fallback (`<Spinner />`), `ScrollRestoration` on layout.
- **Theme sync** — `useThemeSync()` hook keeps `<html>` class in sync with Redux `ui.theme`; persisted to `localStorage`; respects `prefers-color-scheme`.
- **Proxy** — Vite dev-server proxies `/api/*` and `/health` to `http://127.0.0.1:8000` (configurable via `VITE_API_PROXY_TARGET`).

## Verified

```
npm run typecheck   → 0 errors
npm run build       → ✓ 2024 modules, 3.76 s, ~145 KB gzip
```

## Next phases

- **Phase 4** — Authentication screens (OTP login, Google OAuth callback, JWT storage/refresh, device management).
- **Phase 5** — Product catalog (grid, search, filters, product detail, variants).
- **Phase 6** — Cart & checkout (cart state, delivery rules, coupon/voucher engine).
- **Phase 7** — Payments (Razorpay checkout sheet, webhook handling UI).
- **Phase 8** — Wallet & vouchers UI (cashback ledger, voucher minting animation, redemption).
- **Phase 9** — AI assistant (chat UI).
- **Phase 10** — Admin dashboard (charts, KPI cards, datatables).