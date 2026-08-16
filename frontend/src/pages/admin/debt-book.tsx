// Admin Debt Book — full debt management: registered + offline customers.
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useSearchParams } from "react-router-dom"
import {
  Search,
  BookOpen,
  UserPlus,
  Plus,
  IndianRupee,
  Wallet,
  TrendingUp,
  MessageSquare,
  Link2,
  Loader2,
  Receipt,
  BadgeCheck,
  Trash2,
  Pencil,
  X,
  ShoppingCart,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { BackButton } from "@/components/ui/back-button"
import { api, toApiError } from "@/lib/api/client"
import { Loader } from "./shared"

interface DebtBookRow {
  id: string
  user_id: number | null
  is_offline: boolean
  name: string
  phone: string
  email: string
  display_name: string
  outstanding: string
  entry_count: number
  created_at: string
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

interface DebtBookDetail {
  id: string
  user_id: number | null
  is_offline: boolean
  name: string
  phone: string
  email: string
  display_name: string
  summary: { outstanding: string; total_added: string; total_paid: string }
  entries: DebtEntry[]
  notes: DebtNote[]
  created_at: string
}

interface CustomerOption {
  id: number
  full_name: string
  phone: string
}

interface ProductOption {
  id: string
  name: string
  selling_price: string
  stock_unit: string
}

interface BillLine {
  product_id: string | null
  product_name: string
  quantity: string
  unit: "kg" | "count"
  unit_price: string
  discount: string
}

const rupee = (value: string | number) =>
  Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })

const num = (value?: string | number | null) => {
  const n = Number(String(value ?? 0))
  return Number.isFinite(n) ? n : 0
}

const ONLY_DIGITS = /^\d*$/
const EMAIL_OK = /^[\w.+-]+@[\w-]+\.[\w.]+$/

/** Extract the first human-readable backend field/message error. */
const fieldError = (err: unknown): string => {
  const data = (err as { response?: { data?: unknown } })?.response?.data
  if (data && typeof data === "object") {
    const d = data as Record<string, unknown>
    for (const value of Object.values(d)) {
      if (Array.isArray(value) && value.length > 0) return String(value[0])
    }
    const nested = d.error as Record<string, unknown> | string | undefined
    if (typeof nested === "string" && nested) return nested
    if (nested && typeof nested === "object") {
      const msg = (nested as Record<string, unknown>).message
      if (typeof msg === "string") return msg
    }
  }
  return toApiError(err).message
}

export default function AdminDebtBook() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [books, setBooks] = useState<DebtBookRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [search, setSearch] = useState("")
  const [selected, setSelected] = useState<DebtBookDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // form states
  const [showNewBook, setShowNewBook] = useState(false)
  const [newName, setNewName] = useState("")
  const [newPhone, setNewPhone] = useState("")
  const [newEmail, setNewEmail] = useState("")
  const [newFormError, setNewFormError] = useState("")
  const [showBill, setShowBill] = useState(false)
  const [showPayment, setShowPayment] = useState(false)
  const [showAdjust, setShowAdjust] = useState(false)
  const [payment, setPayment] = useState({ amount: "", note: "" })
  const [adjust, setAdjust] = useState({ amount: "", reason: "", note: "" })
  const [noteBody, setNoteBody] = useState("")
  const [posting, setPosting] = useState(false)

  // edit / delete offline customer
  const [editing, setEditing] = useState(false)
  const [editForm, setEditForm] = useState({ name: "", phone: "", email: "" })
  const [editError, setEditError] = useState("")
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  // multi-product bill builder
  const [billLines, setBillLines] = useState<BillLine[]>([
    { product_id: null, product_name: "", quantity: "1", unit: "count", unit_price: "", discount: "0" },
  ])
  const [billNote, setBillNote] = useState("")
  const [amountPaid, setAmountPaid] = useState("")

  // catalog product picker (search-as-you-type)
  const [productQuery, setProductQuery] = useState("")
  const [productResults, setProductResults] = useState<ProductOption[]>([])
  const [pickingLine, setPickingLine] = useState<number | null>(null)
  const pickerRef = useRef<HTMLDivElement>(null)

  // offline → registered linking
  const [customers, setCustomers] = useState<CustomerOption[]>([])
  const [linkUserId, setLinkUserId] = useState("")
  const [showLink, setShowLink] = useState(false)

  const loadBooks = useCallback(async (q = "") => {
    setLoading(true)
    setError("")
    try {
      const res = await api.get(`/api/v1/wallet/debt/books/${q ? `?q=${encodeURIComponent(q)}` : ""}`)
      setBooks(res.data)
    } catch (err) {
      setError(fieldError(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadBooks()
  }, [loadBooks])

  // Debounce the server-side search query.
  useEffect(() => {
    const t = setTimeout(() => loadBooks(search), 300)
    return () => clearTimeout(t)
  }, [search, loadBooks])

  // Debounce the catalog product search.
  useEffect(() => {
    if (pickingLine === null) return
    if (!productQuery.trim()) {
      setProductResults([])
      return
    }
    const t = setTimeout(async () => {
      try {
        const res = await api.get(
          `/api/v1/catalog/admin/products/?q=${encodeURIComponent(productQuery)}&page_size=20`,
        )
        setProductResults(res.data.results ?? [])
      } catch {
        setProductResults([])
      }
    }, 250)
    return () => clearTimeout(t)
  }, [productQuery, pickingLine])

  // Close the dropdown when clicking elsewhere.
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setPickingLine(null)
      }
    }
    document.addEventListener("mousedown", onClick)
    return () => document.removeEventListener("mousedown", onClick)
  }, [])

  const loadDetail = useCallback(async (id: string) => {
    setDetailLoading(true)
    setError("")
    try {
      const res = await api.get(`/api/v1/wallet/debt/books/${id}/`)
      setSelected(res.data)
    } catch (err) {
      setError(fieldError(err))
    } finally {
      setDetailLoading(false)
    }
  }, [])

  // Deep-link via ?book=<id> from the Customers page.
  useEffect(() => {
    const id = searchParams.get("book")
    if (id) {
      loadDetail(id)
      setSearchParams({}, { replace: true })
    }
  }, [searchParams, loadDetail, setSearchParams])

  const handleSelect = (id: string) => loadDetail(id)

  const refreshDetail = () => {
    if (selected) loadDetail(selected.id)
  }

  const openEdit = () => {
    if (!selected) return
    setEditForm({ name: selected.name, phone: selected.phone, email: selected.email })
    setEditError("")
    setEditing(true)
    setConfirmingDelete(false)
  }

  const validateNewCustomer = (): string => {
    const phone = newPhone.replace(/\s+/g, "")
    if (!ONLY_DIGITS.test(phone)) return "Phone must contain digits only."
    if (phone && phone.length !== 10) return "Phone must be exactly 10 digits."
    if (newEmail.trim() && !EMAIL_OK.test(newEmail.trim())) return "Enter a valid email address (e.g. name@gmail.com)."
    return ""
  }

  const handleCreateBook = async () => {
    const formErr = validateNewCustomer()
    if (formErr) {
      setNewFormError(formErr)
      return
    }
    if (!newName.trim() && !newPhone.trim() && !newEmail.trim()) return
    setPosting(true)
    setNewFormError("")
    setError("")
    try {
      const res = await api.post("/api/v1/wallet/debt/books/", {
        name: newName,
        phone: newPhone.replace(/\s+/g, ""),
        email: newEmail.trim(),
      })
      setShowNewBook(false)
      setNewName("")
      setNewPhone("")
      setNewEmail("")
      setSelected(res.data)
      loadBooks()
    } catch (err) {
      const msg = fieldError(err)
      // Backend dedupe / validation message goes right under the form.
      setNewFormError(msg)
    } finally {
      setPosting(false)
    }
  }

  const handleSaveEdit = async () => {
    if (!selected) return
    const phone = editForm.phone.replace(/\s+/g, "")
    if (phone && !ONLY_DIGITS.test(phone)) {
      setEditError("Phone must contain digits only.")
      return
    }
    if (phone && phone.length !== 10) {
      setEditError("Phone must be exactly 10 digits.")
      return
    }
    if (editForm.email.trim() && !EMAIL_OK.test(editForm.email.trim())) {
      setEditError("Enter a valid email address (e.g. name@gmail.com).")
      return
    }
    const payload: Record<string, string> = {}
    if (editForm.name !== selected.name) payload.name = editForm.name
    if (editForm.phone.replace(/\s+/g, "") !== selected.phone) payload.phone = phone
    if (editForm.email.trim() !== selected.email) payload.email = editForm.email.trim()
    if (Object.keys(payload).length === 0) {
      setEditing(false)
      return
    }
    setPosting(true)
    setEditError("")
    try {
      const res = await api.patch(`/api/v1/wallet/debt/books/${selected.id}/`, payload)
      setSelected(res.data)
      setEditing(false)
      loadBooks()
    } catch (err) {
      setEditError(fieldError(err))
    } finally {
      setPosting(false)
    }
  }

  const handleDelete = async () => {
    if (!selected) return
    setPosting(true)
    setError("")
    try {
      await api.delete(`/api/v1/wallet/debt/books/${selected.id}/`)
      setSelected(null)
      setConfirmingDelete(false)
      loadBooks()
    } catch (err) {
      setError(fieldError(err))
      setConfirmingDelete(false)
    } finally {
      setPosting(false)
    }
  }

  const billTotals = useMemo(() => {
    let subtotal = 0
    let discountTotal = 0
    for (const line of billLines) {
      subtotal += num(line.quantity) * num(line.unit_price)
      discountTotal += num(line.discount)
    }
    const total = Math.max(subtotal - discountTotal, 0)
    const paid = num(amountPaid)
    const remaining = Math.max(total - paid, 0)
    return { subtotal, discountTotal, total, paid, remaining }
  }, [billLines, amountPaid])

  const addBillLine = () => {
    setBillLines((lines) => [
      ...lines,
      { product_id: null, product_name: "", quantity: "1", unit: "count", unit_price: "", discount: "0" },
    ])
  }

  const removeBillLine = (index: number) => {
    setBillLines((lines) => (lines.length > 1 ? lines.filter((_, i) => i !== index) : lines))
  }

  const updateBillLine = (index: number, patch: Partial<BillLine>) => {
    setBillLines((lines) => lines.map((line, i) => (i === index ? { ...line, ...patch } : line)))
  }

  const pickProduct = (lineIndex: number, product: ProductOption) => {
    setBillLines((lines) =>
      lines.map((line, i) =>
        i === lineIndex
          ? {
              ...line,
              product_id: product.id,
              product_name: product.name,
              unit: product.stock_unit === "kg" ? "kg" : "count",
              unit_price: String(num(product.selling_price)),
            }
          : line,
      ),
    )
    setPickingLine(null)
    setProductQuery("")
    setProductResults([])
  }

  const handleAddBill = async () => {
    if (!selected) return
    const items = billLines
      .filter((line) => line.product_name.trim() || num(line.unit_price))
      .map((line) => ({
        product_id: line.product_id,
        product_name: line.product_name.trim(),
        quantity: num(line.quantity) || 1,
        unit: line.unit,
        unit_price: String(num(line.unit_price)),
        discount: String(num(line.discount)),
      }))
    if (items.length === 0) {
      setError("Add at least one product to the bill.")
      return
    }
    if (items.some((i) => !i.product_name)) {
      setError("Give every product line a name (pick from catalog or type it).")
      return
    }
    setPosting(true)
    setError("")
    try {
      await api.post(`/api/v1/wallet/debt/books/${selected.id}/bills/`, {
        items,
        amount_paid: String(num(amountPaid)),
        note: billNote,
      })
      setBillLines([
        { product_id: null, product_name: "", quantity: "1", unit: "count", unit_price: "", discount: "0" },
      ])
      setAmountPaid("")
      setBillNote("")
      setShowBill(false)
      refreshDetail()
    } catch (err) {
      setError(fieldError(err))
    } finally {
      setPosting(false)
    }
  }

  const handlePayment = async () => {
    if (!selected) return
    setPosting(true)
    setError("")
    try {
      await api.post(`/api/v1/wallet/debt/books/${selected.id}/payments/`, {
        amount: payment.amount,
        note: payment.note,
      })
      setPayment({ amount: "", note: "" })
      setShowPayment(false)
      refreshDetail()
    } catch (err) {
      setError(fieldError(err))
    } finally {
      setPosting(false)
    }
  }

  const handleAdjust = async () => {
    if (!selected) return
    setPosting(true)
    setError("")
    try {
      await api.post(`/api/v1/wallet/debt/books/${selected.id}/adjustments/`, adjust)
      setAdjust({ amount: "", reason: "", note: "" })
      setShowAdjust(false)
      refreshDetail()
    } catch (err) {
      setError(fieldError(err))
    } finally {
      setPosting(false)
    }
  }

  const handleNote = async () => {
    if (!selected || !noteBody.trim()) return
    setPosting(true)
    setError("")
    try {
      await api.post(`/api/v1/wallet/debt/books/${selected.id}/notes/`, { body: noteBody })
      setNoteBody("")
      refreshDetail()
    } catch (err) {
      setError(fieldError(err))
    } finally {
      setPosting(false)
    }
  }

  const loadCustomers = async () => {
    setError("")
    try {
      const res = await api.get("/api/v1/admin-dashboard/customers/")
      setCustomers(res.data)
      setShowLink(true)
    } catch (err) {
      setError(fieldError(err))
    }
  }

  const handleLink = async () => {
    if (!selected || !linkUserId) return
    setPosting(true)
    setError("")
    try {
      const res = await api.post(`/api/v1/wallet/debt/books/${selected.id}/link/`, {
        user_id: parseInt(linkUserId, 10),
      })
      setSelected(res.data)
      setShowLink(false)
      setLinkUserId("")
      loadBooks()
    } catch (err) {
      setError(fieldError(err))
    } finally {
      setPosting(false)
    }
  }

  const entrySign = (e: DebtEntry) => {
    if (e.entry_type === "payment") return <span className="text-success">−₹{rupee(e.amount_paid)}</span>
    if (Number(e.delta) < 0) return <span className="text-success">−₹{rupee(Math.abs(Number(e.delta)))}</span>
    return <span className="text-danger">+₹{rupee(e.amount_added || e.delta)}</span>
  }

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

  const summaryCards = useMemo(() => {
    const s = selected?.summary
    return [
      { label: "Outstanding", value: s ? `₹${rupee(s.outstanding)}` : "—", icon: Wallet, tone: "text-danger" },
      { label: "Total Debt Added", value: s ? `₹${rupee(s.total_added)}` : "—", icon: TrendingUp, tone: "text-ink" },
      { label: "Total Paid", value: s ? `₹${rupee(s.total_paid)}` : "—", icon: IndianRupee, tone: "text-success" },
    ]
  }, [selected])

  return (
    <div>
      <BackButton to="/admin/dashboard" homeTo="/admin/dashboard" storeTo="/shop" />
      <div className="flex flex-wrap items-center gap-3 justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold">Debt Book</h1>
          <p className="text-sm text-ink-muted">Outstanding balances, bills, payments and notes for every customer — online or offline.</p>
        </div>
        <Button onClick={() => setShowNewBook((v) => !v)} variant="outline">
          <UserPlus className="h-4 w-4" /> {showNewBook ? "Close" : "New Customer"}
        </Button>
      </div>

      {showNewBook && (
        <div className="mt-4 rounded-2xl border border-border bg-surface p-5">
          <BackButton label="Back to Debt Book" onClick={() => setShowNewBook(false)} homeTo="/admin/dashboard" storeTo="/shop" />
          <h3 className="font-semibold mb-1">Add Offline / New Customer</h3>
          <p className="text-sm text-ink-muted mb-3">
            Create a debt record for a customer without a PACHOOS account. No login account is created. Phone must be 10 digits; email such as a Gmail address is used to avoid duplicate records.
          </p>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <label className="block flex-1">
              <span className="mb-1 block text-xs text-ink-muted">Full name</span>
              <Input placeholder="Customer name" value={newName} onChange={(e) => setNewName(e.target.value)} />
            </label>
            <label className="block flex-1">
              <span className="mb-1 block text-xs text-ink-muted">Phone</span>
              <Input
                placeholder="10 digits"
                value={newPhone}
                inputMode="numeric"
                onChange={(e) => setNewPhone(e.target.value.replace(/[^\d\s]/g, ""))}
              />
            </label>
            <label className="block flex-1">
              <span className="mb-1 block text-xs text-ink-muted">Email</span>
              <Input
                placeholder="name@gmail.com"
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
              />
            </label>
            <Button onClick={handleCreateBook} disabled={(!newName.trim() && !newPhone.trim() && !newEmail.trim()) || posting}>
              {posting && <Loader2 className="h-4 w-4 animate-spin" />} Create Book
            </Button>
          </div>
          {newFormError && (
            <p className="mt-3 rounded-xl bg-danger-muted px-3 py-2 text-sm text-danger">{newFormError}</p>
          )}
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-xl bg-danger-muted p-3 text-sm text-danger">{error}</div>
      )}

      <div className="mt-4 mb-4 flex items-center gap-3">
        <label className="relative block flex-1">
          <span className="mb-1 block text-xs text-ink-muted">Search</span>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" />
            <Input placeholder="Name, phone or account…" value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10" />
          </div>
        </label>
      </div>

      {loading ? <Loader /> : (
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Debt book list */}
          <div className="lg:col-span-1 rounded-2xl border border-border bg-surface overflow-hidden max-h-[70vh] overflow-y-auto">
            {books.map((b) => (
              <button
                key={b.id}
                onClick={() => handleSelect(b.id)}
                className={`w-full px-4 py-3 text-left border-b border-border hover:bg-ink-subtle transition-colors ${
                  selected?.id === b.id ? "bg-primary/10 border-l-2 border-l-primary" : ""
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium text-sm truncate">{b.display_name}</p>
                  <span className="text-sm font-semibold text-danger shrink-0">₹{rupee(b.outstanding)}</span>
                </div>
                <div className="flex items-center justify-between gap-2 mt-0.5">
                  <p className="text-xs text-ink-muted">{b.phone || b.email || "No phone"}{b.phone && b.email ? ` • ${b.email}` : ""} • {b.entry_count} entries</p>
                  {b.is_offline ? (
                    <Badge variant="warning">Offline</Badge>
                  ) : (
                    <Badge variant="success">Online</Badge>
                  )}
                </div>
              </button>
            ))}
            {books.length === 0 && (
              <div className="p-8 text-center text-sm text-ink-muted">
                <BookOpen className="mx-auto mb-2 h-8 w-8 opacity-30" />
                <p>No customers with debt yet.</p>
                <p className="text-xs mt-1">Use “New Customer” or add a bill from an existing book.</p>
              </div>
            )}
          </div>

          {/* Debt book detail */}
          <div className="lg:col-span-2">
            {detailLoading ? <Loader /> : !selected ? (
              <div className="rounded-2xl border border-border bg-surface p-8 text-center text-ink-muted">
                <BookOpen className="mx-auto mb-2 h-8 w-8 opacity-30" />
                <p>Select a customer’s Debt Book to manage it.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Overview */}
                <div className="rounded-2xl border border-border bg-surface p-6">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h3 className="flex items-center gap-2 font-semibold text-lg">
                        {selected.display_name}
                        {selected.is_offline ? (
                          <Badge variant="warning">Offline</Badge>
                        ) : (
                          <BadgeCheck className="h-4 w-4 text-success" />
                        )}
                      </h3>
                      <p className="text-xs text-ink-muted">
                        {selected.phone || "No phone"}{selected.email ? ` • ${selected.email}` : ""}
                        {selected.is_offline ? " • No website account" : ""}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {selected.is_offline && (
                        <>
                          <Button variant="secondary" size="sm" onClick={openEdit}>
                            <Pencil className="h-4 w-4" /> Edit
                          </Button>
                          <Button variant="outline" size="sm" onClick={() => { setConfirmingDelete((v) => !v); setEditing(false) }}>
                            <Trash2 className="h-4 w-4" /> Delete
                          </Button>
                          <Button variant="secondary" size="sm" onClick={loadCustomers}>
                            <Link2 className="h-4 w-4" /> Link to account
                          </Button>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Edit offline customer */}
                  {editing && selected.is_offline && (
                    <div className="mt-4 rounded-xl border border-border bg-ink-subtle p-4">
                      <BackButton label="Back to Debt Book" onClick={() => setEditing(false)} homeTo="/admin/dashboard" storeTo="/shop" />
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-semibold text-sm">Edit offline customer</h4>
                        <button
                          type="button"
                          onClick={() => setEditing(false)}
                          className="rounded-full p-1 hover:bg-ink-muted/20"
                          aria-label="Close edit"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
                        <label className="block flex-1">
                          <span className="mb-1 block text-xs text-ink-muted">Full name</span>
                          <Input placeholder="Customer name" value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
                        </label>
                        <label className="block flex-1">
                          <span className="mb-1 block text-xs text-ink-muted">Phone</span>
                          <Input
                            placeholder="10 digits"
                            inputMode="numeric"
                            value={editForm.phone}
                            onChange={(e) => setEditForm({ ...editForm, phone: e.target.value.replace(/[^\d\s]/g, "") })}
                          />
                        </label>
                        <label className="block flex-1">
                          <span className="mb-1 block text-xs text-ink-muted">Email</span>
                          <Input placeholder="name@gmail.com" type="email" value={editForm.email} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} />
                        </label>
                        <Button size="sm" onClick={handleSaveEdit} disabled={posting}>
                          {posting && <Loader2 className="h-4 w-4 animate-spin" />} Save
                        </Button>
                      </div>
                      {editError && <p className="mt-2 text-xs text-danger">{editError}</p>}
                    </div>
                  )}

                  {/* Delete confirmation */}
                  {confirmingDelete && selected.is_offline && (
                    <div className="mt-4 rounded-xl border border-danger/40 bg-danger-muted p-4">
                      <BackButton label="Back" onClick={() => setConfirmingDelete(false)} homeTo="/admin/dashboard" storeTo="/shop" />
                      <h4 className="font-semibold text-sm text-danger">Delete this offline customer?</h4>
                      <p className="text-xs text-ink-muted mt-1">
                        Deletion is only allowed when this book has no transaction history, so ledger and audit records are never lost.
                      </p>
                      <div className="mt-3 flex gap-2">
                        <Button size="sm" variant="danger" onClick={handleDelete} disabled={posting || selected.entries.length > 0}>
                          {posting && <Loader2 className="h-4 w-4 animate-spin" />} Yes, delete
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => setConfirmingDelete(false)}>Cancel</Button>
                      </div>
                      {selected.entries.length > 0 && (
                        <p className="text-xs text-danger mt-2">Cannot delete — this customer has {selected.entries.length} ledger entries.</p>
                      )}
                    </div>
                  )}

                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                    {summaryCards.map((c) => (
                      <div key={c.label} className="rounded-xl bg-ink-subtle px-4 py-3">
                        <div className="flex items-center gap-2 text-xs text-ink-muted">
                          <c.icon className="h-4 w-4" /> {c.label}
                        </div>
                        <p className={`text-xl font-bold ${c.tone}`}>{c.value}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Link form */}
                {showLink && selected.is_offline && (
                  <div className="rounded-2xl border border-border bg-surface p-5">
                    <BackButton label="Back to Debt Book" onClick={() => setShowLink(false)} homeTo="/admin/dashboard" storeTo="/shop" />
                    <h4 className="font-semibold mb-1 text-sm">Link to registered customer</h4>
                    <p className="text-xs text-ink-muted mb-3">
                      When this offline customer creates an account, associate their existing debt with the verified account. Historical records stay unchanged.
                    </p>
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
                      <label className="block flex-1">
                        <span className="mb-1 block text-xs text-ink-muted">Registered customer</span>
                        <select
                          value={linkUserId}
                          onChange={(e) => setLinkUserId(e.target.value)}
                          className="flex h-11 w-full rounded-xl border border-border bg-surface px-4 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 sm:flex-1"
                        >
                          <option value="">Select registered customer…</option>
                          {customers.map((c) => (
                            <option key={c.id} value={c.id}>{c.full_name || c.phone} ({c.phone})</option>
                          ))}
                        </select>
                      </label>
                      <Button onClick={handleLink} disabled={!linkUserId || posting}>
                        {posting && <Loader2 className="h-4 w-4 animate-spin" />} Link
                      </Button>
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" onClick={() => { setShowBill((v) => !v); setShowPayment(false); setShowAdjust(false) }}>
                    <ShoppingCart className="h-4 w-4" /> Add Debt / Bill
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => { setShowPayment((v) => !v); setShowBill(false); setShowAdjust(false) }}>
                    <IndianRupee className="h-4 w-4" /> Record Payment
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => { setShowAdjust((v) => !v); setShowBill(false); setShowPayment(false) }}>
                    <Receipt className="h-4 w-4" /> Adjust / Fix
                  </Button>
                </div>

                {showBill && (
                  <form onSubmit={(e) => { e.preventDefault(); handleAddBill() }} className="rounded-2xl border border-border bg-surface p-5 space-y-4">
                    <BackButton label="Back to Debt Book" onClick={() => setShowBill(false)} homeTo="/admin/dashboard" storeTo="/shop" />
                    <div className="flex items-center justify-between">
                      <h4 className="font-semibold text-sm">Add Debt — one bill, multiple products</h4>
                      <Button type="button" size="sm" variant="outline" onClick={addBillLine}>
                        <Plus className="h-4 w-4" /> Add product
                      </Button>
                    </div>

                    {/* Bill lines */}
                    <div className="space-y-3">
                      {billLines.map((line, i) => {
                        const lineTotal = Math.max(num(line.quantity) * num(line.unit_price) - num(line.discount), 0)
                        return (
                          <div key={i} className="rounded-xl border border-border bg-ink-subtle p-3 space-y-2">
                            <div ref={pickerRef} className="relative">
                              <div className="flex items-center justify-between">
                                <label className="block flex-1">
                                  <span className="mb-1 block text-xs text-ink-muted">Product</span>
                                  <div className="relative">
                                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" />
                                    <Input
                                      placeholder="Search catalog or type a name…"
                                      value={line.product_name}
                                      className="pl-10"
                                      onChange={(e) => {
                                        updateBillLine(i, { product_name: e.target.value, product_id: null })
                                        setPickingLine(i)
                                        setProductQuery(e.target.value)
                                      }}
                                      onFocus={() => {
                                        setPickingLine(i)
                                        setProductQuery(line.product_name)
                                      }}
                                    />
                                  </div>
                                </label>
                                <button type="button" onClick={() => removeBillLine(i)} className="ml-2 rounded-full p-1.5 hover:bg-danger-muted hover:text-danger" aria-label="Remove line">
                                  <X className="h-4 w-4" />
                                </button>
                              </div>
                              {pickingLine === i && productResults.length > 0 && (
                                <div className="absolute left-0 right-0 top-full mt-1 z-20 max-h-56 overflow-y-auto rounded-xl border border-border bg-surface shadow-lg">
                                  {productResults.map((p) => (
                                    <button
                                      type="button"
                                      key={p.id}
                                      onClick={() => pickProduct(i, p)}
                                      className="w-full px-3 py-2 text-left text-sm hover:bg-ink-subtle"
                                    >
                                      <span className="font-medium">{p.name}</span>
                                      <span className="ml-2 text-xs text-ink-muted">₹{rupee(p.selling_price)} / {p.stock_unit}</span>
                                    </button>
                                  ))}
                                </div>
                              )}
                              {pickingLine === i && productQuery.trim() && productResults.length === 0 && (
                                <div className="absolute left-0 right-0 top-full mt-1 z-20 rounded-xl border border-border bg-surface px-3 py-2 text-xs text-ink-muted shadow-lg">
                                  No catalog match — the typed name will be saved as a custom item.
                                </div>
                              )}
                            </div>

                            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5 sm:items-end">
                              <label className="block">
                                <span className="mb-1 block text-xs text-ink-muted">Qty</span>
                                <Input
                                  type="number" min="0.01" step="0.01"
                                  placeholder="0"
                                  value={line.quantity}
                                  onChange={(e) => updateBillLine(i, { quantity: e.target.value })}
                                />
                              </label>
                              <label className="block">
                                <span className="mb-1 block text-xs text-ink-muted">Unit</span>
                                <select
                                  value={line.unit}
                                  onChange={(e) => updateBillLine(i, { unit: e.target.value as "kg" | "count" })}
                                  className="flex h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
                                >
                                  <option value="count">count</option>
                                  <option value="kg">kg</option>
                                </select>
                              </label>
                              <label className="block col-span-2 sm:col-span-1">
                                <span className="mb-1 block text-xs text-ink-muted">Unit price (₹)</span>
                                <Input
                                  type="number" min="0" step="0.01"
                                  placeholder="0.00"
                                  value={line.unit_price}
                                  onChange={(e) => updateBillLine(i, { unit_price: e.target.value })}
                                />
                              </label>
                              <label className="block col-span-2 sm:col-span-1">
                                <span className="mb-1 block text-xs text-ink-muted">Discount (₹)</span>
                                <Input
                                  type="number" min="0" step="0.01"
                                  placeholder="0.00"
                                  value={line.discount}
                                  onChange={(e) => updateBillLine(i, { discount: e.target.value })}
                                />
                              </label>
                              <p className="col-span-2 sm:col-span-1 flex items-center justify-end text-sm font-semibold text-ink sm:justify-start sm:px-2">
                                ₹{rupee(lineTotal)}
                              </p>
                            </div>
                          </div>
                        )
                      })}
                    </div>

                    {/* Totals */}
                    <div className="rounded-xl border border-border bg-ink-subtle p-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="text-sm text-ink-muted space-y-1">
                          <p>Subtotal: <span className="font-medium text-ink">₹{rupee(billTotals.subtotal)}</span></p>
                          <p>Discount: <span className="font-medium text-ink">−₹{rupee(billTotals.discountTotal)}</span></p>
                          <p className="text-base font-bold text-ink">Bill total: ₹{rupee(billTotals.total)}</p>
                        </div>
                        <label className="block w-full sm:w-44">
                          <span className="mb-1 block text-xs text-ink-muted">Amount paid now (₹)</span>
                          <Input type="number" min="0" step="0.01" value={amountPaid} onChange={(e) => setAmountPaid(e.target.value)} />
                        </label>
                        <div className="text-sm">
                          <p className="text-ink-muted">Remaining debt on this bill</p>
                          <p className={`text-xl font-bold ${billTotals.remaining > 0 ? "text-danger" : "text-success"}`}>₹{rupee(billTotals.remaining)}</p>
                        </div>
                      </div>
                    </div>

                    <label className="block">
                      <span className="mb-1 block text-xs text-ink-muted">Note (optional)</span>
                      <Input placeholder="Add a note for this bill" value={billNote} onChange={(e) => setBillNote(e.target.value)} />
                    </label>
                    <Button type="submit" disabled={posting || billTotals.total <= 0}>
                      {posting && <Loader2 className="h-4 w-4 animate-spin" />} Save Bill ({rupee(billTotals.total)})
                    </Button>
                  </form>
                )}

                {showPayment && (
                  <form onSubmit={(e) => { e.preventDefault(); handlePayment() }} className="rounded-2xl border border-border bg-surface p-5 space-y-3">
                    <BackButton label="Back to Debt Book" onClick={() => setShowPayment(false)} homeTo="/admin/dashboard" storeTo="/shop" />
                    <h4 className="font-semibold text-sm">Record Payment</h4>
                    <label className="block">
                      <span className="mb-1 block text-xs text-ink-muted">Amount received (₹)</span>
                      <Input type="number" min="0.01" step="0.01" placeholder="0.00" value={payment.amount} onChange={(e) => setPayment({ ...payment, amount: e.target.value })} />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-xs text-ink-muted">Note (optional)</span>
                      <Input placeholder="Payment note" value={payment.note} onChange={(e) => setPayment({ ...payment, note: e.target.value })} />
                    </label>
                    <Button type="submit" variant="secondary" disabled={posting || !payment.amount}>
                      {posting && <Loader2 className="h-4 w-4 animate-spin" />} Save Payment
                    </Button>
                  </form>
                )}

                {showAdjust && (
                  <form onSubmit={(e) => { e.preventDefault(); handleAdjust() }} className="rounded-2xl border border-border bg-surface p-5 space-y-3">
                    <BackButton label="Back to Debt Book" onClick={() => setShowAdjust(false)} homeTo="/admin/dashboard" storeTo="/shop" />
                    <h4 className="font-semibold text-sm">Adjust / Fix Entry</h4>
                    <p className="text-xs text-ink-muted -mt-2">
                      History is never overwritten — a signed correction entry is appended and audited. Use + to add and − to reduce.
                    </p>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <label className="block">
                        <span className="mb-1 block text-xs text-ink-muted">Signed amount (₹)</span>
                        <Input type="number" step="0.01" placeholder="e.g. -25.00" value={adjust.amount} onChange={(e) => setAdjust({ ...adjust, amount: e.target.value })} />
                      </label>
                      <label className="block">
                        <span className="mb-1 block text-xs text-ink-muted">Reason</span>
                        <Input placeholder="Why this correction" value={adjust.reason} onChange={(e) => setAdjust({ ...adjust, reason: e.target.value })} />
                      </label>
                    </div>
                    <label className="block">
                      <span className="mb-1 block text-xs text-ink-muted">Note (optional)</span>
                      <Input placeholder="Adjustment note" value={adjust.note} onChange={(e) => setAdjust({ ...adjust, note: e.target.value })} />
                    </label>
                    <Button type="submit" variant="outline" disabled={posting || !adjust.amount}>
                      {posting && <Loader2 className="h-4 w-4 animate-spin" />} Apply Correction
                    </Button>
                  </form>
                )}

                {/* Statement / ledger */}
                <div className="rounded-2xl border border-border bg-surface p-6">
                  <h4 className="font-semibold mb-3">Transactions & Bills</h4>
                  {selected.entries.length === 0 ? (
                    <p className="text-sm text-ink-muted">No transactions yet.</p>
                  ) : (
                    <div className="space-y-2">
                      {selected.entries.map((e) => (
                        <div key={e.id} className="rounded-xl bg-ink-subtle px-4 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <div className="min-w-0">
                              <p className="text-sm font-medium truncate">
                                {e.entry_type === "bill" && (e.product_name || "Bill")}
                                {e.entry_type === "payment" && "Payment received"}
                                {e.entry_type === "adjustment" && (e.reason || "Adjustment")}
                              </p>
                              <p className="text-xs text-ink-muted">
                                <Badge variant={e.entry_type === "payment" ? "success" : "default"} className="mr-1">
                                  {e.entry_label}
                                </Badge>
                                {new Date(e.created_at).toLocaleString()} • by {e.updated_by_name || "Admin"}
                              </p>
                            </div>
                            <div className="text-right shrink-0">{entrySign(e)}</div>
                          </div>
                          {entryLines(e)}
                          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
                            <span>Previous: ₹{rupee(e.prev_balance)}</span>
                            {e.entry_type === "bill" && num(e.amount_paid) > 0 && <span>Paid at counter: ₹{rupee(e.amount_paid)}</span>}
                            <span className="font-medium text-ink">Remaining: ₹{rupee(e.remaining)}</span>
                          </div>
                          {e.note && <p className="mt-1 text-xs italic text-ink-muted">“{e.note}”</p>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Notes / Chat */}
                <div className="rounded-2xl border border-border bg-surface p-6">
                  <h4 className="font-semibold mb-3 flex items-center gap-2">
                    <MessageSquare className="h-4 w-4" /> Notes / Chat
                  </h4>
                  {selected.notes.length === 0 ? (
                    <p className="text-sm text-ink-muted">No notes yet.</p>
                  ) : (
                    <div className="space-y-2">
                      {selected.notes.map((n) => {
                        const isAdmin = n.sender_role !== "customer"
                        return (
                          <div key={n.id} className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${isAdmin ? "bg-primary/10 text-ink" : "bg-ink-subtle text-ink"}`}>
                            <p>{n.body}</p>
                            <p className="mt-1 text-xs text-ink-muted">
                              <Badge variant={isAdmin ? "default" : "secondary"} className="mr-1">{isAdmin ? "Admin" : "Customer"}</Badge>
                              {n.sender_name} • {new Date(n.created_at).toLocaleString()}
                            </p>
                          </div>
                        )
                      })}
                    </div>
                  )}
                  <div className="mt-3 flex gap-2">
                    <label className="block flex-1">
                      <span className="mb-1 block text-xs text-ink-muted">Note</span>
                      <Input placeholder="Add a note for this customer…" value={noteBody} onChange={(e) => setNoteBody(e.target.value)} />
                    </label>
                    <Button onClick={handleNote} disabled={posting || !noteBody.trim()}>
                      {posting && <Loader2 className="h-4 w-4 animate-spin" />} Post
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}