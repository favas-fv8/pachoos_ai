// Admin Payments — manage the shop's bank account(s) used for payouts/refunds.
// Only the masked account number is shown; the full number is encrypted at rest.
import { useCallback, useEffect, useState } from "react"
import { CreditCard, Landmark, Plus, Pencil, Trash2, X, ShieldCheck, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { BackButton } from "@/components/ui/back-button"
import { api, toApiError } from "@/lib/api/client"
import { Loader } from "./shared"

interface BankAccount {
  id: number
  account_holder_name: string
  bank_name: string
  account_number_masked: string
  account_number_last4: string
  ifsc: string
  is_active: boolean
  owner_shop: boolean
  created_at: string
}

const ONLY_DIGITS = /^\d{6,18}$/
const IFSC_OK = /^[A-Za-z]{4}0[A-Z0-9]{6}$/

const fieldError = (err: unknown): string => {
  const data = (err as { response?: { data?: unknown } })?.response?.data
  if (data && typeof data === "object") {
    const d = data as Record<string, unknown>
    for (const value of Object.values(d)) {
      if (Array.isArray(value) && value.length > 0) return String(value[0])
    }
    const nested = d.error
    if (nested && typeof nested === "object") {
      const msg = (nested as Record<string, unknown>).message
      if (typeof msg === "string") return msg
    } else if (typeof nested === "string" && nested) return nested
  }
  return toApiError(err).message
}

export default function AdminPayments() {
  const [accounts, setAccounts] = useState<BankAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [posting, setPosting] = useState(false)

  // Add / edit form
  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState({ account_holder_name: "", bank_name: "", account_number: "", ifsc: "", is_active: true })
  const [formError, setFormError] = useState("")
  const [confirmingId, setConfirmingId] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const res = await api.get("/api/v1/payments/bank-accounts/")
      setAccounts(res.data)
    } catch (err) {
      setError(toApiError(err).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const openAdd = () => {
    setEditingId(null)
    setForm({ account_holder_name: "", bank_name: "", account_number: "", ifsc: "", is_active: true })
    setFormError("")
    setFormOpen(true)
  }

  const openEdit = (a: BankAccount) => {
    setEditingId(a.id)
    setForm({ account_holder_name: a.account_holder_name, bank_name: a.bank_name, account_number: a.account_number_last4, ifsc: a.ifsc, is_active: a.is_active })
    setFormError("")
    setFormOpen(true)
  }

  const closeForm = () => {
    setFormOpen(false)
    setEditingId(null)
    setForm({ account_holder_name: "", bank_name: "", account_number: "", ifsc: "", is_active: true })
    setFormError("")
  }

  const validate = (): string => {
    if (!form.account_holder_name.trim()) return "Account holder name is required."
    if (!form.bank_name.trim()) return "Bank name is required."
    const accountNumber = form.account_number.replace(/[\s-]/g, "")
    if (!ONLY_DIGITS.test(accountNumber)) return "Account number must be 6–18 digits."
    const ifsc = form.ifsc.trim().toUpperCase()
    if (!IFSC_OK.test(ifsc)) return "Enter a valid IFSC (e.g. HDFC0001234)."
    return ""
  }

  const handleSubmit = async () => {
    const err = validate()
    if (err) {
      setFormError(err)
      return
    }
    setPosting(true)
    setFormError("")
    try {
      const payload = {
        account_holder_name: form.account_holder_name.trim(),
        bank_name: form.bank_name.trim(),
        account_number: form.account_number.replace(/[\s-]/g, ""),
        ifsc: form.ifsc.trim().toUpperCase(),
        is_active: form.is_active,
      }
      if (editingId) {
        await api.patch(`/api/v1/payments/bank-accounts/${editingId}/`, payload)
      } else {
        await api.post("/api/v1/payments/bank-accounts/", payload)
      }
      closeForm()
      await load()
    } catch (caught) {
      setFormError(fieldError(caught))
    } finally {
      setPosting(false)
    }
  }

  const handleDelete = async (id: number) => {
    setPosting(true)
    setError("")
    try {
      await api.delete(`/api/v1/payments/bank-accounts/${id}/`)
      setConfirmingId(null)
      await load()
    } catch (caught) {
      setError(fieldError(caught))
    } finally {
      setPosting(false)
    }
  }

  return (
    <div>
      <BackButton to="/admin/dashboard" homeTo="/admin/dashboard" storeTo="/shop" />
      <div>
        <h1 className="font-display text-2xl font-bold">Payments</h1>
        <p className="text-sm text-ink-muted">
          Manage the shop's bank account(s) used for payments and refunds. Account numbers are encrypted — never enter online-banking passwords, PINs or credentials.
        </p>
      </div>

      {error && (
        <div className="mt-4 rounded-xl bg-danger-muted p-3 text-sm text-danger">{error}</div>
      )}

      {/* Shop bank account */}
      <div className="mt-6 rounded-2xl border border-border bg-surface p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold flex items-center gap-2">
              <Landmark className="h-4 w-4 text-primary" /> Shop Bank Account
            </h3>
            <p className="text-sm text-ink-muted mt-0.5">
              Payout details for the shop. The complete account number is never displayed.
            </p>
          </div>
          <div className="flex gap-2">
            {!formOpen && (
              <Button size="sm" onClick={openAdd}>
                <Plus className="h-4 w-4" /> Add account
              </Button>
            )}
          </div>
        </div>

        {/* Add / edit form */}
        {formOpen && (
          <div className="mt-4 rounded-xl border border-border bg-ink-subtle p-4 space-y-3">
            <BackButton label="Back to Payments" onClick={closeForm} homeTo="/admin/dashboard" storeTo="/shop" />
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-semibold">{editingId ? "Edit bank account" : "Add bank account"}</h4>
              <button type="button" onClick={closeForm} className="rounded-full p-1 hover:bg-ink-muted/20" aria-label="Close form">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Input placeholder="Account holder name" value={form.account_holder_name} onChange={(e) => setForm({ ...form, account_holder_name: e.target.value })} />
              <Input placeholder="Bank name" value={form.bank_name} onChange={(e) => setForm({ ...form, bank_name: e.target.value })} />
              <Input
                placeholder="Account number (digits only)"
                inputMode="numeric"
                value={form.account_number}
                onChange={(e) => setForm({ ...form, account_number: e.target.value.replace(/[^\d\s-]/g, "") })}
              />
              <Input
                placeholder="IFSC (e.g. HDFC0001234)"
                value={form.ifsc}
                onChange={(e) => setForm({ ...form, ifsc: e.target.value.replace(/[^A-Za-z0-9]/g, "") })}
              />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} className="h-4 w-4" />
              Account active
            </label>
            {formError && <p className="text-xs text-danger">{formError}</p>}
            <div className="flex gap-2">
              <Button size="sm" onClick={handleSubmit} disabled={posting}>
                {posting && <Loader2 className="h-4 w-4 animate-spin" />} {editingId ? "Save changes" : "Add account"}
              </Button>
              <Button size="sm" variant="outline" onClick={closeForm}>Cancel</Button>
            </div>
          </div>
        )}

        {loading ? <Loader /> : (
          <div className="mt-4 space-y-2">
            {accounts.length === 0 ? (
              <div className="rounded-xl bg-ink-subtle p-6 text-center text-sm text-ink-muted">
                <CreditCard className="mx-auto mb-2 h-8 w-8 opacity-30" />
                <p>No shop bank account yet. Add one above.</p>
              </div>
            ) : (
              accounts.map((a) => (
                <div key={a.id} className="rounded-xl bg-ink-subtle px-4 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium flex items-center gap-2">
                        {a.account_holder_name}
                        <Badge variant={a.is_active ? "success" : "secondary"}>
                          {a.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </p>
                      <p className="text-xs text-ink-muted">
                        {a.bank_name} • {a.account_number_masked} • IFSC: {a.ifsc}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      <Button size="sm" variant="ghost" onClick={() => openEdit(a)}>
                        <Pencil className="h-4 w-4" /> Edit
                      </Button>
                      {confirmingId === a.id ? (
                        <span className="flex items-center gap-2">
                          <span className="text-xs text-danger">Delete this account?</span>
                          <BackButton label="Back" onClick={() => setConfirmingId(null)} homeTo="/admin/dashboard" storeTo="/shop" />
                          <Button size="sm" variant="danger" onClick={() => handleDelete(a.id)} disabled={posting}>
                            {posting && <Loader2 className="h-4 w-4 animate-spin" />} Delete
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => setConfirmingId(null)}>Cancel</Button>
                        </span>
                      ) : (
                        <Button size="sm" variant="ghost" onClick={() => setConfirmingId(a.id)}>
                          <Trash2 className="h-4 w-4" /> Delete
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      <div className="mt-4 flex items-start gap-2 rounded-xl bg-ink-subtle p-3 text-xs text-ink-muted">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-success" />
        <p>
          Account numbers are encrypted at rest and only their last 4 digits are shown. Online-banking passwords, PINs or other credentials are never stored.
        </p>
      </div>
    </div>
  )
}