import { AnimatePresence, motion } from 'framer-motion'
import { NavLink } from 'react-router-dom'
import { X } from 'lucide-react'
import { useAppDispatch, useAppSelector } from '@/store/hooks'
import { setMobileNavOpen } from '@/store/slices/uiSlice'
import { isAdminRole } from '@/router/roles'

const links = [
  { to: '/', label: 'Home' },
  { to: '/shop', label: 'Shop' },
  { to: '/track', label: 'Track Order' },
  { to: '/account', label: 'Account' },
  { to: '/account/wallet', label: 'Wallet' },
  { to: '/account/orders', label: 'My Orders' },
  { to: '/account/debt-book', label: 'Debt Book' },
]

export function MobileNav() {
  const open = useAppSelector((s) => s.ui.mobileNavOpen)
  const user = useAppSelector((s) => s.auth.user)
  const dispatch = useAppDispatch()
  const close = () => dispatch(setMobileNavOpen(false))

  const navLinks = isAdminRole(user?.role)
    ? [...links, { to: '/admin', label: 'Admin Dashboard' }]
    : links

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[80] bg-ink/40 backdrop-blur-sm"
            onClick={close}
          />
          <motion.aside
            initial={{ x: -280 }}
            animate={{ x: 0 }}
            exit={{ x: -280 }}
            transition={{ type: 'tween', duration: 0.22, ease: 'easeOut' }}
            className="fixed inset-y-0 left-0 z-[90] flex w-[280px] flex-col bg-surface p-4 shadow-pop"
            aria-label="Mobile menu"
          >
            <div className="flex items-center justify-between">
              <span className="font-display text-lg font-semibold">Menu</span>
              <button
                onClick={close}
                aria-label="Close menu"
                className="rounded-lg p-2 text-ink-muted hover:bg-surface-muted"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <nav className="mt-4 flex flex-col gap-1">
              {navLinks.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  onClick={close}
                  className={({ isActive }) =>
                    `rounded-xl px-3 py-2.5 text-sm font-medium ${
                      isActive ? 'bg-primary/10 text-primary' : 'text-ink hover:bg-surface-muted'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}