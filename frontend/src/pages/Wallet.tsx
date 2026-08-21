// Wallet page — cashback balance, redemption, and history.
import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import { BackButton } from "@/components/ui/back-button"
import {
  Wallet,
  Clock,
  AlertCircle,
  Loader2,
  HandCoins,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api, toApiError } from "@/lib/api/client"

const MIN_REDEEM = 10

interface WalletBalance {
  cashback_balance: string
  debt_balance: string
  active_vouchers: number
  total_cashback_earned: string
  cashback_redeemed: string
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
  const [history, setHistory] = useState<LedgerEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const [redeemMode, setRedeemMode] = useState<"full" | "custom">("full")
  const [customAmount, setCustomAmount] = useState("")
  const [redeemLoading, setRedeemLoading] = useState(false)
  const [redeemMsg, setRedeemMsg] = useState("")
  const [redeemError, setRedeemError] = useState("")

  useEffect(() => {
    fetchWalletData()
  }, [])

  const fetchWalletData = async () => {
    setLoading(true)
    setError("")
    try {
      const [balRes, historyRes] = await Promise.all([
        api.get("/api/v1/wallet/balance/"),
        api.get("/api/v1/wallet/history/"),
      ])
      setBalance(balRes.data)
      setHistory(historyRes.data)
    } catch {
      setError("Failed to load wallet data.")
    } finally {
      setLoading(false)
    }
  }

  const cashbackBalance = Number(balance?.cashback_balance ?? 0)
  const eligible = cashbackBalance >= MIN_REDEEM
  const parsedCustom = Number(customAmount)
  const customValid =
    redeemMode === "full" ||
    (customAmount.trim() !== "" &&
      Number.isFinite(parsedCustom) &&
      parsedCustom >= MIN_REDEEM &&
      parsedCustom <= cashbackBalance)

  // Redemption entries (manual redemptions + legacy voucher mints) all read
  // "Redeemed Cashback" with the actual redeemed amount.
  const historyTitle = (entry: LedgerEntry) =>
    entry.reason === "cashback_redeemed" || entry.reason === "voucher_mint"
      ? "Redeemed Cashback"
      : entry.note || entry.reason

  const handleRedeemCashback = async () => {
    if (!eligible || !customValid || redeemLoading) return
    setRedeemLoading(true)
    setRedeemMsg("")
    setRedeemError("")
    try {
      const payload =
        redeemMode === "full" ? {} : { amount: parsedCustom }
      const res = await api.post("/api/v1/wallet/cashback/redeem/", payload)
      setRedeemMsg(res.data.message)
      setCustomAmount("")
      await fetchWalletData()
    } catch (err) {
      setRedeemError(
        toApiError(err).message || "Redemption failed. Please try again.",
      )
    } finally {
      setRedeemLoading(false)
    }
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
              <HandCoins className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-ink-muted">Cashback Redeemed</p>
              <p className="text-2xl font-bold">₹{balance?.cashback_redeemed || "0.00"}</p>
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
              <Clock className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-ink-muted">Total Earned</p>
              <p className="text-2xl font-bold">₹{balance?.total_cashback_earned || "0.00"}</p>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Redeem Cashback */}
      <section className="mt-6 rounded-2xl border border-border bg-surface p-6 shadow-card">
        <h2 className="font-display text-lg font-semibold mb-3 flex items-center gap-2">
          <HandCoins className="h-5 w-5 text-primary" /> Redeem Cashback
        </h2>

        {!eligible ? (
          <p className="text-sm text-ink-muted mb-3">
            You need at least ₹{MIN_REDEEM} cashback to redeem. Keep earning!
          </p>
        ) : (
          <div className="mb-3 flex flex-wrap gap-2">
            {(["full", "custom"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => {
                  setRedeemMode(mode)
                  setRedeemMsg("")
                  setRedeemError("")
                }}
                className={`rounded-full px-4 py-1.5 text-xs font-medium transition-colors ${
                  redeemMode === mode
                    ? "bg-primary text-primary-foreground"
                    : "border border-border bg-surface text-ink-muted hover:bg-surface-muted"
                }`}
              >
                {mode === "full" ? `Full balance (₹${balance?.cashback_balance})` : "Custom amount"}
              </button>
            ))}
          </div>
        )}

        {eligible && redeemMode === "custom" && (
          <div className="mb-3 max-w-xs">
            <Input
              type="number"
              min={MIN_REDEEM}
              max={cashbackBalance}
              step="0.01"
              placeholder={`Min ₹${MIN_REDEEM}, max ₹${balance?.cashback_balance}`}
              value={customAmount}
              onChange={(e) => {
                setCustomAmount(e.target.value)
                setRedeemMsg("")
                setRedeemError("")
              }}
            />
            {customAmount.trim() !== "" && !customValid && (
              <p className="mt-1 text-xs text-danger">
                Enter between ₹{MIN_REDEEM} and ₹{balance?.cashback_balance}.
              </p>
            )}
          </div>
        )}

        <Button
          onClick={handleRedeemCashback}
          disabled={!eligible || !customValid || redeemLoading}
          className="w-full sm:w-auto"
        >
          {redeemLoading ? (
            <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Redeeming...</>
          ) : (
            "Redeem Cashback"
          )}
        </Button>

        {redeemMsg && <p className="mt-2 text-sm text-success">{redeemMsg}</p>}
        {redeemError && <p className="mt-2 text-sm text-danger">{redeemError}</p>}
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
                  <p className="text-sm font-medium">{historyTitle(h)}</p>
                  <p className="text-xs text-ink-muted">
                    {new Date(h.created_at).toLocaleDateString()}
                  </p>
                </div>
                <span className={`font-semibold ${parseFloat(h.delta) >= 0 ? "text-success" : "text-danger"}`}>
                  {parseFloat(h.delta) >= 0 ? "+" : "−"}₹{Math.abs(parseFloat(h.delta)).toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
