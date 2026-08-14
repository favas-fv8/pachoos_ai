import { useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, toApiError } from '@/lib/api/client'
import { useAppDispatch, useAppSelector } from '@/store/hooks'
import { setUser } from '@/store/slices/authSlice'
import { pushToast } from '@/store/slices/uiSlice'
import { checkPassword, isStrongPassword } from '@/lib/password'

/**
 * Shown once after a Google first-login: the account was auto-created and still
 * needs a password before the user enters the store. Guarded by RequirePasswordSetup.
 */
export default function CreatePassword() {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const user = useAppSelector((s) => s.auth.user)

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const checks = checkPassword(password)
  const valid = isStrongPassword(password) && password === confirm

  const handleSubmit = async () => {
    if (!valid) {
      setError('Enter a strong password and matching confirmation.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await api.post('/api/v1/auth/password/create/', { password })
      dispatch(setUser(res.data))
      dispatch(pushToast({ message: 'Password created successfully.', variant: 'success' }))
      navigate('/')
    } catch (err) {
      setError(toApiError(err).message || 'Could not create the password. Please try again.')
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
          <h1 className="font-display text-2xl font-bold">Create your password</h1>
          <p className="mt-1 text-sm text-ink-muted">
            {user?.email ? (
              <>
                Set a password for <span className="font-medium">{user.email}</span> to also sign in
                with email and password.
              </>
            ) : (
              'Set a password to complete your account setup.'
            )}
          </p>
        </div>

        {error && <div className="mb-4 rounded-xl bg-danger-muted p-3 text-sm text-danger">{error}</div>}

        <div className="space-y-4">
          <div>
            <Input
              type="password"
              placeholder="Create a password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
            />
            {password && (
              <ul className="mt-2 space-y-1">
                {checks.map((c) => (
                  <li
                    key={c.label}
                    className={`text-xs ${c.ok ? 'text-success' : 'text-ink-muted'}`}
                  >
                    {c.ok ? '✓' : '○'} {c.label}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <Input
            type="password"
            placeholder="Confirm password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="new-password"
          />
          <Button onClick={handleSubmit} disabled={loading} className="w-full">
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Create password & continue
          </Button>
        </div>
      </motion.div>
    </div>
  )
}
