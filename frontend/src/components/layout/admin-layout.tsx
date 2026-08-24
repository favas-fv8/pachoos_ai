import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  Package,
  ShoppingCart,
  Users,
    Bell,
    MapPin,
    Menu,
  X,
  Leaf,
  Store,
  Home,
  ArrowLeft,
  LogOut,
  Sun,
  Moon,
  Settings,
  BookOpen,
  CreditCard,
} from 'lucide-react'
import { useAppDispatch, useAppSelector } from '@/store/hooks'
import { toggleTheme } from '@/store/slices/uiSlice'
import { logout } from '@/store/slices/authSlice'
import { signOutFirebase } from '@/lib/firebase'
import { useAdminNotifications } from '@/hooks/useAdminNotifications'
import { ChatWidget } from '@/components/chat/ChatWidget'
import { ShopLocationPicker } from '@/components/location/ShopLocationPicker'
import { Badge } from '@/components/ui/badge'
import { Toaster } from '@/components/ui/toaster'

type NavItem = {
  to: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  badge?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { to: '/admin/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/admin/products', label: 'Products', icon: Package },
  { to: '/admin/orders', label: 'Orders', icon: ShoppingCart },
  { to: '/admin/customers', label: 'Customers', icon: Users },
  { to: '/admin/debt-book', label: 'Debt Book', icon: BookOpen },
  { to: '/admin/payments', label: 'Payments', icon: CreditCard },
  { to: '/admin/notifications', label: 'Notifications', icon: Bell },
  { to: '/admin/settings', label: 'Settings', icon: Settings },
]

const roleLabel = (role?: string) => {
  if (role === 'super_admin') return 'Super Admin'
  if (role === 'store_manager') return 'Store Manager'
  return role
}

export function AdminLayout() {
  const user = useAppSelector((s) => s.auth.user)
  const theme = useAppSelector((s) => s.ui.theme)
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [shopLocationOpen, setShopLocationOpen] = useState(false)
  const { unreadCount, refresh: refreshNotifications } = useAdminNotifications()
  const location = useLocation()
  const isAccountArea = location.pathname.startsWith('/account')

  // When another admin performs an operation, this dashboard picks it up on the
  // next poll (see useAdminNotifications). Refetch on window focus for freshness.
  useEffect(() => {
    const onFocus = () => void refreshNotifications(true)
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [refreshNotifications])

  const handleLogout = async () => {
    // Sign out of any lingering Firebase session too, even though admin auth is
    // email+password only — keeps Google sign-in clean for the same browser.
    await signOutFirebase()
    dispatch(logout())
    navigate('/login', { replace: true })
  }

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center justify-between px-5">
        <Link to="/admin/dashboard" className="flex items-center gap-2" aria-label="Admin dashboard">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary text-primary-foreground">
            <Leaf className="h-5 w-5" />
          </span>
          <span className="font-display text-lg font-semibold tracking-tight">PACHOOS</span>
        </Link>
        <button
          onClick={() => setSidebarOpen(false)}
          className="rounded-lg p-2 text-ink-muted hover:bg-surface-muted lg:hidden"
          aria-label="Close menu"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <nav className="mt-4 flex flex-1 flex-col gap-1 px-3" aria-label="Admin">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-ink-muted hover:bg-surface-muted hover:text-ink'
              }`
            }
          >
            <item.icon className="h-4 w-4" />
            <span className="flex-1">{item.label}</span>
            {item.badge && unreadCount > 0 && (
              <span className="grid h-5 min-w-5 place-items-center rounded-full bg-primary px-1.5 text-xs font-semibold text-primary-foreground">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </NavLink>
        ))}
        <button
          type="button"
          onClick={() => {
            setShopLocationOpen(true)
            setSidebarOpen(false)
          }}
          className="mt-1 flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-ink-muted transition-colors hover:bg-surface-muted hover:text-ink"
        >
          <MapPin className="h-4 w-4" />
          <span className="flex-1 text-left">Shop Location</span>
        </button>
      </nav>

      <div className="space-y-1 border-t border-border p-3">
        <Link
          to="/"
          className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-ink-muted hover:bg-surface-muted hover:text-ink"
        >
          <Store className="h-4 w-4" />
          View store
        </Link>
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-ink-muted hover:bg-danger-muted hover:text-danger"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-background">
      {/* Mobile sidebar */}
      {sidebarOpen && !isAccountArea && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-ink/40 backdrop-blur-sm"
            onClick={() => setSidebarOpen(false)}
          />
          <aside className="absolute inset-y-0 left-0 w-72 bg-surface shadow-pop">{sidebar}</aside>
        </div>
      )}

      {/* Desktop sidebar */}
      {!isAccountArea && (
        <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 border-r border-border bg-surface lg:block">
          {sidebar}
        </aside>
      )}

      <div className={isAccountArea ? '' : 'lg:pl-64'}>
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border/70 bg-background/85 px-4 backdrop-blur-xl sm:px-6">
          {!isAccountArea && (
            <button
              onClick={() => setSidebarOpen(true)}
              className="rounded-lg p-2 text-ink-muted hover:bg-surface-muted lg:hidden"
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5" />
            </button>
          )}

          <div className="flex flex-1 items-center justify-between gap-3">
            <p className="font-display text-sm font-semibold sm:text-base">Admin Dashboard</p>
            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate(-1)}
                className="rounded-lg p-2 text-ink-muted hover:bg-surface-muted"
                aria-label="Back"
                title="Back"
              >
                <ArrowLeft className="h-5 w-5" />
              </button>
              <Link
                to="/admin/dashboard"
                className="rounded-lg p-2 text-ink-muted hover:bg-surface-muted"
                aria-label="Dashboard"
                title="Dashboard"
              >
                <LayoutDashboard className="h-5 w-5" />
              </Link>
              <Link
                to="/shop"
                className="rounded-lg p-2 text-ink-muted hover:bg-surface-muted"
                aria-label="Store"
                title="Store"
              >
                <Store className="h-5 w-5" />
              </Link>
              <Link
                to="/"
                className="rounded-lg p-2 text-ink-muted hover:bg-surface-muted"
                aria-label="Home"
                title="Home"
              >
                <Home className="h-5 w-5" />
              </Link>
              <button
                onClick={() => dispatch(toggleTheme())}
                className="rounded-lg p-2 text-ink-muted hover:bg-surface-muted"
                aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
              >
                {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </button>
              <div className="hidden text-right sm:block">
                <p className="text-sm font-medium leading-tight">{user?.full_name || user?.email || 'Admin'}</p>
                <Badge variant="secondary" className="mt-0.5">{roleLabel(user?.role)}</Badge>
              </div>
              <div className="grid h-9 w-9 place-items-center rounded-full bg-primary/10 font-semibold text-primary">
                {(user?.full_name || user?.email || 'A').charAt(0).toUpperCase()}
              </div>
            </div>
          </div>
        </header>

        <main className={isAccountArea ? 'flex-1' : 'mx-auto w-full max-w-6xl px-4 py-6 sm:px-6'}>
          <Outlet />
        </main>
      </div>
      <Toaster />
      <ShopLocationPicker open={shopLocationOpen} onClose={() => setShopLocationOpen(false)} />
      {/* Admin-audience AI assistant — separate endpoint/permissions from the
          customer assistant; admin data never mixes with customer scope. */}
      <ChatWidget audience="admin" />
    </div>
  )
}
