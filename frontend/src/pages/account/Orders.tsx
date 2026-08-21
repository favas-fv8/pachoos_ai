import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Package, Loader2, AlertTriangle, RotateCcw } from 'lucide-react'
import { BackButton } from '@/components/ui/back-button'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { fetchListAll, toApiError } from '@/lib/api/client'
import { formatINR } from '@/lib/utils'
import type { OrderListItem } from '@/types'

const statusColor = (s: string) => {
  const map: Record<string, 'warning' | 'success' | 'secondary' | 'danger'> = {
    pending: 'warning',
    accepted: 'success',
    preparing: 'secondary',
    packed: 'secondary',
    out_for_delivery: 'secondary',
    delivered: 'success',
    cancelled: 'danger',
  }
  return map[s] || 'secondary'
}

const paymentColor = (s: string) => {
  const map: Record<string, 'warning' | 'success' | 'danger'> = {
    pending: 'warning',
    paid: 'success',
    failed: 'danger',
    refunded: 'warning',
  }
  return map[s] || 'warning'
}

export default function Orders() {
  const [orders, setOrders] = useState<OrderListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchListAll<OrderListItem>('/api/v1/orders/')
      setOrders(data)
    } catch (err) {
      setError(toApiError(err).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  if (loading) {
    return (
      <div>
        <BackButton to="/account" />
        <div className="flex justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div>
        <BackButton to="/account" />
        <div className="rounded-2xl border border-danger/30 bg-danger-muted p-6 text-center">
          <AlertTriangle className="mx-auto mb-2 h-8 w-8 text-danger" />
          <p className="text-sm text-danger">{error}</p>
          <Button variant="secondary" size="sm" onClick={() => void load()}>
            <RotateCcw className="h-4 w-4" /> Retry
          </Button>
        </div>
      </div>
    )
  }

  if (orders.length === 0) {
    return (
      <div>
        <BackButton to="/account" />
        <div className="rounded-2xl border border-border bg-surface p-10 text-center text-ink-muted">
          <Package className="mx-auto mb-3 h-10 w-10 opacity-30" />
          <p>You haven't placed any orders yet.</p>
          <Link to="/shop" className="mt-3 inline-block font-medium text-primary">Start shopping</Link>
        </div>
      </div>
    )
  }

  return (
    <div>
      <BackButton to="/account" />
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
        {orders.map((o) => (
          <Link
            key={o.id}
            to={`/track/${o.id}`}
            className="flex items-center justify-between rounded-2xl border border-border bg-surface p-5 shadow-card transition-shadow hover:shadow-pop"
          >
            <div>
              <p className="font-semibold">{o.order_number}</p>
              <p className="text-xs text-ink-muted">
                {new Date(o.created_at).toLocaleString()} • {o.items_count ?? 0} item(s)
              </p>
            </div>
            <div className="text-right">
              <p className="font-semibold">{formatINR(Number(o.grand_total))}</p>
              <div className="mt-1 flex justify-end gap-1">
                <Badge variant={statusColor(o.status)}>
                  {o.status_display || o.status}
                </Badge>
                <Badge variant={paymentColor(o.payment_status)}>
                  {o.payment_status_display || o.payment_status}
                </Badge>
              </div>
              {o.payment_method && (
                <p className="mt-1 text-xs capitalize text-ink-muted">
                  {o.payment_method.replace(/_/g, ' ')}
                </p>
              )}
              <p className="mt-1 text-xs text-ink-muted">
                Cashback {formatINR(Number(o.cashback_earned ?? 0))}
              </p>
            </div>
          </Link>
        ))}
      </motion.div>
    </div>
  )
}