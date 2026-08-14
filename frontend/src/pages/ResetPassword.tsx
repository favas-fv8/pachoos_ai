import { useState } from 'react'
import { motion } from 'framer-motion'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Loader2, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, toApiError } from '@/lib/api/client'
import { checkPassword, isStrongPassword } from '@/lib/password'

/**
 * Public "Reset Password" page — reached from the emailed reset link
 * (/reset-password?uid=...&token=...). Sets the new password directly.
 */
export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const uid = searchParams.get('uid') ?? ''
  const token = searchParams.get('token') ?? ''

  const [newPassword, setNewPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const checks = checkPassword(newPassword)
  const valid = isStrongPassword(newPassword) && newPassword === confirm

  if (!uid || !token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        <div className="max-w-md rounded-2xl border border-border bg-surface p-8 text-center shadow-card">
          <p className="text-sm text-ink-muted">
            This password reset link is invalid or expired. Please request a new one.
          </p>
          <Link to="/forgot-password" className="mt-4 inline-block text-sm font-medium text-primary hover:underline">
            Request a new link
          </Link>
        </div>
      </div>
    )
  }

  const handleSubmit = async () => {
    if (!valid) {
      setError('Enter a strong password and matching confirmation.')
      return
    }
    setLoading(true)
    setError('')
    try {
      await api.post('/api/v1/auth/password/reset/', {
        uid,
        token,
        new_password: newPassword,
      })
      setDone(true)
    } catch (err) {
      const apiErr = toApiError(err)
      if (apiErr.code === 'RESET_TOKEN_INVALID') {
        setError(apiErr.message)
      } else {
        setError(apiErr.message || 'Could not reset the password. Try again.')
      }
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
          <p className="mt-1 text-sm text-ink-muted">Choose a new password</p>
        </div>

        {done ? (
          <div className="flex items-start gap-3 rounded-xl bg-success-muted p-4 text-sm text-success">
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-medium">Password updated</p>
              <p className="mt-1 text-success/80">
                All existing sessions have been closed. Sign in with your new password.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {error && <div className="rounded-xl bg-danger-muted p-3 text-sm text-danger">{error}</div>}
            <div>
              <Input
                type="password"
                placeholder="New password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
              />
              {newPassword && (
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
              placeholder="Confirm new password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="new-password"
            />
            <Button onClick={handleSubmit} disabled={loading} className="w-full">
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Update password
            </Button>
          </div>
        )}

        <div className="mt-6 text-center">
          <Link
            to="/login"
            className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
          >
            <ArrowLeft className="h-4 w-4" /> Back to sign in
          </Link>
        </div>
      </motion.div>
    </div>
  )
}
