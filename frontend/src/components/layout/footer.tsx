import { Link } from 'react-router-dom'
import { Leaf } from 'lucide-react'

export function Footer() {
  return (
    <footer className="border-t border-border bg-surface-muted/50">
      <div className="container-px mx-auto flex flex-col gap-6 py-10 sm:flex-row sm:items-start sm:justify-between">
        <div className="max-w-xs">
          <Link to="/" className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-primary-foreground">
              <Leaf className="h-4 w-4" />
            </span>
            <span className="font-display text-lg font-semibold">PACHOOS</span>
          </Link>
          <p className="mt-3 text-sm text-ink-muted">
            Fresh bakery &amp; fruits, delivered to your door in minutes.
          </p>
        </div>

        <nav className="grid grid-cols-2 gap-x-12 gap-y-2 text-sm text-ink-muted" aria-label="Footer">
          <Link to="/shop" className="hover:text-ink">Shop</Link>
          <Link to="/track" className="hover:text-ink">Track order</Link>
          <Link to="/account/wallet" className="hover:text-ink">Wallet</Link>
          <Link to="/account/orders" className="hover:text-ink">My orders</Link>
        </nav>
      </div>
      <div className="border-t border-border py-4 text-center text-xs text-ink-muted">
        © {new Date().getFullYear()} PACHOOS Bakery &amp; Fruits. All rights reserved.
      </div>
    </footer>
  )
}