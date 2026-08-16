import { motion } from 'framer-motion'
import { User, Wallet, Package, CreditCard, Settings } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAppSelector } from '@/store/hooks'
import { isAdminRole } from '@/router/roles'
import { BackButton } from '@/components/ui/back-button'

const sections = [
  { icon: User, label: 'Profile', to: '/account/profile' },
  { icon: Package, label: 'Orders', to: '/account/orders' },
  { icon: Wallet, label: 'Wallet', to: '/account/wallet' },
  { icon: CreditCard, label: 'Payment history', to: '/account/payments' },
  { icon: Settings, label: 'Settings', to: '/account/settings' },
]

const ADMIN_HIDDEN_SECTIONS = new Set<string>(['/account/orders', '/account/wallet', '/account/payments'])

export default function Account() {
  const user = useAppSelector((s) => s.auth.user)
  const isAdmin = isAdminRole(user?.role)
  const visibleSections = isAdmin ? sections.filter((s) => !ADMIN_HIDDEN_SECTIONS.has(s.to)) : sections

  return (
    <div className="container-px mx-auto py-8">
      <BackButton to="/shop" className="mb-4" />
      <h1 className="font-display text-3xl font-bold">Account</h1>
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {visibleSections.map((s) => (
          <motion.div
            key={s.label}
            whileHover={{ y: -3 }}
            transition={{ duration: 0.18 }}
          >
            <Link
              to={s.to}
              className="flex items-center gap-3 rounded-2xl border border-border bg-surface p-5 shadow-card hover:shadow-pop"
            >
              <div className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary">
                <s.icon className="h-5 w-5" />
              </div>
              <span className="font-medium">{s.label}</span>
            </Link>
          </motion.div>
        ))}
      </div>
    </div>
  )
}