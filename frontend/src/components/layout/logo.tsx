import { Link } from 'react-router-dom'
import { Leaf } from 'lucide-react'

export function HeaderLogo() {
  return (
    <Link to="/" className="flex items-center gap-2" aria-label="PACHOOS home">
      <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary text-primary-foreground">
        <Leaf className="h-5 w-5" />
      </span>
      <span className="font-display text-xl font-semibold tracking-tight">
        PACHOOS
      </span>
    </Link>
  )
}