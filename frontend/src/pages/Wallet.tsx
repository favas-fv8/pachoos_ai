// Wallet page — cashback balance, voucher list, voucher redemption.
import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import { BackButton } from "@/components/ui/back-button"
import {
  Wallet,
  Gift,
  Clock,
  CheckCircle,
  AlertCircle,
  Loader2,
  Plus,
  Ticket,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { api } from "@/lib/api/client"

interface WalletBalance {
  cashback_balance: string
  debt_balance: string
  active_vouchers: number
  total_cashback_earned: string
}

interface Voucher {
  id: string
  code: string
  amount: string
  status: string
  expires_at: string | null
  used_at: string | null
  created_at: string
}

interface LedgerEntry {
  id: string
  delta: string
  balance_after: string
  reason: string
  note: string
  created_at: string
}

export default function WalletPage() {
  const [balance, setBalance] = useState<WalletBalance | null>(null)
  const [vouchers, setVouchers] = useState<Voucher[]>([])
  const [history, setHistory] = useState<LedgerEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [redeemCode, setRedeemCode] = useState("")
  const [redeemLoading, setRedeemLoading] = useState(false)
  const [redeemMsg, setRedeemMsg] = useState("")
  const [mintLoading, setMintLoading] = useState(false)

  useEffect(() => {
    fetchWalletData()
  }, [])

  const fetchWalletData = async () => {
    setLoading(true)
    setError("")
    try {
      const [balRes, voucherRes, historyRes] = await Promise.all([
        api.get("/api/v1/wallet/balance/"),
        api.get("/api/v1/wallet/vouchers/"),
        api.get("/api/v1/wallet/history/"),
      ])
      setBalance(balRes.data)
      setVouchers(voucherRes.data)
      setHistory(historyRes.data)
    } catch {
      setError("Failed to load wallet data.")
    } finally {
      setLoading(false)
    }
  }

  const handleRedeem = async () => {
    if (!redeemCode.trim()) return
    setRedeemLoading(true)
    setRedeemMsg("")
    try {
      const res = await api.post("/api/v1/wallet/vouchers/redeem/", {
        voucher_code: redeemCode,
        order_id: "00000000-0000-0000-0000-000000000000",
      })
      setRedeemMsg(res.data.message)
      setRedeemCode("")
      fetchWalletData()
    } catch (err: any) {
      setRedeemMsg(err?.response?.data?.error?.message || "Redemption failed.")
    } finally {
      setRedeemLoading(false)
    }
  }

  const handleMint = async () => {
    setMintLoading(true)
    try {
      await api.post("/api/v1/wallet/vouchers/mint/")
      fetchWalletData()
    } catch (err: any) {
      setError(err?.response?.data?.error?.message || "Minting failed.")
    } finally {
      setMintLoading(false)
    }
  }

  const statusColor = (s: string) => {
    if (s === "active") return "success"
    if (s === "used") return "secondary"
    return "danger"
  }

  if (loading) {
    return (
      <div className="container-px mx-auto py-8">
        <BackButton to="/account" />
        <div className="flex justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </div>
    )
  }

  return (
    <div>
      <BackButton to="/account" />
      <h1 className="font-display text-3xl font-bold">My Wallet</h1>

      {error && (
        <div className="mt-4 rounded-xl bg-danger-muted p-3 text-sm text-danger flex items-center gap-2">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}

      {/* Balance Cards */}
      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border border-border bg-surface p-6 shadow-card"
        >
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-success/10 text-success">
              <Wallet className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-ink-muted">Cashback Balance</p>
              <p className="text-2xl font-bold text-success">₹{balance?.cashback_balance || "0.00"}</p>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="rounded-2xl border border-border bg-surface p-6 shadow-card"
        >
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary">
              <Ticket className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-ink-muted">Active Vouchers</p>
              <p className="text-2xl font-bold">{balance?.active_vouchers || 0}</p>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="rounded-2xl border border-border bg-surface p-6 shadow-card"
        >
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-warning/10 text-warning">
              <Gift className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-ink-muted">Total Earned</p>
              <p className="text-2xl font-bold">₹{balance?.total_cashback_earned || "0.00"}</p>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Mint + Redeem Actions */}
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <section className="rounded-2xl border border-border bg-surface p-6 shadow-card">
          <h2 className="font-display text-lg font-semibold mb-3 flex items-center gap-2">
            <Plus className="h-5 w-5 text-primary" /> Mint Voucher
          </h2>
          <p className="text-sm text-ink-muted mb-3">
            Convert ₹10 cashback into a voucher. Vouchers expire in 60 days.
          </p>
          <Button onClick={handleMint} disabled={mintLoading} className="w-full">
            {mintLoading ? (
              <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Minting...</>
            ) : (
              "Mint ₹10 Voucher"
            )}
          </Button>
        </section>

        <section className="rounded-2xl border border-border bg-surface p-6 shadow-card">
          <h2 className="font-display text-lg font-semibold mb-3 flex items-center gap-2">
            <Gift className="h-5 w-5 text-primary" /> Redeem Voucher
          </h2>
          <div className="flex gap-2">
            <Input
              placeholder="Enter voucher code"
              value={redeemCode}
              onChange={(e) => setRedeemCode(e.target.value)}
            />
            <Button onClick={handleRedeem} disabled={redeemLoading} variant="outline">
              {redeemLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Apply"}
            </Button>
          </div>
          {redeemMsg && (
            <p className="mt-2 text-sm text-success">{redeemMsg}</p>
          )}
        </section>
      </div>

      {/* Vouchers List */}
      <section className="mt-6 rounded-2xl border border-border bg-surface p-6 shadow-card">
        <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
          <Ticket className="h-5 w-5 text-primary" /> My Vouchers
        </h2>
        {vouchers.length === 0 ? (
          <p className="text-sm text-ink-muted">No vouchers yet. Earn cashback to mint one!</p>
        ) : (
          <div className="space-y-3">
            {vouchers.map((v) => (
              <div key={v.id} className="flex items-center justify-between rounded-xl bg-ink-subtle p-4">
                <div>
                  <p className="font-mono font-semibold">{v.code}</p>
                  <p className="text-xs text-ink-muted">
                    ₹{v.amount} • Expires: {v.expires_at ? new Date(v.expires_at).toLocaleDateString() : "Never"}
                  </p>
                </div>
                <Badge variant={statusColor(v.status) as any}>
                  {v.status === "active" && <CheckCircle className="mr-1 h-3 w-3" />}
                  {v.status}
                </Badge>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Ledger History */}
      <section className="mt-6 rounded-2xl border border-border bg-surface p-6 shadow-card">
        <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
          <Clock className="h-5 w-5 text-primary" /> Cashback History
        </h2>
        {history.length === 0 ? (
          <p className="text-sm text-ink-muted">No transactions yet.</p>
        ) : (
          <div className="space-y-2">
            {history.map((h) => (
              <div key={h.id} className="flex items-center justify-between rounded-xl bg-ink-subtle px-4 py-3">
                <div>
                  <p className="text-sm font-medium">{h.note || h.reason}</p>
                  <p className="text-xs text-ink-muted">
                    {new Date(h.created_at).toLocaleDateString()}
                  </p>
                </div>
                <span className={`font-semibold ${parseFloat(h.delta) >= 0 ? "text-success" : "text-danger"}`}>
                  {parseFloat(h.delta) >= 0 ? "+" : ""}₹{h.delta}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
