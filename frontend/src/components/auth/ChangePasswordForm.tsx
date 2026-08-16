import { useState } from 'react'
import { Loader2, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, toApiError } from '@/lib/api/client'
import { useAppDispatch } from '@/store/hooks'
import { setCredentials } from '@/store/slices/authSlice'
import { pushToast } from '@/store/slices/uiSlice'
import { checkPassword, isStrongPassword } from '@/lib/password'

/**
 * Change the account password (current password required). The backend revokes
 * every other session and returns a fresh token pair for this device, so the
 * user stays signed in here while everyone else is signed out.
 */
export default function ChangePasswordForm() {
  const dispatch = useAppDispatch()

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const checks = checkPassword(newPassword)
  const valid = isStrongPassword(newPassword) && newPassword === confirm

  const handleSubmit = async () => {
    if (!currentPassword) {
      setError('Enter your current password.')
      return
    }
    if (!valid) {
      setError('Enter a strong new password and matching confirmation.')
      return
    }
    setLoading(true)
    setError('')
    setDone(false)
    try {
      const res = await api.post('/api/v1/auth/password/change/', {
        current_password: currentPassword,
        new_password: newPassword,
      })
      dispatch(
        setCredentials({ access: res.data.access, refresh: res.data.refresh, user: res.data.user }),
      )
      setCurrentPassword('')
      setNewPassword('')
      setConfirm('')
      setDone(true)
      dispatch(pushToast({ message: 'Password changed. Other sessions were signed out.', variant: 'success' }))
    } catch (err) {
      setError(toApiError(err).message || 'Could not change the password. Try again.')
    } finally {
      setLoading(false)
    }
  }

  if (done) {
    return (
      <div className="flex items-start gap-3 rounded-xl bg-success-muted p-4 text-sm text-success">
        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0" />
        <div>
          <p className="font-medium">Password changed</p>
          <p className="mt-1 text-success/80">All other devices have been signed out.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {error && <div className="rounded-xl bg-danger-muted p-3 text-sm text-danger">{error}</div>}
      <label className="block">
        <span className="mb-1 block text-xs text-ink-muted">Current password</span>
        <Input
          type="password"
          placeholder="Enter your current password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          autoComplete="current-password"
        />
      </label>
      <label className="block">
        <span className="mb-1 block text-xs text-ink-muted">New password</span>
        <Input
          type="password"
          placeholder="Set a strong new password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          autoComplete="new-password"
        />
        {newPassword && (
          <ul className="mt-2 space-y-1">
            {checks.map((c) => (
              <li key={c.label} className={`text-xs ${c.ok ? 'text-success' : 'text-ink-muted'}`}>
                {c.ok ? '✓' : '○'} {c.label}
              </li>
            ))}
          </ul>
        )}
      </label>
      <label className="block">
        <span className="mb-1 block text-xs text-ink-muted">Confirm new password</span>
        <Input
          type="password"
          placeholder="Re-enter the new password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          autoComplete="new-password"
        />
      </label>
      <Button onClick={handleSubmit} disabled={loading} className="w-full">
        {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
        Change password
      </Button>
    </div>
  )
}
