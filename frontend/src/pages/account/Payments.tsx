import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { CreditCard, Loader2, AlertTriangle, RotateCcw } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { BackButton } from '@/components/ui/back-button'
import { fetchListAll, toApiError } from '@/lib/api/client'

interface PaymentRecord {
  id: string
  order_number: string
  grand_total: string
  status: string
  created_at: string
}

const paymentStatus = (orderStatus: string) => {
  if (orderStatus === 'delivered' || orderStatus === 'refunded') return { label: 'Captured', tone: 'success' as const }
  if (orderStatus === 'cancelled') return { label: 'Refunded', tone: 'danger' as const }
  if (orderStatus === 'pending') return { label: 'Awaiting payment', tone: 'warning' as const }
  return { label: 'In progress', tone: 'secondary' as const }
}

export default function Payments() {
  const [records, setRecords] = useState<PaymentRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchListAll<PaymentRecord>('/api/v1/orders/')
      setRecords(data)
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

  if (error && records.length === 0) {
    return (
      <div>
        <BackButton to="/account" />
        <div className="rounded-2xl border border-danger/30 bg-danger-muted p-6 text-center">
          <AlertTriangle className="mx-auto mb-2 h-8 w-8 text-danger" />
          <p className="text-sm text-danger">{error}</p>
          <Button variant="secondary" size="sm" className="mt-3" onClick={() => void load()}>
            <RotateCcw className="h-4 w-4" /> Retry
          </Button>
        </div>
      </div>
    )
  }

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
      <BackButton to="/account" />

      {/* Payment history */}
      <div>
        <h3 className="font-display text-lg font-semibold mb-3">Payment History</h3>
        {records.length === 0 ? (
          <div className="rounded-2xl border border-border bg-surface p-10 text-center text-ink-muted">
            <CreditCard className="mx-auto mb-3 h-10 w-10 opacity-30" />
            <p>No payments yet.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {records.map((o) => {
              const ps = paymentStatus(o.status)
              return (
                <div key={o.id} className="flex items-center justify-between rounded-2xl border border-border bg-surface p-5 shadow-card">
                  <div>
                    <p className="font-semibold">{o.order_number}</p>
                    <p className="text-xs text-ink-muted">{new Date(o.created_at).toLocaleString()}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold">₹{o.grand_total}</p>
                    <Badge variant={ps.tone} className="mt-1">{ps.label}</Badge>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </motion.div>
  )
}
