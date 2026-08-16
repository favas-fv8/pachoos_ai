// Admin Order Detail — full view of a single order (customer, payment,
// items, timeline, delivery) plus status management.
import { useState, useEffect } from "react"
import { useParams } from "react-router-dom"
import { Loader2, MapPin, CreditCard, Package, RefreshCw } from "lucide-react"
import { BackButton } from "@/components/ui/back-button"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { api, toApiError } from "@/lib/api/client"
import { Loader, StatusBadge } from "./shared"
import { STATUS_OPTIONS } from "./constants"
import { formatINR } from "@/lib/utils"
import type { AdminOrderDetail, OrderStatus } from "@/types"

const PAYMENT_STATUS_COLORS: Record<string, "warning" | "success" | "danger"> = {
  pending: "warning",
  paid: "success",
  failed: "danger",
  refunded: "warning",
}

export default function AdminOrderDetailPage() {
  const { orderId } = useParams<{ orderId: string }>()
  const [order, setOrder] = useState<AdminOrderDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [updating, setUpdating] = useState(false)

  const load = async () => {
    if (!orderId) return
    setLoading(true)
    setError("")
    try {
      const res = await api.get(`/api/v1/admin-dashboard/orders/${orderId}/`)
      setOrder(res.data)
    } catch (err) {
      setError(toApiError(err).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderId])

  const handleStatusChange = async (newStatus: string) => {
    if (!order) return
    setUpdating(true)
    setError("")
    try {
      await api.post(`/api/v1/orders/${order.id}/update_status/`, { status: newStatus })
      setOrder((prev) => (prev ? { ...prev, status: newStatus as OrderStatus } : prev))
    } catch (err) {
      setError(toApiError(err).message)
    } finally {
      setUpdating(false)
    }
  }

  return (
    <div>
      <BackButton to="/admin/orders" />
      <div>
        <h1 className="font-display text-2xl font-bold">Order Detail</h1>
        <p className="text-sm text-ink-muted">{order?.order_number ?? "Loading…"}</p>
      </div>

      {error && (
        <div className="mt-4 flex items-center justify-between rounded-xl bg-danger-muted p-3 text-sm text-danger">
          <span>{error}</span>
          <Button variant="secondary" size="sm" onClick={() => void load()}>
            <RefreshCw className="h-4 w-4" /> Retry
          </Button>
        </div>
      )}

      {loading ? (
        <Loader />
      ) : !order ? (
        <div className="mt-4 rounded-2xl border border-border bg-surface p-8 text-center text-ink-muted">
          Order not found.
        </div>
      ) : (
        <div className="mt-6 space-y-6">
          {/* Customer + payment + status */}
          <div className="grid gap-6 lg:grid-cols-3">
            <section className="rounded-2xl border border-border bg-surface p-5 shadow-card">
              <h2 className="font-display text-base font-semibold mb-3">Customer</h2>
              <div className="space-y-1 text-sm">
                <p className="font-medium">{order.customer.full_name}</p>
                <p className="text-ink-muted">{order.customer.phone || "No phone"}</p>
                <p className="text-ink-muted">{order.customer.email || "No email"}</p>
              </div>
            </section>

            <section className="rounded-2xl border border-border bg-surface p-5 shadow-card">
              <h2 className="font-display text-base font-semibold mb-3 flex items-center gap-2">
                <CreditCard className="h-4 w-4 text-primary" /> Payment
              </h2>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-ink-muted">Status</span>
                  <Badge variant={PAYMENT_STATUS_COLORS[order.payment.status] ?? "warning"}>
                    {order.payment.status}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-muted">Method</span>
                  <span className="capitalize">
                    {order.payment.method ? order.payment.method.replace(/_/g, " ") : "—"}
                  </span>
                </div>
                {order.payment.is_demo && (
                  <div className="rounded-lg bg-ink-subtle px-2 py-1 text-center text-xs text-ink-muted">
                    Demo Payment
                  </div>
                )}
                {order.payment.transaction_id && (
                  <div className="flex justify-between">
                    <span className="text-ink-muted">Txn ID</span>
                    <span className="font-mono text-xs">{order.payment.transaction_id}</span>
                  </div>
                )}
              </div>
            </section>

            <section className="rounded-2xl border border-border bg-surface p-5 shadow-card">
              <h2 className="font-display text-base font-semibold mb-3">Status</h2>
              <div className="flex items-center gap-3">
                <StatusBadge status={order.status} />
                <select
                  value={order.status}
                  onChange={(e) => handleStatusChange(e.target.value)}
                  disabled={updating}
                  className="ml-auto rounded-lg border border-border bg-surface px-2 py-1 text-xs"
                >
                  {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                {updating && <Loader2 className="h-3 w-3 animate-spin text-primary" />}
              </div>
              {order.cancellation_reason && (
                <p className="mt-3 rounded-lg bg-danger-muted p-2 text-xs text-danger">
                  Reason: {order.cancellation_reason}
                </p>
              )}
            </section>
          </div>

          {/* Totals + delivery */}
          <div className="grid gap-6 lg:grid-cols-2">
            <section className="rounded-2xl border border-border bg-surface p-5 shadow-card">
              <h2 className="font-display text-base font-semibold mb-3">Totals</h2>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-ink-muted">Subtotal</span>
                  <span>{formatINR(Number(order.totals.subtotal))}</span>
                </div>
                {Number(order.totals.discount_total) > 0 && (
                  <div className="flex justify-between text-success">
                    <span>Discounts</span>
                    <span>-{formatINR(Number(order.totals.discount_total))}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-ink-muted">Delivery</span>
                  <span className={order.totals.delivery_free ? "text-success" : ""}>
                    {order.totals.delivery_free ? "FREE" : formatINR(Number(order.totals.delivery_charge))}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-muted">GST</span>
                  <span>{formatINR(Number(order.totals.tax_total))}</span>
                </div>
                <hr className="border-border" />
                <div className="flex justify-between font-semibold">
                  <span>Grand total</span>
                  <span>{formatINR(Number(order.totals.grand_total))}</span>
                </div>
              </div>
            </section>

            <section className="rounded-2xl border border-border bg-surface p-5 shadow-card">
              <h2 className="font-display text-base font-semibold mb-3 flex items-center gap-2">
                <MapPin className="h-4 w-4 text-primary" /> Delivery
              </h2>
              {order.delivery ? (
                <div className="space-y-2 text-sm">
                  <p className="text-ink-muted">{order.delivery.delivery_address}</p>
                  <div className="flex justify-between">
                    <span className="text-ink-muted">Distance</span>
                    <span>{order.delivery.distance_km} km</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-ink-muted">Charge</span>
                    <span>{formatINR(Number(order.delivery.charge))}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-ink-muted">Status</span>
                    <span className="capitalize">{order.delivery.status.replace(/_/g, " ")}</span>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-ink-muted">No delivery record.</p>
              )}
            </section>
          </div>

          {/* Items */}
          <section className="rounded-2xl border border-border bg-surface p-5 shadow-card">
            <h2 className="font-display text-base font-semibold mb-3 flex items-center gap-2">
              <Package className="h-4 w-4 text-primary" /> Items
            </h2>
            <div className="divide-y divide-border">
              {order.items.map((item) => (
                <div key={item.product_id} className="flex items-center justify-between gap-3 py-3 text-sm">
                  <div>
                    <p className="font-medium">{item.product_name}</p>
                    {item.variant_name && <p className="text-xs text-ink-muted">{item.variant_name}</p>}
                    <p className="text-xs text-ink-muted">
                      {item.quantity} × {formatINR(Number(item.unit_price))} • GST {item.tax_percent}%
                    </p>
                  </div>
                  <p className="font-semibold">{formatINR(Number(item.line_total))}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Timeline */}
          <section className="rounded-2xl border border-border bg-surface p-5 shadow-card">
            <h2 className="font-display text-base font-semibold mb-3">History</h2>
            <div className="space-y-3">
              {order.timeline.length === 0 && (
                <p className="text-sm text-ink-muted">No events recorded.</p>
              )}
              {[...order.timeline].reverse().map((t, i) => (
                <div key={i} className="flex gap-3 text-sm">
                  <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary/60" />
                  <div>
                    <p className="capitalize">{t.status.replace(/_/g, " ")}</p>
                    {t.note && <p className="text-xs text-ink-muted">{t.note}</p>}
                    <p className="text-xs text-ink-muted">
                      {new Date(t.created_at).toLocaleString()} • {t.actor_role}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  )
}