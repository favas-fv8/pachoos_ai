import { NavLink, Outlet } from 'react-router-dom'
import { User, Wallet, Package, CreditCard, Settings, MapPinned, BookOpen } from 'lucide-react'
import { useAppSelector } from '@/store/hooks'
import { isAdminRole } from '@/router/roles'

const ACCOUNT_LINKS = [
  { to: '/account/profile', label: 'Profile', icon: User },
  { to: '/account/orders', label: 'Orders', icon: Package },
  { to: '/account/debt-book', label: 'Debt Book', icon: BookOpen },
  { to: '/account/wallet', label: 'Wallet', icon: Wallet },
  { to: '/account/payments', label: 'Payments', icon: CreditCard },
  { to: '/account/settings', label: 'Settings', icon: Settings },
]

const ADMIN_HIDDEN_ACCOUNT_LINKS = new Set<string>([
  '/account/orders',
  '/account/debt-book',
  '/account/wallet',
  '/account/payments',
])

export function AccountLayout() {
  const user = useAppSelector((s) => s.auth.user)
  const isAdmin = isAdminRole(user?.role)
  const visibleLinks = isAdmin
    ? ACCOUNT_LINKS.filter((l) => !ADMIN_HIDDEN_ACCOUNT_LINKS.has(l.to))
    : ACCOUNT_LINKS

  return (
    <div className="container-px mx-auto py-8">
      <h1 className="font-display text-3xl font-bold">My Account</h1>
      <div className="mt-6 grid gap-6 lg:grid-cols-[220px_1fr]">
        <nav className="flex gap-2 overflow-x-auto lg:flex-col lg:overflow-visible" aria-label="Account">
          {visibleLinks.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              className={({ isActive }) =>
                `flex shrink-0 items-center gap-3 rounded-xl px-4 py-2.5 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-ink-muted hover:bg-surface-muted hover:text-ink'
                }`
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
          {!isAdmin && (
            <NavLink
              to="/track"
              className="flex shrink-0 items-center gap-3 rounded-xl px-4 py-2.5 text-sm font-medium text-ink-muted transition-colors hover:bg-surface-muted hover:text-ink"
            >
              <MapPinned className="h-4 w-4" />
              Track Order
            </NavLink>
          )}
        </nav>

        <div className="min-w-0">
          <Outlet />
        </div>
      </div>
    </div>
  )
}