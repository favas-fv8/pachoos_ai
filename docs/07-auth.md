# PACHOOS — Phase 4: Authentication

> Firebase Phone Auth (SMS OTP), Google OAuth 2.0, email OTP (password recovery),
> customer Sign In / Sign Up with strong passwords, admin sign-in, JWT access +
> refresh with rotation, device tracking, RBAC enforcement, audit logging.

## Backend auth endpoints (`/api/v1/auth/`)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/customer/signup/` | public | Customer Sign Up. `provider=phone` (Firebase ID token from phone OTP) or `provider=google` (registration token from Google OAuth) + strong password → creates account + JWT pair. |
| POST | `/customer/login/` | public | Customer Sign In. `identifier` = phone **or** registered email + `password` → JWT pair. |
| POST | `/password/reset/` | public | Forgot/Reset password after proving identity. `verification=firebase` (ID token) or `verification=email` (`identifier` + `otp`) + `new_password`. Revokes every session. |
| POST | `/otp/send/` | public | Send a 6-digit **email** OTP for password-recovery identity verification. |
| POST | `/otp/resend/` | public | Resend a password-recovery email OTP after the cooldown; invalidates the previous code. |
| POST | `/admin/login/` | public | Admin Sign In (email/password). No self-registration exists. |
| POST | `/google/callback/` | public | Exchange Google auth code. Existing identity → JWT pair; new identity → `registration_required` + short-lived `registration_token` to complete Sign Up. |
| POST | `/token/refresh/` | public | Rotate refresh token → new access token. Validates against active device rows. |
| GET | `/me/` | auth | Current user profile. |
| GET | `/devices/` | staff | List active device sessions for the authenticated user. |
| POST | `/devices/revoke/` | staff | Revoke a single device by `token_hash`. |
| POST | `/devices/revoke-all/` | staff | Revoke every active device ("logout everywhere"). |

> The legacy **email OTP login** and self-hosted phone OTP login are removed.
> `otp.py` now only serves password-recovery email verification. Phone OTP is
> handled entirely by Firebase (`apps/accounts/firebase.py`).

## Customer authentication (`apps/accounts/views.py`)

- **Sign Up — Phone**: Firebase Phone Auth sends the SMS OTP client-side; the
  client submits the Firebase ID token + a strong password. Backend verifies the
  token, rejects duplicate phone numbers, and hashes the password with Django's
  Argon2/PBKDF2 hashers.
- **Sign Up — Google**: "Continue with Google" → OAuth callback → new identity
  gets a signed `registration_token` (10 min TTL); the frontend collects name +
  password and completes sign-up. Duplicate Google emails/subs are rejected.
- **Sign In — Phone**: phone number + password.
- **Sign In — Google**: one-tap "Continue with Google", or the registered Google
  email + password.

## Firebase verification (`apps/accounts/firebase.py`)

- `verify_id_token` validates Firebase ID tokens via the Admin SDK
  (`firebase_admin`). Production enforces signature/issuer/audience/expiry.
- Sandbox mode (no `FIREBASE_PROJECT_ID`) decodes claims without signature
  verification so the flow works end-to-end in dev and tests.
- Credentials come only from environment variables:
  `FIREBASE_PROJECT_ID`, `FIREBASE_CREDENTIALS_PATH`, `FIREBASE_CREDENTIALS`.

## Email OTP service (`apps/accounts/otp.py`)

- Used only for password-recovery identity verification (Google accounts, admins).
- 6-digit **numeric** OTP via `secrets.randbelow` (cryptographically secure).
- Stored **hashed** (SHA-256) in the cache with a 5-minute TTL — never plaintext.
- Expiry, max **5 verify attempts** (locks the code), **30s resend cooldown**,
  per-identifier send quota (5/hour), and per-IP quota (10/hour).
- Email delivery uses Django's `EMAIL_BACKEND` (SMTP / SendGrid / Mailgun /
  AWS SES), configured entirely through environment variables.

## Google OAuth (`apps/accounts/views.py`)

- Authorization-code flow (not implicit).
- In dev/sandbox (no `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`): accepts any code and returns a mock profile.
- Production: exchanges code at `https://oauth2.googleapis.com/token`, fetches userinfo at `https://www.googleapis.com/oauth2/v3/userinfo`.
- `GOOGLE_REDIRECT_URI` must match the Google Cloud Console config.

## Passwords

- Created at registration (both phone and Google sign-up) and via forgot/reset.
- Stored with Django password hashing (Argon2 preferred, PBKDF2 fallback).
- Strong-password policy enforced on both client and server:
  min 8 chars, uppercase, lowercase, number, special character
  (`validate_password_strength` in `serializers.py`).

## JWT + device tracking

- `JWT_ACCESS_TTL_MINUTES` (default 15) + `JWT_REFRESH_TTL_DAYS` (default 14).
- `ROTATE_REFRESH_TOKENS = True` — every refresh invalidates the old token.
- Device sessions are `UserDevice` rows keyed by `sha256(refresh_token)`. Revocation is instant and persists.
- **Password reset revokes every active session** for the user — they must sign in again.
- "Logout from all devices" → `POST /auth/devices/revoke-all/` sets `revoked_at` on every active `UserDevice`.

## RBAC + rate limiting + audit

- Identity endpoints carry a strict throttle (scope `auth`, 5/min) on top of the
  existing per-identifier/per-IP OTP quotas.
- Device list/revoke/revoke-all → `IsAdmin` (the 2 staff roles only).
- Admin Sign In is the only admin path — there is **no admin self-registration**.
- Password resets append an immutable `AuditLog` entry (`action=password.reset`).

## Frontend auth pages

| Route | Component | Description |
|---|---|---|
| `/login` | `Login` | Customer (Sign In / Sign Up toggle) + Admin modes. Sign In: Phone+Password / Google (OAuth or email+password). Sign Up: Phone (Firebase OTP + password) / Google (OAuth + password). Admin: email/password, no sign-up. |
| `/forgot-password` | `ForgotPassword` | Identity verification (phone OTP or registered email) → set new password. Shared `PasswordResetForm` component. |
| `/auth/register` | `GoogleRegister` | Completes Google Sign Up: collect name + strong password from the registration token. |
| `/auth/google/callback` | `AuthCallback` | Exchanges Google code; routes new identities to `/auth/register`. |
| `/account/settings` | `Settings` | Customer Reset Password (OTP/verification required; sessions invalidated). |
| `/admin/settings` | `admin/settings` | Admin Reset Password via registered email verification. |

## Auth state (`authSlice`)

- `access`, `refresh`, `user`, `isAuthenticated`, `isLoading`.
- `setCredentials` stores tokens in Redux + triggers API client interceptor.
- `logout` clears Redux + localStorage tokens.

## API client refresh logic (`client.ts`)

- On 401: single refresh attempt via `/auth/token/refresh/`.
- If refresh fails → dispatches `pachoos:unauthorized` custom event.
- `SessionGuard` (root layout) listens and redirects to `/login` after clearing
  auth state (this also covers sessions invalidated by a password reset).
- Idempotent: only one refresh in-flight at a time (`refreshPromise`).

## Verified

```
manage.py check       → no issues
pytest apps/accounts  → 36 tests (signup phone/google, signin, firebase,
                        google oauth, forgot/reset password + session
                        invalidation, admin sign-in, duplicates, strong
                        passwords, regressions) — all green
pytest                → 90 tests (full suite)
npm run typecheck     → 0 errors
npm run lint          → no issues in auth files
npm run build         → ✓
```

## Next phases

- **Phase 7** — Razorpay payments, webhooks, invoices.
- **Phase 8** — Wallet cashback, voucher minting, debt ledger.
- **Phase 9** — AI assistant & recommendations.
- **Phase 10** — Admin dashboard.
