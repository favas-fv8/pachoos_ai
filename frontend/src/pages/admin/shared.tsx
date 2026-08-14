import { Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { STATUS_COLORS } from './constants'

/** Order status → badge (typed, shared across admin pages). */
export function StatusBadge({ status }: { status: string }) {
  return <Badge variant={STATUS_COLORS[status] ?? 'default'}>{status}</Badge>
}

export function Loader() {
  return (
    <div className="flex justify-center py-12">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
    </div>
  )
}