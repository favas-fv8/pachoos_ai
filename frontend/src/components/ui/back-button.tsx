import { ArrowLeft, LayoutDashboard, Store } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { Button, buttonVariants } from '@/components/ui/button'

interface BackButtonProps {
  /** Destination used whenever the browser has no in-app history to go back to. */
  to?: string
  /** Direct handler (e.g. clear the selected row on a master-detail page). */
  onClick?: () => void
  label?: string
  className?: string
  /** Optional link to the admin dashboard (home). */
  homeTo?: string
  /** Optional link to the store landing page. */
  storeTo?: string
}

/**
 * A "Back" button for any section/page. Pops the previous logical screen
 * (React Router `navigate(-1)`), and falls back to an explicit `to` route when
 * the user landed directly on the page — so navigation never dead-ends or loops.
 * Optional `homeTo` / `storeTo` render Home (Dashboard) and Store (Landing) links.
 */
export function BackButton({ to, onClick, label = 'Back', className, homeTo, storeTo }: BackButtonProps) {
  const navigate = useNavigate()

  const handle = () => {
    if (onClick) {
      onClick()
      return
    }
    const canGoBack = (window.history.state?.idx ?? 0) > 0
    if (canGoBack) {
      navigate(-1)
    } else if (to) {
      navigate(to)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-1">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={handle}
        className={cn('-ml-2 text-ink-muted hover:text-ink', className)}
      >
        <ArrowLeft className="h-4 w-4" /> {label}
      </Button>
      {homeTo && (
        <Link
          to={homeTo}
          className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'text-ink-muted hover:text-ink')}
        >
          <LayoutDashboard className="h-4 w-4" /> Dashboard
        </Link>
      )}
      {storeTo && (
        <Link
          to={storeTo}
          className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'text-ink-muted hover:text-ink')}
        >
          <Store className="h-4 w-4" /> Store
        </Link>
      )}
    </div>
  )
}
