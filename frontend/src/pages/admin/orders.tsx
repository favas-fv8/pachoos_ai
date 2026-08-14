// Admin Orders — list, search, filter and update order status.
import { useState, useEffect, useCallback } from "react"
import { Search, Loader2 } from "lucide-react"
import { Input } from "@/components/ui/input"
import { BackButton } from "@/components/ui/back-button"
import { api, toApiError } from "@/lib/api/client"
import { Loader, StatusBadge } from "./shared"
import { STATUS_OPTIONS } from "./constants"

interface Order {
  id: string
  order_number: string
  user_name: string
  user_phone: string
  status: string
  subtotal: string
  grand_total: string
  created_at: string
  cancellation_reason: string
}

export default function AdminOrders() {
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [updatingId, setUpdatingId] = useState<string | null>(null)

  const fetchOrders = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const params = statusFilter ? `?status=${statusFilter}` : ""
      const res = await api.get(`/api/v1/admin-dashboard/all-orders/${params}`)
      setOrders(res.data)
    } catch {
      setError("Failed to load orders.")
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

  useEffect(() => {
    fetchOrders()
  }, [fetchOrders])

  const filtered = orders.filter((o) =>
    o.order_number?.toLowerCase().includes(search.toLowerCase()) ||
    o.user_name?.toLowerCase().includes(search.toLowerCase()) ||
    o.user_phone?.toLowerCase().includes(search.toLowerCase())
  )

  const handleStatusChange = async (orderId: string, newStatus: string) => {
    setUpdatingId(orderId)
    try {
      await api.post(`/api/v1/orders/${orderId}/update_status/`, { status: newStatus })
      setOrders((prev) => prev.map((o) => o.id === orderId ? { ...o, status: newStatus } : o))
    } catch (err) {
      setError(toApiError(err).message)
    } finally {
      setUpdatingId(null)
    }
  }

  return (
    <div>
      <BackButton to="/admin/dashboard" homeTo="/admin/dashboard" storeTo="/shop" />
      <div>
        <h1 className="font-display text-2xl font-bold">Orders</h1>
        <p className="text-sm text-ink-muted">Review and manage all customer orders.</p>
      </div>

      {error && (
        <div className="mt-4 rounded-xl bg-danger-muted p-3 text-sm text-danger">{error}</div>
      )}

      <div className="mt-4 mb-4 flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" />
          <Input placeholder="Search by order #, customer or phone..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10" />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-xl border border-border bg-surface px-4 py-2 text-sm"
        >
          <option value="">All Status</option>
          {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {loading ? <Loader /> : (
        <div className="rounded-2xl border border-border bg-surface overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-ink-subtle">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Order #</th>
                <th className="px-4 py-3 text-left font-medium">Customer</th>
                <th className="px-4 py-3 text-left font-medium">Total</th>
                <th className="px-4 py-3 text-left font-medium">Date</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
                <th className="px-4 py-3 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((o) => (
                <tr key={o.id} className="border-t border-border">
                  <td className="px-4 py-3 font-medium">{o.order_number}</td>
                  <td className="px-4 py-3">
                    <p>{o.user_name}</p>
                    <p className="text-xs text-ink-muted">{o.user_phone}</p>
                  </td>
                  <td className="px-4 py-3 font-semibold">₹{o.grand_total}</td>
                  <td className="px-4 py-3 text-ink-muted">{new Date(o.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={o.status} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className="inline-flex items-center gap-1">
                      <select
                        value={o.status}
                        onChange={(e) => handleStatusChange(o.id, e.target.value)}
                        disabled={updatingId === o.id}
                        className="rounded-lg border border-border bg-surface px-2 py-1 text-xs"
                      >
                        {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                      {updatingId === o.id && <Loader2 className="h-3 w-3 animate-spin text-primary" />}
                    </span>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-ink-muted">No orders found.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}