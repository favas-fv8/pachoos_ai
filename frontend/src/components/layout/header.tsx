import { NavLink } from 'react-router-dom'
import { MapPin, Search, ShoppingBag, Sun, Moon, Menu, User, Shield } from 'lucide-react'
import { HeaderLogo } from './logo'
import { Button, ButtonLink } from '@/components/ui/button'
import { LocationPicker } from '@/components/location/LocationPicker'
import { useAppDispatch, useAppSelector } from '@/store/hooks'
import { setMobileNavOpen, toggleTheme } from '@/store/slices/uiSlice'
import { isAdminRole } from '@/router/roles'
import { useState } from 'react'

const nav = [
  { to: '/', label: 'Home' },
  { to: '/shop', label: 'Shop' },
  { to: '/track', label: 'Track Order' },
]

export function Header() {
  const theme = useAppSelector((s) => s.ui.theme)
  const user = useAppSelector((s) => s.auth.user)
  const deliveryAddress = useAppSelector((s) => s.ui.deliveryAddress)
  const mobileNavOpen = useAppSelector((s) => s.ui.mobileNavOpen)
  const dispatch = useAppDispatch()
  const [locationOpen, setLocationOpen] = useState(false)
  const toggle = () => dispatch(setMobileNavOpen(!mobileNavOpen))
  const visibleNav = isAdminRole(user?.role) ? nav.filter((n) => n.to !== '/track') : nav

  return (
    <header className="sticky top-0 z-50 border-b border-border/70 bg-background/85 backdrop-blur-xl">
      <div className="container-px mx-auto flex h-16 items-center gap-3">
        <div className="flex flex-1 items-center gap-5">
          <button
            onClick={toggle}
            className="rounded-lg p-2 text-ink-muted hover:bg-surface-muted md:hidden"
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>
          <HeaderLogo />
          <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
            {visibleNav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                    isActive ? 'bg-surface-muted text-ink' : 'text-ink-muted hover:text-ink'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-1.5">
          <ButtonLink href="/shop" variant="outline" size="icon" aria-label="Search">
            <Search className="h-4 w-4" />
          </ButtonLink>
          {isAdminRole(user?.role) && (
            <ButtonLink href="/admin" variant="outline" size="icon" aria-label="Admin dashboard">
              <Shield className="h-4 w-4" />
            </ButtonLink>
          )}
          <Button
            variant="outline"
            size="icon"
            aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            onClick={() => dispatch(toggleTheme())}
          >
            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
          <ButtonLink href="/account" variant="ghost" size="icon" aria-label="Account">
            <User className="h-4 w-4" />
          </ButtonLink>
          <ButtonLink href="/cart" variant="default" size="icon" aria-label="Cart">
            <ShoppingBag className="h-4 w-4" />
          </ButtonLink>
        </div>
      </div>

      {/* Location strip (admins use the Admin shell instead) */}
      {!isAdminRole(user?.role) && (
        <button
          onClick={() => setLocationOpen(true)}
          className="container-px mx-auto flex w-full items-center gap-1.5 pb-3 text-left text-xs font-medium text-ink-muted hover:text-ink"
        >
          <MapPin className="h-3.5 w-3.5 shrink-0 text-primary" />
          Deliver to{' '}
          <span className="truncate text-ink">
            {deliveryAddress ? deliveryAddress.label : '— set your address for delivery'}
          </span>
        </button>
      )}
      <LocationPicker open={locationOpen} onClose={() => setLocationOpen(false)} />
    </header>
  )
}