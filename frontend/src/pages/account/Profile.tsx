import { motion } from 'framer-motion'
import { BackButton } from '@/components/ui/back-button'
import { useAppSelector } from '@/store/hooks'
import { Badge } from '@/components/ui/badge'

const roleLabel = (role?: string) => {
  if (role === 'super_admin') return 'Super Admin'
  if (role === 'store_manager') return 'Store Manager'
  return 'Customer'
}

export default function Profile() {
  const user = useAppSelector((s) => s.auth.user)

  return (
    <div>
      <BackButton to="/account" />
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <div className="rounded-2xl border border-border bg-surface p-6 shadow-card">
          <div className="flex items-center gap-4">
            <div className="grid h-14 w-14 place-items-center rounded-full bg-primary/10 text-xl font-bold text-primary">
              {(user?.full_name || user?.email || 'U').charAt(0).toUpperCase()}
            </div>
            <div>
              <h2 className="text-lg font-semibold">{user?.full_name || 'Account'}</h2>
              <Badge variant="secondary" className="mt-1">{roleLabel(user?.role)}</Badge>
            </div>
          </div>

          <dl className="mt-6 grid gap-4 sm:grid-cols-2">
            {[
              { label: 'Full name', value: user?.full_name || '—' },
              { label: 'Phone', value: user?.phone || '—' },
              { label: 'Email', value: user?.email || '—' },
              { label: 'Referral code', value: user?.referral_code || '—' },
            ].map((f) => (
              <div key={f.label}>
                <dt className="text-sm text-ink-muted">{f.label}</dt>
                <dd className="mt-0.5 font-medium">{f.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </motion.div>
    </div>
  )
}