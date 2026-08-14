import { useState } from 'react'
import { motion } from 'framer-motion'
import { Link, useNavigate } from 'react-router-dom'
import { Shield, Loader2, UserPlus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAppDispatch } from '@/store/hooks'
import { setCredentials, type AuthState } from '@/store/slices/authSlice'
import { pushToast } from '@/store/slices/uiSlice'
import { api, toApiError } from '@/lib/api/client'
import { signInWithGoogle } from '@/lib/firebase'

type PageMode = 'customer' | 'admin'
type CustomerFlow = 'signin' | 'signup'

function GoogleIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
    </svg>
  )
}

interface GoogleResponse {
  access?: string
  refresh?: string
  user?: AuthState['user']
  password_required?: boolean
  password_challenge?: boolean
  email?: string
}

export default function Login() {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()

  const [pageMode, setPageMode] = useState<PageMode>('customer')
  const [flow, setFlow] = useState<CustomerFlow>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [challengeEmail, setChallengeEmail] = useState('')

  const reset = () => {
    setError('')
    setPassword('')
    setEmail('')
    setChallengeEmail('')
  }

  const switchMode = (m: PageMode) => {
    setPageMode(m)
    reset()
  }

  const switchFlow = (f: CustomerFlow) => {
    setFlow(f)
    reset()
  }

  // -------------------------------------------------------------------------
  // Customer sign-in (email + password)
  // -------------------------------------------------------------------------
  const handleSignIn = async () => {
    const value = email.trim()
    if (!value || !password) {
      setError('Enter your email and password.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await api.post('/api/v1/auth/customer/login/', { email: value, password })
      dispatch(
        setCredentials({ access: res.data.access, refresh: res.data.refresh, user: res.data.user }),
      )
      setChallengeEmail('')
      dispatch(pushToast({ message: 'Signed in successfully.', variant: 'success' }))
      navigate('/')
    } catch (err) {
      setError(toApiError(err).message || 'Login failed. Check your credentials.')
    } finally {
      setLoading(false)
    }
  }

  // -------------------------------------------------------------------------
  // Continue with Google (Firebase popup) — primary customer auth.
  // Handles both Sign In (existing account) and Sign Up (new account).
  // -------------------------------------------------------------------------
  const completeGoogle = async (): Promise<GoogleResponse> => {
    const { idToken } = await signInWithGoogle()
    return (await api.post<GoogleResponse>('/api/v1/auth/google/', { token: idToken })).data
  }

  const handleGoogleContinue = async () => {
    setLoading(true)
    setError('')
    try {
      let data: GoogleResponse
      try {
        data = await completeGoogle()
      } catch (err) {
        const apiErr = toApiError(err)
        // Backend had a transient failure fetching Google's verification keys.
        // Wait briefly and retry with a freshly fetched ID token.
        if (apiErr.code === 'AUTH_SERVICE_UNAVAILABLE') {
          await new Promise((r) => setTimeout(r, 1200))
          data = await completeGoogle()
        } else {
          throw err
        }
      }

      // Existing account with a password → require it before issuing a session.
      if (data.password_challenge && data.email) {
        switchFlow('signin')
        setEmail(data.email)
        setChallengeEmail(data.email)
        setError('')
        return
      }

      if (!data.access || !data.refresh || !data.user) {
        throw new Error('Incomplete response')
      }
      dispatch(
        setCredentials({
          access: data.access,
          refresh: data.refresh,
          user: data.user,
        }),
      )
      if (data.password_required) {
        // New account (no password yet) → set a password before entering the store.
        navigate('/create-password')
        return
      }
      dispatch(pushToast({ message: 'Signed in successfully.', variant: 'success' }))
      navigate('/')
    } catch (err) {
      setError(toApiError(err).message || 'Google sign-in failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  // -------------------------------------------------------------------------
  // Admin sign-in — Sign In only. No admin self-registration exists.
  // -------------------------------------------------------------------------
  const handleAdminSignIn = async () => {
    const value = email.trim()
    if (!value || !password) {
      setError('Enter your email and password.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await api.post('/api/v1/auth/admin/login/', { email: value, password })
      dispatch(
        setCredentials({ access: res.data.access, refresh: res.data.refresh, user: res.data.user }),
      )
      dispatch(pushToast({ message: 'Signed in successfully.', variant: 'success' }))
      navigate('/admin/dashboard')
    } catch (err) {
      setError(toApiError(err).message || 'Login failed. Check your credentials.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="w-full max-w-md rounded-2xl border border-border bg-surface p-8 shadow-card"
      >
        <div className="mb-6 text-center">
          <h1 className="font-display text-2xl font-bold">PACHOOS</h1>
          <p className="mt-1 text-sm text-ink-muted">
            {pageMode === 'admin' ? 'Shop owner sign in' : flow === 'signup' ? 'Create your account' : 'Customer sign in'}
          </p>
        </div>

        {error && <div className="mb-4 rounded-xl bg-danger-muted p-3 text-sm text-danger">{error}</div>}

        {/* Customer / Admin */}
        <div className="mb-4 flex gap-2">
          <Button
            variant={pageMode === 'customer' ? 'default' : 'outline'}
            size="sm"
            className="flex-1"
            onClick={() => switchMode('customer')}
          >
            Customer
          </Button>
          <Button
            variant={pageMode === 'admin' ? 'default' : 'outline'}
            size="sm"
            className="flex-1"
            onClick={() => switchMode('admin')}
          >
            <Shield className="mr-1 h-3 w-3" /> Admin
          </Button>
        </div>

        {pageMode === 'admin' ? (
          <div className="space-y-4">
            <Input
              type="email"
              placeholder="Email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Input
              type="password"
              placeholder="Password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Button onClick={handleAdminSignIn} disabled={loading} className="w-full">
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Sign in
            </Button>
            <div className="text-center">
              <Link to="/forgot-password" className="text-xs font-medium text-primary hover:underline">
                Forgot password?
              </Link>
            </div>
            <p className="pt-2 text-center text-xs text-ink-muted">Admin sign-in is for staff accounts only.</p>
          </div>
        ) : flow === 'signup' ? (
          // ── Customer Sign Up ──────────────────────────────────────────────
          <div className="space-y-4">
            <Button variant="outline" className="w-full" onClick={handleGoogleContinue} disabled={loading}>
              <GoogleIcon /> Continue with Google
            </Button>
            <div className="rounded-xl bg-primary-muted p-3 text-center text-xs text-primary">
              Sign up with your Google account. After verifying you, we&apos;ll ask you to set a
              password to finish creating your PACHOOS account.
            </div>
            <div className="pt-1 text-center text-sm text-ink-muted">
              Already have an account?{' '}
              <button
                type="button"
                onClick={() => switchFlow('signin')}
                className="font-medium text-primary hover:underline"
              >
                Sign in
              </button>
            </div>
          </div>
        ) : (
          // ── Customer Sign In (default mode) ────────────────────────────────
          <div className="space-y-4">
            <Button variant="outline" className="w-full" onClick={handleGoogleContinue} disabled={loading}>
              <GoogleIcon /> Continue with Google
            </Button>
            <div className="flex items-center gap-3">
              <div className="flex-1 border-t border-border" />
              <span className="text-xs text-ink-muted">or sign in with email</span>
              <div className="flex-1 border-t border-border" />
            </div>
            {challengeEmail && (
              <div className="rounded-xl bg-primary-muted p-3 text-sm text-primary">
                Google verified <span className="font-medium">{challengeEmail}</span>. Enter
                your password to finish signing in.
              </div>
            )}
            <Input
              type="email"
              placeholder="you@example.com"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Input
              type="password"
              placeholder="Password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Button onClick={handleSignIn} disabled={loading} className="w-full">
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Sign in
            </Button>
            <div className="text-center">
              <Link to="/forgot-password" className="text-xs font-medium text-primary hover:underline">
                Forgot password?
              </Link>
            </div>
            <div className="border-t border-border pt-3 text-center text-sm text-ink-muted">
              New to PACHOOS?{' '}
              <button
                type="button"
                onClick={() => switchFlow('signup')}
                className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
              >
                <UserPlus className="h-3.5 w-3.5" /> Create an account
              </button>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  )
}
