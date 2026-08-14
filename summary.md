# Summary

## Objective
Modify the existing PACHOOS admin and customer modules to add/edit/delete customers, show linked offline debt in admin customer details, add back buttons throughout, remove the (non-existent) admin wallet section, add bank account management for both admins and customers, and verify all changes work correctly.

## Important Details
- **Admin Wallet section**: Already absent in the admin sidebar (sidebar has Dashboard, Products, Orders, Customers, Debt Book, Notifications, Settings). No removal needed; customer wallet data fully preserved.
- **Bank account encryption**: AES-GCM via `cryptography` library (already in venv). Full account number never exposed by any API; only last 4 digits shown masked (`••••1234`). Never store online-banking passwords, PINs, or credentials.
- **Customer delete** = soft-delete (`is_active=False`); all orders, wallet ledger, and debt history stays intact. Hard delete would fail for customers with orders (FK `PROTECT` on orders model).
- **Admin customer edit**: limited to `full_name`, `phone` (10-digit validated via `validate_phone`), `email` (format validated via `validate_email`). Phone/email deduped against other accounts. Staff accounts cannot be edited/deleted.
- **"Admin Payment" section** did not exist in the admin sidebar; created dedicated `/admin/payments` page and `/api/v1/payments/bank-accounts/` endpoints with full CRUD, masked display, and validation.
- **Customer bank accounts** under `/account/payments` and `/api/v1/payments/my/bank-accounts/`; scoped to owning user only via permission `IsCustomer`. 
- **Frontend typecheck** passes (`tsc -b --noEmit` clean). **Backend**: 196 tests pass (including new bank account CRUD, RBAC, customer edit/delete, debt intact, validation).

## Work State

### Completed
- **BankAccount model** (`apps/payments/models.py`) with encrypted `account_number_encrypted`, `account_number_last4`, `ifsc`, `is_active`, `shop`/`user` FKs.
- **BankAccount serializers** (`apps/payments/serializers.py`) with IFSC regex validation, account number digit validation, masked output (`account_number_masked`).
- **BankAccount views** (`apps/payments/views.py`) — admin list/create/detail/delete, customer list/create/detail-delete (own-only scoping, 404 for others).
- **BankAccount URLs** (`apps/payments/urls.py`) under `/api/v1/payments/bank-accounts/` and `/my/bank-accounts/`.
- **AES-GCM encryption module** (`apps/payments/encryption.py`) with `encrypt_account_number`, `decrypt_account_number`, `mask_account_number`, `normalize_account_number`.
- **Admin customer edit** (`apps/admin_dashboard/views.py` `CustomerDetailView.patch`/`delete`) with safe profile updates and soft-delete preserving all financial history.
- **Admin customer services** (`apps/admin_dashboard/services.py`) — `get_customer_list` (excludes inactive), `get_customer_detail` (full linked Debt Book via `DebtBookDetailSerializer`), `update_customer`, `deactivate_customer`, audit via `record_admin_activity`.
- **Admin Customers page** (`frontend/src/pages/admin/customers.tsx`) — Edit (inline form for name/phone/email) and Delete (confirmation, financial history preserved) buttons; full linked Debt Book rendered with summary cards, transaction/bill items with quantities/prices/discounts, remaining balances, notes, and "Open in Debt Book" link.
- **Admin Payments page** (`frontend/src/pages/admin/payments.tsx`) — Shop bank account list/add/edit/delete with masked numbers, status badges, validation.
- **Customer Payments page** (`frontend/src/pages/account/Payments.tsx`) — Bank account section (list/add/edit/delete own accounts, masked) plus existing payment history.
- **Shared BackButton component** (`frontend/src/components/ui/back-button.tsx`) with smart history-aware navigation (use `navigate(-1)` when browser history exists; fallback to explicit `to` prop).
- **Back buttons wired** on: Admin products, orders, notifications, settings, debt-book, customers; Customer Profile, Orders, Payments, Wallet, DebtBook, Settings, Shop, Checkout, Track, Wallet (`/wallet`).
- **Tests**: 196 backend tests pass (bank account CRUD + RBAC, customer edit/delete + debt intact, validation). Frontend typecheck clean.

### Active
- Running verification against all 7 numbered user requirements; minor edge-case refinements possible (e.g., products internal back button coexists with dashboard back).

### Blocked
- None.

## Next Move
1. Run full test suite one final time to confirm all 196+ tests pass and no regressions.
2. Manually walk through each user story: admin edit/delete customer, verify linked offline debt appears in customer detail, test back buttons navigate correctly, confirm admin wallet already absent, add/manage shop and customer bank accounts, verify masked display and validation.
3. If all checks pass, the implementation is complete.

## Relevant Files
- `backend/apps/payments/models.py` — BankAccount model (encrypted account number, IFSC, status, shop/user ownership)
- `backend/apps/payments/encryption.py` — AES-GCM encrypt/decrypt/mask for bank account numbers at rest
- `backend/apps/payments/serializers.py` — BankAccountWriteSerializer, BankAccountAdminWriteSerializer, BankAccountSerializer (masked output)
- `backend/apps/payments/views.py` — AdminBankAccountListCreateView, AdminBankAccountDetailView, CustomerBankAccountListCreateView, CustomerBankAccountDetailView
- `backend/apps/payments/urls.py` — /api/v1/payments/bank-accounts/ and /my/bank-accounts/ routes
- `backend/apps/admin_dashboard/services.py` — get_customer_list (excludes inactive), get_customer_detail (full Debt Book), update_customer, deactivate_customer, record_admin_activity
- `backend/apps/admin_dashboard/views.py` — CustomerDetailView with PATCH/DELETE handlers
- `backend/apps/admin_dashboard/tests/test_customer_management.py` — Tests for edit, delete, list exclusion, audit, full debt book
- `backend/apps/payments/tests/test_bank_accounts.py` — Tests for encryption, RBAC, validation, admin/customer CRUD
- `frontend/src/components/ui/back-button.tsx` — Shared back navigation component
- `frontend/src/pages/admin/payments.tsx` — Admin bank account management page
- `frontend/src/pages/admin/customers.tsx` — Admin customers with edit/delete + full linked debt book
- `frontend/src/pages/account/Payments.tsx` — Customer bank account section + payment history
- `frontend/src/pages/admin/notifications.tsx` — Back button to dashboard
- `frontend/src/pages/admin/settings.tsx` — Back button to dashboard
- `frontend/src/pages/account/Profile.tsx` — Back button to /account
- `frontend/src/pages/account/Orders.tsx` — Back button to /account
- `frontend/src/pages/account/Wallet.tsx` — Back button (navigate-1 or /account fallback)
- `frontend/src/pages/account/DebtBook.tsx` — Back button to /account
- `frontend/src/pages/account/Settings.tsx` — Back button to /account
- `frontend/src/pages/Shop.tsx` — Back button to /
- `frontend/src/pages/Checkout.tsx` — Back button to /cart
- `frontend/src/pages/Track.tsx` — Back button to /account/orders