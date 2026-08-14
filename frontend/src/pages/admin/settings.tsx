import { useState } from 'react'
import { motion } from 'framer-motion'
import { KeyRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { BackButton } from '@/components/ui/back-button'
import ChangePasswordForm from '@/components/auth/ChangePasswordForm'
import { useAppSelector } from '@/store/hooks'

const roleLabel = (role?: string) => {
  if (role === 'super_admin') return 'Super Admin'
  if (role === 'store_manager') return 'Store Manager'
  return role
}

/** Admin Settings — profile info + change password (current password required). */
export default function AdminSettings() {
  const user = useAppSelector((s) => s.auth.user)
  const [passwordOpen, setPasswordOpen] = useState(false)

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <BackButton to="/admin/dashboard" homeTo="/admin/dashboard" storeTo="/shop" />
      <div className="rounded-2xl border border-border bg-surface p-6 shadow-card">
        <div className="flex items-center gap-4">
          <div className="grid h-14 w-14 place-items-center rounded-full bg-primary/10 text-xl font-bold text-primary">
            {(user?.full_name || user?.email || 'A').charAt(0).toUpperCase()}
          </div>
          <div>
            <h2 className="text-lg font-semibold">{user?.full_name || 'Admin'}</h2>
            <Badge variant="secondary" className="mt-1">{roleLabel(user?.role)}</Badge>
          </div>
        </div>
        <dl className="mt-6 grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-sm text-ink-muted">Email</dt>
            <dd className="mt-0.5 font-medium">{user?.email || '—'}</dd>
          </div>
          <div>
            <dt className="text-sm text-ink-muted">Phone</dt>
            <dd className="mt-0.5 font-medium">{user?.phone || '—'}</dd>
          </div>
        </dl>
      </div>

      <div className="rounded-2xl border border-border bg-surface p-6 shadow-card">
        <div className="flex items-center justify-between">
          <div>
            <p className="font-semibold">Change password</p>
            <p className="text-sm text-ink-muted">
              Enter your current password, then set a new one. All other devices will be signed out.
            </p>
          </div>
          <Button variant="outline" onClick={() => setPasswordOpen((o) => !o)}>
            <KeyRound className="h-4 w-4" />
            {passwordOpen ? 'Close' : 'Change'}
          </Button>
        </div>
        {passwordOpen && (
          <div className="mt-4 border-t border-border pt-4">
            <BackButton label="Back to Settings" onClick={() => setPasswordOpen(false)} homeTo="/admin/dashboard" storeTo="/shop" />
            <ChangePasswordForm />
          </div>
        )}
      </div>
    </motion.div>
  )
}
