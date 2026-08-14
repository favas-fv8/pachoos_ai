import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import {
  CreditCard,
  Loader2,
  AlertTriangle,
  RotateCcw,
  Landmark,
  Plus,
  Pencil,
  Trash2,
  X,
  ShieldCheck,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { BackButton } from '@/components/ui/back-button'
import { fetchListAll, toApiError } from '@/lib/api/client'
import { api } from '@/lib/api/client'

interface PaymentRecord {
  id: string
  order_number: string
  grand_total: string
  status: string
  created_at: string
}

interface BankAccount {
  id: number
  account_holder_name: string
  bank_name: string
  account_number_masked: string
  account_number_last4: string
  ifsc: string
  is_active: boolean
}

const paymentStatus = (orderStatus: string) => {
  if (orderStatus === 'delivered' || orderStatus === 'refunded') return { label: 'Captured', tone: 'success' as const }
  if (orderStatus === 'cancelled') return { label: 'Refunded', tone: 'danger' as const }
  if (orderStatus === 'pending') return { label: 'Awaiting payment', tone: 'warning' as const }
  return { label: 'In progress', tone: 'secondary' as const }
}

const ONLY_DIGITS = /^\d{6,18}$/
const IFSC_OK = /^[A-Za-z]{4}0[A-Z0-9]{6}$/

const fieldError = (err: unknown): string => {
  const data = (err as { response?: { data?: unknown } })?.response?.data
  if (data && typeof data === 'object') {
    const d = data as Record<string, unknown>
    for (const value of Object.values(d)) {
      if (Array.isArray(value) && value.length > 0) return String(value[0])
    }
    const nested = (d as Record<string, unknown>).error
    if (typeof nested === 'string' && nested) return nested
    if (nested && typeof nested === 'object') {
      const msg = (nested as Record<string, unknown>).message
      if (typeof msg === 'string') return msg
    }
  }
  return toApiError(err).message
}

export default function Payments() {
  const [records, setRecords] = useState<PaymentRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // bank account state
  const [accounts, setAccounts] = useState<BankAccount[]>([])
  const [bankLoading, setBankLoading] = useState(true)
  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState({ account_holder_name: '', bank_name: '', account_number: '', ifsc: '' })
  const [formError, setFormError] = useState('')
  const [posting, setPosting] = useState(false)
  const [confirmingId, setConfirmingId] = useState<number | null>(null)

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

  const loadBank = useCallback(async () => {
    setBankLoading(true)
    try {
      const res = await api.get('/api/v1/payments/my/bank-accounts/')
      setAccounts(res.data)
    } catch {
      /* bank list is best-effort — the payments list still renders */
    } finally {
      setBankLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
    void loadBank()
  }, [load, loadBank])

  const validate = (): string => {
    if (!form.account_holder_name.trim()) return 'Account holder name is required.'
    if (!form.bank_name.trim()) return 'Bank name is required.'
    const accountNumber = form.account_number.replace(/[\s-]/g, '')
    if (!ONLY_DIGITS.test(accountNumber)) return 'Account number must be 6–18 digits.'
    if (!IFSC_OK.test(form.ifsc.trim().toUpperCase())) return 'Enter a valid IFSC (e.g. HDFC0001234).'
    return ''
  }

  const closeForm = () => {
    setFormOpen(false)
    setEditingId(null)
    setForm({ account_holder_name: '', bank_name: '', account_number: '', ifsc: '' })
    setFormError('')
  }

  const openEdit = (a: BankAccount) => {
    setEditingId(a.id)
    setForm({
      account_holder_name: a.account_holder_name,
      bank_name: a.bank_name,
      account_number: a.account_number_last4,
      ifsc: a.ifsc,
    })
    setFormError('')
    setFormOpen(true)
  }

  const handleSubmit = async () => {
    const err = validate()
    if (err) {
      setFormError(err)
      return
    }
    setPosting(true)
    setFormError('')
    try {
      const payload = {
        account_holder_name: form.account_holder_name.trim(),
        bank_name: form.bank_name.trim(),
        account_number: form.account_number.replace(/[\s-]/g, ''),
        ifsc: form.ifsc.trim().toUpperCase(),
      }
      if (editingId) {
        await api.patch(`/api/v1/payments/my/bank-accounts/${editingId}/`, payload)
      } else {
        await api.post('/api/v1/payments/my/bank-accounts/', payload)
      }
      closeForm()
      void loadBank()
    } catch (caught) {
      setFormError(fieldError(caught))
    } finally {
      setPosting(false)
    }
  }

  const handleDelete = async (id: number) => {
    setPosting(true)
    try {
      await api.delete(`/api/v1/payments/my/bank-accounts/${id}/`)
      setConfirmingId(null)
      void loadBank()
    } catch (caught) {
      setError(fieldError(caught))
    } finally {
      setPosting(false)
    }
  }

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

      {/* Bank accounts */}
      <div className="rounded-2xl border border-border bg-surface p-6 shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-display text-lg font-semibold flex items-center gap-2">
              <Landmark className="h-5 w-5 text-primary" /> My Bank Account
            </h3>
            <p className="text-sm text-ink-muted mt-0.5">
              Add the account you use to settle payments. Only the last 4 digits are shown.
            </p>
          </div>
          {!formOpen && (
            <Button size="sm" onClick={() => { setEditingId(null); setForm({ account_holder_name: '', bank_name: '', account_number: '', ifsc: '' }); setFormError(''); setFormOpen(true) }}>
              <Plus className="h-4 w-4" /> Add account
            </Button>
          )}
        </div>

        {formOpen && (
          <div className="mt-4 rounded-xl border border-border bg-ink-subtle p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-semibold">{editingId ? 'Edit bank account' : 'Add bank account'}</h4>
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
                onChange={(e) => setForm({ ...form, account_number: e.target.value.replace(/[^\d\s-]/g, '') })}
              />
              <Input
                placeholder="IFSC (e.g. HDFC0001234)"
                value={form.ifsc}
                onChange={(e) => setForm({ ...form, ifsc: e.target.value.replace(/[^A-Za-z0-9]/g, '') })}
              />
            </div>
            {formError && <p className="text-xs text-danger">{formError}</p>}
            <div className="flex gap-2">
              <Button size="sm" onClick={handleSubmit} disabled={posting}>
                {posting && <Loader2 className="h-4 w-4 animate-spin" />} {editingId ? 'Save changes' : 'Add account'}
              </Button>
              <Button size="sm" variant="outline" onClick={closeForm}>Cancel</Button>
            </div>
            <p className="flex items-center gap-1.5 text-xs text-ink-muted">
              <ShieldCheck className="h-3.5 w-3.5 text-success" /> Encrypted and masked. Never stored or shared beyond your profile.
            </p>
          </div>
        )}

        {bankLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
          </div>
        ) : (
          <div className="mt-3 space-y-2">
            {accounts.length === 0 ? (
              <p className="rounded-xl bg-ink-subtle p-4 text-center text-sm text-ink-muted">
                <CreditCard className="mx-auto mb-1 h-6 w-6 opacity-30" />
                No bank account added yet.
              </p>
            ) : (
              accounts.map((a) => (
                <div key={a.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-ink-subtle px-4 py-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium flex items-center gap-2">
                      {a.account_holder_name}
                      <Badge variant={a.is_active ? 'success' : 'secondary'}>{a.is_active ? 'Active' : 'Inactive'}</Badge>
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
                        <span className="text-xs text-danger">Remove this account?</span>
                        <Button size="sm" variant="danger" onClick={() => handleDelete(a.id)} disabled={posting}>
                          {posting && <Loader2 className="h-4 w-4 animate-spin" />} Remove
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => setConfirmingId(null)}>Cancel</Button>
                      </span>
                    ) : (
                      <Button size="sm" variant="ghost" onClick={() => setConfirmingId(a.id)}>
                        <Trash2 className="h-4 w-4" /> Remove
                      </Button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

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