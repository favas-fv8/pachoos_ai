// Admin Customers — customer list, details (with the complete linked Debt Book),
// safe profile editing and soft deletion (financial history is never touched).
import { useState, useEffect } from "react"
import { Search, UserCog, Pencil, Trash2, X, Loader2, BookOpen } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { BackButton } from "@/components/ui/back-button"
import { api, toApiError } from "@/lib/api/client"
import { Loader, StatusBadge } from "./shared"

interface Customer {
  id: number
  full_name: string
  phone: string
  email: string
  order_count: number
  total_spent: string
  date_joined: string
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
  note: string
  updated_by_name: string
  created_at: string
}

interface DebtBookProfile {
  id: string
  display_name: string
  is_offline: boolean
  summary: { outstanding: string; total_added: string; total_paid: string }
  entries: DebtEntry[]
  notes: { id: string; body: string; sender_name: string; sender_role: string; created_at: string }[]
}

interface CustomerDetail extends Customer {
  role: string
  is_active: boolean
  last_login: string | null
  total_debt: string
  debt_book_id: string | null
  debt_book: DebtBookProfile | null
  orders: { id: string; order_number: string; status: string; grand_total: string; created_at: string }[]
}

const rupee = (value: string | number) =>
  Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })

const num = (value?: string | number | null) => {
  const n = Number(String(value ?? 0))
  return Number.isFinite(n) ? n : 0
}

const ONLY_DIGITS = /^\d*$/
const EMAIL_OK = /^[\w.+-]+@[\w-]+\.[\w.]+$/

const fieldError = (err: unknown): string => {
  const data = (err as { response?: { data?: unknown } })?.response?.data
  if (data && typeof data === "object") {
    const d = data as Record<string, unknown>
    for (const value of Object.values(d)) {
      if (Array.isArray(value) && value.length > 0) return String(value[0])
    }
    const nested = d.error
    if (typeof nested === "string" && nested) return nested
    if (nested && typeof nested === "object") {
      const msg = (nested as Record<string, unknown>).message
      if (typeof msg === "string") return msg
    }
  }
  return toApiError(err).message
}

export default function AdminCustomers() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [search, setSearch] = useState("")
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<CustomerDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // edit / delete
  const [editing, setEditing] = useState(false)
  const [editForm, setEditForm] = useState({ full_name: "", phone: "", email: "" })
  const [editError, setEditError] = useState("")
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [posting, setPosting] = useState(false)

  const loadCustomers = () =>
    api.get("/api/v1/admin-dashboard/customers/")
      .then((res) => setCustomers(res.data))
      .catch(() => setError("Failed to load customers."))

  useEffect(() => {
    loadCustomers().finally(() => setLoading(false))
  }, [])

  const filtered = customers.filter((c) =>
    c.full_name?.toLowerCase().includes(search.toLowerCase()) ||
    c.phone?.includes(search) ||
    c.email?.toLowerCase().includes(search.toLowerCase())
  )

  const loadDetail = async (id: number) => {
    setSelectedId(id)
    setDetailLoading(true)
    setError("")
    setEditing(false)
    setConfirmingDelete(false)
    try {
      const res = await api.get(`/api/v1/admin-dashboard/customers/${id}/`)
      setDetail(res.data)
    } catch (err) {
      setError(fieldError(err))
    } finally {
      setDetailLoading(false)
    }
  }

  const backToList = () => {
    setSelectedId(null)
    setDetail(null)
    setEditing(false)
    setConfirmingDelete(false)
  }

  const openEdit = () => {
    if (!detail) return
    setEditForm({ full_name: detail.full_name, phone: detail.phone, email: detail.email })
    setEditError("")
    setEditing(true)
    setConfirmingDelete(false)
  }

  const validateEdit = (): string => {
    const phone = editForm.phone.replace(/\s+/g, "")
    if (phone && !ONLY_DIGITS.test(phone)) return "Phone must contain digits only."
    if (phone && phone.length !== 10) return "Phone must be exactly 10 digits."
    if (editForm.email.trim() && !EMAIL_OK.test(editForm.email.trim())) return "Enter a valid email address (e.g. name@gmail.com)."
    if (!editForm.full_name.trim()) return "Full name is required."
    return ""
  }

  const handleSaveEdit = async () => {
    if (!detail) return
    const formErr = validateEdit()
    if (formErr) {
      setEditError(formErr)
      return
    }
    setPosting(true)
    setEditError("")
    try {
      const res = await api.patch(`/api/v1/admin-dashboard/customers/${detail.id}/`, {
        full_name: editForm.full_name.trim(),
        phone: editForm.phone.replace(/\s+/g, ""),
        email: editForm.email.trim(),
      })
      setDetail(res.data)
      setEditing(false)
      void loadCustomers()
    } catch (err) {
      setEditError(fieldError(err))
    } finally {
      setPosting(false)
    }
  }

  const handleDelete = async () => {
    if (!detail) return
    setPosting(true)
    setError("")
    try {
      await api.delete(`/api/v1/admin-dashboard/customers/${detail.id}/`)
      setConfirmingDelete(false)
      setSelectedId(null)
      setDetail(null)
      void loadCustomers()
    } catch (err) {
      setError(fieldError(err))
      setConfirmingDelete(false)
    } finally {
      setPosting(false)
    }
  }

  const hasDebt = !!detail?.debt_book && num(detail.debt_book.summary.outstanding) > 0

  const entryLines = (e: DebtEntry) => {
    if (e.entry_type !== "bill") return null
    if (e.items && e.items.length > 0) {
      return (
        <div className="mt-2 space-y-1">
          {e.items.map((item) => (
            <div key={item.id} className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-ink-muted">
              <span className="font-medium text-ink">{item.product_name || "Item"}</span>
              <span>{item.quantity}{item.unit} × ₹{rupee(item.unit_price)}</span>
              {num(item.discount) > 0 && <span>−₹{rupee(item.discount)}</span>}
              <span className="ml-auto font-semibold text-ink">₹{rupee(item.line_total)}</span>
            </div>
          ))}
          <div className="flex flex-wrap gap-x-4 gap-y-0.5 pt-1 text-xs text-ink-muted border-t border-border">
            <span>Subtotal: ₹{rupee(e.subtotal)}</span>
            <span>Discount: −₹{rupee(e.discount_total)}</span>
            <span className="font-medium text-ink">Total: ₹{rupee(e.line_total)}</span>
          </div>
        </div>
      )
    }
    return (
      <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-ink-muted sm:grid-cols-4">
        <span>Qty: {e.quantity}</span>
        <span>Price: ₹{rupee(e.unit_price)}</span>
        <span>Discount: −₹{rupee(e.discount)}</span>
        <span>Total: ₹{rupee(e.line_total)}</span>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <BackButton to="/admin/dashboard" onClick={() => (selectedId ? backToList() : undefined)} label={selectedId ? "Back to list" : "Back"} homeTo="/admin/dashboard" storeTo="/shop" />
      </div>
      <div>
        <h1 className="font-display text-2xl font-bold">Customers</h1>
        <p className="text-sm text-ink-muted">Edit customer details, view order history and the complete linked Debt Book. Delete safely deactivates the account without touching financial history.</p>
      </div>

      {error && (
        <div className="mt-4 rounded-xl bg-danger-muted p-3 text-sm text-danger">{error}</div>
      )}

      <div className="mt-4 mb-4 flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" />
          <Input placeholder="Search by name, phone or email..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10" />
        </div>
      </div>

      {loading ? <Loader /> : (
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Customer list */}
          <div className="lg:col-span-1 rounded-2xl border border-border bg-surface overflow-hidden max-h-[70vh] overflow-y-auto">
            {filtered.map((c) => (
              <button
                key={c.id}
                onClick={() => loadDetail(c.id)}
                className={`w-full px-4 py-3 text-left border-b border-border hover:bg-ink-subtle transition-colors ${
                  selectedId === c.id ? "bg-primary/10 border-l-2 border-l-primary" : ""
                }`}
              >
                <p className="font-medium text-sm">{c.full_name || c.phone || "Unknown"}</p>
                <p className="text-xs text-ink-muted">{c.phone} • {c.order_count} orders</p>
                <p className="text-xs font-semibold text-success">₹{c.total_spent}</p>
              </button>
            ))}
            {filtered.length === 0 && <p className="p-4 text-sm text-ink-muted text-center">No customers found.</p>}
          </div>

          {/* Customer detail */}
          <div className="lg:col-span-2">
            {detailLoading ? <Loader /> : !detail ? (
              <div className="rounded-2xl border border-border bg-surface p-8 text-center text-ink-muted">
                <UserCog className="mx-auto mb-2 h-8 w-8 opacity-30" />
                <p>Select a customer to view details</p>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Info card */}
                <div className="rounded-2xl border border-border bg-surface p-6">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="flex items-center gap-2 font-semibold text-lg">
                        {detail.full_name || "Customer"}
                        {!detail.is_active && <Badge variant="secondary">Deleted</Badge>}
                      </h3>
                    </div>
                    <div className="flex gap-2">
                      <Button variant="secondary" size="sm" onClick={openEdit}>
                        <Pencil className="h-4 w-4" /> Edit
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => { setConfirmingDelete((v) => !v); setEditing(false) }}
                      >
                        <Trash2 className="h-4 w-4" /> Delete
                      </Button>
                    </div>
                  </div>

                  {/* Edit form */}
                  {editing && (
                    <div className="mt-4 rounded-xl border border-border bg-ink-subtle p-4">
                      <BackButton label="Back to Customer" onClick={() => setEditing(false)} homeTo="/admin/dashboard" storeTo="/shop" />
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-semibold text-sm">Edit customer profile</h4>
                        <button type="button" onClick={() => setEditing(false)} className="rounded-full p-1 hover:bg-ink-muted/20" aria-label="Close edit">
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                      <div className="flex flex-col gap-2 sm:flex-row">
                        <Input placeholder="Full name" value={editForm.full_name} onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })} />
                        <Input
                          placeholder="Phone (10 digits)"
                          inputMode="numeric"
                          value={editForm.phone}
                          onChange={(e) => setEditForm({ ...editForm, phone: e.target.value.replace(/[^\d\s]/g, "") })}
                        />
                        <Input placeholder="Email (e.g. name@gmail.com)" type="email" value={editForm.email} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} />
                        <Button size="sm" onClick={handleSaveEdit} disabled={posting}>
                          {posting && <Loader2 className="h-4 w-4 animate-spin" />} Save
                        </Button>
                      </div>
                      {editError && <p className="mt-2 text-xs text-danger">{editError}</p>}
                    </div>
                  )}

                  {/* Delete confirmation */}
                  {confirmingDelete && (
                    <div className="mt-4 rounded-xl border border-danger/40 bg-danger-muted p-4">
                      <BackButton label="Back" onClick={() => setConfirmingDelete(false)} homeTo="/admin/dashboard" storeTo="/shop" />
                      <h4 className="font-semibold text-sm text-danger">Delete this customer?</h4>
                      <p className="text-xs text-ink-muted mt-1">
                        The account is deactivated and removed from the list. Order, wallet and debt history is preserved and never deleted.
                      </p>
                      <div className="mt-3 flex gap-2">
                        <Button size="sm" variant="danger" onClick={handleDelete} disabled={posting}>
                          {posting && <Loader2 className="h-4 w-4 animate-spin" />} Yes, delete
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => setConfirmingDelete(false)}>Cancel</Button>
                      </div>
                    </div>
                  )}

                  <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-ink-muted">Phone</p>
                      <p className="font-medium">{detail.phone || "—"}</p>
                    </div>
                    <div>
                      <p className="text-ink-muted">Email</p>
                      <p className="font-medium">{detail.email || "—"}</p>
                    </div>
                    <div>
                      <p className="text-ink-muted">Total Orders</p>
                      <p className="font-medium">{detail.order_count}</p>
                    </div>
                    <div>
                      <p className="text-ink-muted">Total Spent</p>
                      <p className="font-medium text-success">₹{detail.total_spent}</p>
                    </div>
                    <div>
                      <p className="text-ink-muted">Outstanding Debt</p>
                      {hasDebt && detail.debt_book ? (
                        <a href={`/admin/debt-book?book=${detail.debt_book.id}`} className="font-medium text-danger underline decoration-dashed underline-offset-2 hover:text-danger/80">
                          ₹{rupee(detail.debt_book.summary.outstanding)}
                        </a>
                      ) : (
                        <p className="font-medium text-ink-muted">₹{detail.total_debt}</p>
                      )}
                    </div>
                    <div>
                      <p className="text-ink-muted">Joined</p>
                      <p className="font-medium">{new Date(detail.date_joined).toLocaleDateString()}</p>
                    </div>
                  </div>
                </div>

                {/* Complete linked Debt Book */}
                {detail.debt_book && (
                  <div className="rounded-2xl border border-border bg-surface p-6">
                    <h4 className="font-semibold mb-1 flex items-center justify-between flex-wrap gap-2">
                      <span className="flex items-center gap-2">
                        <BookOpen className="h-4 w-4 text-primary" /> Debt Book
                        {detail.debt_book.is_offline && <Badge variant="warning">Offline</Badge>}
                      </span>
                      <a href={`/admin/debt-book?book=${detail.debt_book.id}`} className="text-sm font-medium text-primary hover:underline">
                        Open in Debt Book →
                      </a>
                    </h4>
                    <p className="text-sm text-ink-muted mb-3">
                      Complete linked balance, bills, payments and history. Read-only here — manage in the Debt Book.
                    </p>
                    <div className="grid gap-3 sm:grid-cols-3">
                      <div className="rounded-xl bg-ink-subtle px-4 py-3">
                        <p className="text-xs text-ink-muted">Overall Outstanding</p>
                        <p className="text-xl font-bold text-danger">₹{rupee(detail.debt_book.summary.outstanding)}</p>
                      </div>
                      <div className="rounded-xl bg-ink-subtle px-4 py-3">
                        <p className="text-xs text-ink-muted">Total Debt Added</p>
                        <p className="text-xl font-bold text-ink">₹{rupee(detail.debt_book.summary.total_added)}</p>
                      </div>
                      <div className="rounded-xl bg-ink-subtle px-4 py-3">
                        <p className="text-xs text-ink-muted">Total Paid</p>
                        <p className="text-xl font-bold text-success">₹{rupee(detail.debt_book.summary.total_paid)}</p>
                      </div>
                    </div>
                    <div className="mt-4 space-y-2">
                      {detail.debt_book.entries.length === 0 && (
                        <p className="text-sm text-ink-muted">No transactions yet.</p>
                      )}
                      {detail.debt_book.entries.map((d) => (
                        <div key={d.id} className="rounded-xl bg-ink-subtle px-4 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <div className="min-w-0">
                              <p className="text-sm font-medium truncate">
                                {d.entry_type === "bill" && (d.product_name || "Bill")}
                                {d.entry_type === "payment" && "Payment received"}
                                {d.entry_type === "adjustment" && "Adjustment"}
                              </p>
                              <p className="text-xs text-ink-muted">
                                <Badge variant={d.entry_type === "payment" ? "success" : "default"} className="mr-1">{d.entry_label}</Badge>
                                {new Date(d.created_at).toLocaleString()} • by {d.updated_by_name || "Admin"}
                              </p>
                            </div>
                            <div className="text-right shrink-0">
                              {d.entry_type === "payment" ? (
                                <span className="text-sm font-semibold text-success">−₹{rupee(d.amount_paid)}</span>
                              ) : (
                                <span className="text-sm font-semibold text-danger">+₹{rupee(d.amount_added || d.delta)}</span>
                              )}
                            </div>
                          </div>
                          {entryLines(d)}
                          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
                            <span>Previous: ₹{rupee(d.prev_balance)}</span>
                            {d.entry_type === "bill" && num(d.amount_paid) > 0 && <span>Paid at counter: ₹{rupee(d.amount_paid)}</span>}
                            <span className="font-medium text-ink">Remaining: ₹{rupee(d.remaining)}</span>
                          </div>
                          {d.note && <p className="mt-1 text-xs italic text-ink-muted">“{d.note}”</p>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Order history */}
                {detail.orders.length > 0 && (
                  <div className="rounded-2xl border border-border bg-surface p-6">
                    <h4 className="font-semibold mb-3">Order History</h4>
                    <div className="space-y-2">
                      {detail.orders.map((o) => (
                        <div key={o.id} className="flex items-center justify-between rounded-xl bg-ink-subtle px-4 py-3">
                          <div>
                            <p className="text-sm font-medium">{o.order_number}</p>
                            <p className="text-xs text-ink-muted">{new Date(o.created_at).toLocaleDateString()}</p>
                          </div>
                          <div className="text-right">
                            <StatusBadge status={o.status} />
                            <p className="text-sm font-semibold">₹{o.grand_total}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}