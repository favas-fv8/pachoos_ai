// Admin Payments — view payment history across all shop orders.
import { useCallback, useEffect, useState } from "react"
import { CreditCard } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { BackButton } from "@/components/ui/back-button"
import { api } from "@/lib/api/client"
import { paymentStatusMeta } from "@/lib/payment-status"
import { Loader } from "./shared"

interface PaymentRecord {
  id: string
  order_number: string
  user_name: string
  grand_total: string
  status: string
  payment_status: string
  payment_method: string
  created_at: string
}

export default function AdminPayments() {
  const [records, setRecords] = useState<PaymentRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const res = await api.get("/api/v1/admin-dashboard/all-orders/")
      setRecords(res.data)
    } catch {
      setError("Failed to load payment history.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div>
      <BackButton to="/admin/dashboard" homeTo="/admin/dashboard" storeTo="/shop" />
      <div>
        <h1 className="font-display text-2xl font-bold">Payments</h1>
        <p className="text-sm text-ink-muted">View payment history for all customer orders.</p>
      </div>

      {error && (
        <div className="mt-4 rounded-xl bg-danger-muted p-3 text-sm text-danger">{error}</div>
      )}

      <div className="mt-6">
        <h3 className="font-display text-lg font-semibold mb-3">Payment History</h3>

        {loading ? <Loader /> : records.length === 0 ? (
          <div className="rounded-2xl border border-border bg-surface p-10 text-center text-ink-muted">
            <CreditCard className="mx-auto mb-3 h-10 w-10 opacity-30" />
            <p>No payments yet.</p>
          </div>
        ) : (
          <div className="rounded-2xl border border-border bg-surface overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-ink-subtle">
                <tr>
                  <th className="px-4 py-3 text-left font-medium">Order #</th>
                  <th className="px-4 py-3 text-left font-medium">Customer</th>
                  <th className="px-4 py-3 text-left font-medium">Amount</th>
                  <th className="px-4 py-3 text-left font-medium">Payment Method</th>
                  <th className="px-4 py-3 text-left font-medium">Status</th>
                  <th className="px-4 py-3 text-left font-medium">Date</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r) => {
                  const ps = paymentStatusMeta(r.payment_status, r.status)
                  return (
                    <tr key={r.id} className="border-t border-border">
                      <td className="px-4 py-3 font-medium">{r.order_number}</td>
                      <td className="px-4 py-3">{r.user_name}</td>
                      <td className="px-4 py-3 font-semibold">₹{r.grand_total}</td>
                      <td className="px-4 py-3 capitalize text-ink-muted">
                        {r.payment_method ? r.payment_method.replace(/_/g, " ") : "—"}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={ps.tone}>
                          {ps.label}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-ink-muted">
                        {new Date(r.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
