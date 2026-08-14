// Customer Debt Book — read-only view of the customer's own debt: outstanding,
// bills/statement, history and notes/chat replies.
import { useEffect, useState } from "react"
import { BackButton } from "@/components/ui/back-button"
import { BookOpen, Coins, TrendingUp, MessageSquare, Send } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { api, toApiError } from "@/lib/api/client"
import { Spinner } from "@/components/ui/spinner"

export function useDebtBookBackButton() {
  // Back button handled by parent layout
}

interface DebtBillItem {
  id: string
  product: string | null
  product_name: string
  quantity: string
  unit: "kg" | "count"
  unit_price: string
  discount: string
  line_total: string
}

interface DebtEntry {
  id: string
  entry_type: "bill" | "payment" | "adjustment"
  entry_label: string
  product_name: string
  quantity: number
  unit_price: string
  discount: string
  line_total: string
  subtotal: string
  discount_total: string
  items: DebtBillItem[]
  prev_balance: string
  delta: string
  amount_added: string
  amount_paid: string
  balance_after: string
  remaining: string
  bill_remaining: string
  reason: string
  note: string
  updated_by_name: string
  created_at: string
}

interface DebtNote {
  id: string
  body: string
  sender_name: string
  sender_role: string
  created_at: string
}

interface DebtBookResponse {
  id: string | null
  display_name: string
  summary: { outstanding: string; total_added: string; total_paid: string }
  entries: DebtEntry[]
  notes: DebtNote[]
}

const rupee = (value: string | number) =>
  Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })

const num = (value?: string | number | null) => {
  const n = Number(String(value ?? 0))
  return Number.isFinite(n) ? n : 0
}

const overviewCards = (data: DebtBookResponse | null) => {
  if (!data || !data.id) return []
  return [
    { label: "Overall Outstanding", value: `Rs ${rupee(data.summary.outstanding)}`, icon: Coins, tone: "text-danger" },
    { label: "Total Previous Debt", value: `Rs ${rupee(data.summary.total_added)}`, icon: TrendingUp, tone: "text-ink" },
    { label: "Total Amount Paid", value: `Rs ${rupee(data.summary.total_paid)}`, icon: BookOpen, tone: "text-success" },
  ]
}

// Render individual bill line items
const billLines = (e: DebtEntry) => {
  if (e.entry_type !== "bill") return null
  if (e.items && e.items.length > 0) {
    return (
      <div className="mt-2 space-y-1">
        {e.items.map((item) => (
          <div key={item.id} className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-ink-muted">
            <span className="font-medium text-ink">{item.product_name || "Item"}</span>
            <span>{item.quantity}{item.unit} × Rs {rupee(item.unit_price)}</span>
            {num(item.discount) > 0 && <span>−{rupee(item.discount)}</span>}
            <span className="ml-auto font-semibold text-ink">Rs {rupee(item.line_total)}</span>
          </div>
        ))}
        <div className="flex flex-wrap gap-x-4 gap-y-0.5 pt-1 text-xs text-ink-muted border-t border-border">
          <span>Subtotal: Rs {rupee(e.subtotal)}</span>
          <span>Discount: −{rupee(e.discount_total)}</span>
          <span className="font-medium text-ink">Total: Rs {rupee(e.line_total)}</span>
        </div>
      </div>
    )
  }
  return (
    <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-ink-muted sm:grid-cols-4">
      <span>Qty: {e.quantity}</span>
      <span>Price: Rs {rupee(e.unit_price)}</span>
      <span>Discount: -{rupee(e.discount)}</span>
      <span>Total: Rs {rupee(e.line_total)}</span>
    </div>
  )
}

export default function DebtBook() {
  const [data, setData] = useState<DebtBookResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [noteBody, setNoteBody] = useState("")
  const [posting, setPosting] = useState(false)

  const fetchBook = async () => {
    setLoading(true)
    setError("")
    try {
      const res = await api.get("/api/v1/wallet/my/debt/")
      setData(res.data)
    } catch (err) {
      setError(toApiError(err).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchBook()
  }, [])

  const handleReply = async () => {
    if (!noteBody.trim()) return
    setPosting(true)
    setError("")
    try {
      await api.post("/api/v1/wallet/my/debt/notes/", { body: noteBody })
      setNoteBody("")
      fetchBook()
    } catch (err) {
      setError(toApiError(err).message)
    } finally {
      setPosting(false)
    }
  }

  return (
    <div>
      <BackButton to="/account" />
      <h2 className="font-display text-xl font-bold mb-1">Debt Book</h2>
      <p className="text-sm text-ink-muted mb-5">
        Your outstanding balance, bills and payment history. Amounts are read-only — contact the shop for any correction.
      </p>

      {error && <div className="mb-4 rounded-xl bg-danger-muted p-3 text-sm text-danger">{error}</div>}

      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner size={28} />
        </div>
      ) : !data || !data.id ? (
        <div className="rounded-2xl border border-border bg-surface p-10 text-center text-ink-muted">
          <BookOpen className="mx-auto mb-2 h-10 w-10 opacity-30" />
          <p className="font-medium text-ink">You have no debt records.</p>
          <p className="text-sm">If you believe this is a mistake, please contact the shop.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Overview */}
          <div className="grid gap-3 sm:grid-cols-3">
            {overviewCards(data).map((c) => (
              <div key={c.label} className="rounded-2xl border border-border bg-surface px-5 py-4">
                <div className="flex items-center gap-2 text-xs text-ink-muted">
                  <c.icon className="h-4 w-4" /> {c.label}
                </div>
                <p className={`mt-1 text-xl font-bold ${c.tone}`}>{c.value}</p>
              </div>
            ))}
          </div>

          {/* Statement */}
          <div className="rounded-2xl border border-border bg-surface p-6">
            <h3 className="font-semibold mb-3">Bills & Statement</h3>
            {data.entries.length === 0 ? (
              <p className="text-sm text-ink-muted">No transactions yet.</p>
            ) : (
              <div className="space-y-2">
                {data.entries.map((e) => (
                  <div key={e.id} className="rounded-xl bg-ink-subtle px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">
                          {e.entry_type === "bill" && (e.product_name || "Bill")}
                          {e.entry_type === "payment" && "Payment recorded"}
                          {e.entry_type === "adjustment" && (e.reason || "Adjustment")}
                        </p>
                        <p className="text-xs text-ink-muted">
                          <Badge variant={e.entry_type === "payment" ? "success" : "default"} className="mr-1">
                            {e.entry_label}
                          </Badge>
                          {new Date(e.created_at).toLocaleString()}
                        </p>
                      </div>
                      <div className="text-right shrink-0">
                        {e.entry_type === "payment" ? (
                          <span className="text-sm font-semibold text-success">-{rupee(e.amount_paid)}</span>
                        ) : (
                          <span className="text-sm font-semibold text-danger">+{rupee(e.amount_added || e.delta)}</span>
                        )}
                      </div>
                    </div>
                    {billLines(e)}
                    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
                      {e.entry_type !== "bill" && <span>Previous: Rs {rupee(e.prev_balance)}</span>}
                      {e.entry_type === "bill" && num(e.amount_paid) > 0 && <span>Paid at counter: Rs {rupee(e.amount_paid)}</span>}
                      <span className="font-medium text-ink">Remaining: Rs {rupee(e.remaining)}</span>
                    </div>
                    {e.note && <p className="mt-1 text-xs italic text-ink-muted">"${e.note}"</p>}
                  </div>
                ))}
              </div>
            )}
            </div>

            {/* History */}
            <div className="rounded-2xl border border-border bg-surface p-6">
              <h3 className="font-semibold mb-1">History</h3>
              <p className="text-xs text-ink-muted mb-3">
                Previous debt, payments and remaining balance after every change.
              </p>
              <div className="space-y-1.5">
                {data.entries.map((e) => (
                  <div key={`hist-${e.id}`} className="flex items-center justify-between gap-3 text-sm">
                    <div className="min-w-0">
                      <p className="truncate text-ink">
                        {e.entry_label}
                        {e.product_name ? ` — ${e.product_name}` : ""}
                      </p>
                      <p className="text-xs text-ink-muted">
                        {new Date(e.created_at).toLocaleString()}
                        {e.updated_by_name ? ` • ${e.updated_by_name}` : ""}
                      </p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-xs text-ink-muted">
                        Previous Rs {rupee(e.prev_balance)} → Remaining{" "}
                        <span className="font-medium text-ink">Rs {rupee(e.remaining)}</span>
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Notes / Chat */}
            <div className="rounded-2xl border border-border bg-surface p-6">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <MessageSquare className="h-4 w-4" /> Notes / Chat
              </h3>
              {data.notes.length === 0 ? (
                <p className="text-sm text-ink-muted">No messages yet.</p>
              ) : (
                <div className="space-y-2">
                  {data.notes.map((n) => {
                    const isAdmin = n.sender_role !== "customer"
                    return (
                      <div
                        key={n.id}
                        className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                          isAdmin ? "bg-primary/10 text-ink" : "bg-ink-subtle text-ink"
                        }`}
                      >
                        <p>{n.body}</p>
                        <p className="mt-1 text-xs text-ink-muted">
                          <Badge variant={isAdmin ? "default" : "secondary"} className="mr-1">
                            {isAdmin ? "Shop" : "You"}
                          </Badge>
                          {n.sender_name} • {new Date(n.created_at).toLocaleString()}
                        </p>
                      </div>
                    )
                  })}
                </div>
              )}
              <div className="mt-3 flex gap-2">
                <Input
                  placeholder="Reply to the shop about your debt…"
                  value={noteBody}
                  onChange={(e) => setNoteBody(e.target.value)}
                />
                <Button onClick={handleReply} disabled={posting || !noteBody.trim()}>
                  <Send className="h-4 w-4" /> Send
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
  )
}