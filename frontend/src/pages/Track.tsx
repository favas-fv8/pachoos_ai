import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import { useParams, Link } from "react-router-dom"
import {
  Package,
  Loader2,
  AlertTriangle,
  RefreshCw,
  CheckCircle2,
  MapPin,
  CreditCard,
  Clock,
} from "lucide-react"
import { Button, ButtonLink } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { BackButton } from "@/components/ui/back-button"
import { api, toApiError } from "@/lib/api/client"
import { formatINR } from "@/lib/utils"
import type { OrderDetail } from "@/types"

const ORDER_STEPS = [
  "pending",
  "accepted",
  "preparing",
  "packed",
  "out_for_delivery",
  "delivered",
] as const

const stepIndex = (status: string): number => {
  const idx = ORDER_STEPS.indexOf(status as (typeof ORDER_STEPS)[number])
  return idx >= 0 ? idx : -1
}

const paymentStatusBadge = (status: string) => {
  const map: Record<string, "warning" | "success" | "danger"> = {
    pending: "warning",
    paid: "success",
    failed: "danger",
    refunded: "warning",
  }
  return map[status] || "warning"
}

export default function Track() {
  const { orderId } = useParams<{ orderId?: string }>()
  const [order, setOrder] = useState<OrderDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    if (!orderId) return
    let cancelled = false
    setLoading(true)
    setError("")
    api
      .get(`/api/v1/orders/${orderId}/`)
      .then((res) => {
        if (!cancelled) setOrder(res.data)
      })
      .catch((err) => {
        if (!cancelled) setError(toApiError(err).message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [orderId])

  const currentStep = order ? stepIndex(order.status) : -1

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="container-px mx-auto py-8"
    >
      <BackButton to="/account/orders" />
      <h1 className="font-display text-3xl font-bold">Track Order</h1>

      {!orderId && (
        <div className="mt-6 rounded-2xl border border-border bg-surface p-6 shadow-card">
          <div className="flex items-center gap-3">
            <MapPin className="h-5 w-5 text-primary" />
            <p className="text-ink-muted">
              Select an order from <Link className="font-medium text-primary" to="/account/orders">My Orders</Link> to track it here.
            </p>
          </div>
        </div>
      )}

      {loading && (
        <div className="flex justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      )}

      {error && !loading && (
        <div className="mt-6 rounded-2xl border border-danger/30 bg-danger-muted p-6 text-center">
          <AlertTriangle className="mx-auto mb-2 h-8 w-8 text-danger" />
          <p className="text-sm text-danger">{error}</p>
          <Button variant="secondary" size="sm" className="mt-3" onClick={() => window.location.reload()}>
            <RefreshCw className="h-4 w-4" /> Retry
          </Button>
        </div>
      )}

      {order && !loading && (
        <>
          {/* Header */}
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-surface p-5 shadow-card">
            <div>
              <p className="text-sm text-ink-muted">Order</p>
              <p className="font-display text-xl font-bold">{order.order_number}</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-ink-muted">Total</p>
              <p className="font-display text-xl font-bold">{formatINR(Number(order.grand_total))}</p>
            </div>
          </div>

          {/* Status stepper */}
          <div className="mt-6 rounded-2xl border border-border bg-surface p-6 shadow-card">
            <h2 className="font-display text-lg font-semibold mb-4">Order status</h2>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              {ORDER_STEPS.map((step, i) => {
                const done = i <= currentStep
                const cancelled = order.status === "cancelled"
                return (
                  <div key={step} className="flex items-center gap-3 sm:flex-1 sm:flex-col sm:gap-2 sm:text-center">
                    <div
                      className={`grid h-9 w-9 shrink-0 place-items-center rounded-full border-2 ${
                        done && !cancelled
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-border bg-surface-muted text-ink-muted"
                      }`}
                    >
                      {done && !cancelled ? <CheckCircle2 className="h-5 w-5" /> : <Clock className="h-4 w-4" />}
                    </div>
                    <span
                      className={`text-sm capitalize ${done && !cancelled ? "font-medium text-ink" : "text-ink-muted"}`}
                    >
                      {step.replace(/_/g, " ")}
                    </span>
                  </div>
                )
              })}
            </div>
            {order.status === "cancelled" && (
              <p className="mt-4 rounded-xl bg-danger-muted p-3 text-sm text-danger">
                This order was cancelled. {order.cancellation_reason ? `Reason: ${order.cancellation_reason}` : ""}
              </p>
            )}
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            {/* Payment */}
            <section className="rounded-2xl border border-border bg-surface p-6 shadow-card">
              <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
                <CreditCard className="h-5 w-5 text-primary" /> Payment
              </h2>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-ink-muted">Status</span>
                  <Badge variant={paymentStatusBadge(order.payment_status)}>
                    {order.payment_status}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-muted">Method</span>
                  <span className="capitalize">{order.payment_method.replace(/_/g, " ")}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-muted">Cashback earned</span>
                  <span>{formatINR(Number(order.cashback_earned))}</span>
                </div>
              </div>
            </section>

            {/* Totals */}
            <section className="rounded-2xl border border-border bg-surface p-6 shadow-card">
              <h2 className="font-display text-lg font-semibold mb-4">Summary</h2>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-ink-muted">Subtotal</span>
                  <span>{formatINR(Number(order.subtotal))}</span>
                </div>
                {Number(order.discount_total) > 0 && (
                  <div className="flex justify-between text-success">
                    <span>Discounts</span>
                    <span>-{formatINR(Number(order.discount_total))}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-ink-muted">Delivery</span>
                  <span className={order.delivery_free ? "text-success" : ""}>
                    {order.delivery_free ? "FREE" : formatINR(Number(order.delivery_charge))}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-muted">GST</span>
                  <span>{formatINR(Number(order.tax_total))}</span>
                </div>
                <hr className="border-border" />
                <div className="flex justify-between font-semibold">
                  <span>Total</span>
                  <span>{formatINR(Number(order.grand_total))}</span>
                </div>
              </div>
            </section>
          </div>

          {/* Items */}
          <section className="mt-6 rounded-2xl border border-border bg-surface p-6 shadow-card">
            <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
              <Package className="h-5 w-5 text-primary" /> Items
            </h2>
            <div className="divide-y divide-border">
              {order.items.map((item) => (
                <div key={item.id} className="flex items-center justify-between gap-3 py-3">
                  <div>
                    <p className="font-medium">{item.product_name}</p>
                    {item.variant_name && (
                      <p className="text-xs text-ink-muted">{item.variant_name}</p>
                    )}
                    <p className="text-xs text-ink-muted">
                      {item.quantity} × {formatINR(Number(item.unit_price))}
                    </p>
                  </div>
                  <p className="font-semibold">{formatINR(Number(item.line_total))}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Timeline */}
          {order.timeline.length > 0 && (
            <section className="mt-6 rounded-2xl border border-border bg-surface p-6 shadow-card">
              <h2 className="font-display text-lg font-semibold mb-4">History</h2>
              <div className="space-y-3">
                {[...order.timeline].reverse().map((t) => (
                  <div key={t.id} className="flex gap-3 text-sm">
                    <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary/60" />
                    <div>
                      <p className="capitalize">
                        {t.status.replace(/_/g, " ")}
                        {t.note ? <span className="text-ink-muted"> — {t.note}</span> : ""}
                      </p>
                      <p className="text-xs text-ink-muted">{new Date(t.created_at).toLocaleString()}</p>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          <div className="mt-6 flex gap-3">
            <ButtonLink variant="outline" href="/account/orders">
              Back to orders
            </ButtonLink>
            <ButtonLink href="/shop">
              Shop again
            </ButtonLink>
          </div>
        </>
      )}
    </motion.div>
  )
}