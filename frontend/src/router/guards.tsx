import { useEffect, type JSX } from 'react'
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAppDispatch, useAppSelector } from '@/store/hooks'
import { logout } from '@/store/slices/authSlice'
import { ADMIN_ROLES } from '@/router/roles'
import { signOutFirebase } from '@/lib/firebase'
import type { Role } from '@/types'

/**
 * Renders the router's child routes and reacts to `pachoos:unauthorized` —
 * emitted when the API client can no longer refresh a session (token revoked/
 * expired, e.g. after a password reset invalidated all devices). Clears auth
 * state, closes any lingering Firebase session, and returns to the sign-in page.
 */
export function SessionGuard(): JSX.Element {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()

  useEffect(() => {
    const onUnauthorized = () => {
      // Best-effort: a lingering Firebase session would otherwise reuse a stale
      // ID token on the next Google sign-in.
      void signOutFirebase()
      dispatch(logout())
      navigate('/login', { replace: true })
    }
    window.addEventListener('pachoos:unauthorized', onUnauthorized)
    return () => window.removeEventListener('pachoos:unauthorized', onUnauthorized)
  }, [dispatch, navigate])

  return <Outlet />
}

/** Redirect authenticated users away from public-only pages (e.g. /login). */
export function PublicOnly({ children }: { children: JSX.Element }) {
  const { isAuthenticated, user } = useAppSelector((s) => s.auth)
  if (isAuthenticated) {
    // Accounts that never completed password setup must finish it first.
    const redirectTo = user && !user.has_password ? '/create-password' : '/'
    return <Navigate to={redirectTo} replace />
  }
  return children
}

/** Require an authenticated account that still needs its first password set. */
export function RequirePasswordSetup({ children }: { children: JSX.Element }) {
  const { isAuthenticated, user } = useAppSelector((s) => s.auth)
  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (user?.has_password) return <Navigate to="/" replace />
  return children
}

/** Require authentication; redirect to /login otherwise (preserving intent). */
export function RequireAuth({ children }: { children: JSX.Element }) {
  const isAuthenticated = useAppSelector((s) => s.auth.isAuthenticated)
  const location = useLocation()
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return children
}

/** Require one of the given roles via Role-Based Access Control. */
export function RequireRole({
  roles = ADMIN_ROLES,
  children,
}: {
  roles?: Role[]
  children: JSX.Element
}) {
  const { isAuthenticated, user } = useAppSelector((s) => s.auth)
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  if (!user || !roles.includes(user.role as Role)) {
    return <Navigate to="/" replace />
  }
  return children
}

/** Require an admin role (super_admin or store_manager) for the /admin interface. */
export function RequireAdmin({ children }: { children: JSX.Element }) {
  return <RequireRole roles={ADMIN_ROLES}>{children}</RequireRole>
}
