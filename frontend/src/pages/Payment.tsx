// Payment page — supports both Demo Payment (simulated) and Cashfree (real sandbox).
// The confirmers in apps.orders.services are idempotent, so double-clicks and
// page refreshes can never double-charge or double-deduct.
import { useState, useEffect } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { motion } from "framer-motion"
import {
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  Loader2,
  Smartphone,
  CreditCard,
  Wallet,
  RefreshCw,
  ArrowLeft,
  ShieldCheck,
  ExternalLink,
  MapPin,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { BackButton } from "@/components/ui/back-button"
import { Input } from "@/components/ui/input"
import { api, toApiError } from "@/lib/api/client"
import { formatINR } from "@/lib/utils"
import type { PaymentMethod } from "@/types"

const METHODS: { value: PaymentMethod; label: string; icon: typeof Smartphone }[] = [
  { value: "demo_upi", label: "Demo UPI", icon: Smartphone },
  { value: "demo_card", label: "Demo Card", icon: CreditCard },
  { value: "demo_gpay", label: "Demo GPay", icon: Wallet },
  { value: "demo_phonepe", label: "Demo PhonePe", icon: Wallet },
  { value: "demo_paytm", label: "Demo Paytm", icon: Wallet },
  { value: "cod", label: "Cash on Delivery", icon: Wallet },
]

const methodLabel = (m: string): string =>
  METHODS.find((x) => x.value === m)?.label ?? m.replace(/_/g, " ")

// Minimum cashback a customer may put toward an order (mirrors backend rule).
const MIN_CASHBACK_USE = 10

type PageState = "loading" | "pending" | "paid" | "failed"

export default function PaymentPage() {
  const navigate = useNavigate()
  const { orderId } = useParams<{ orderId: string }>()

  const [state, setState] = useState<PageState>("loading")
  const [orderNumber, setOrderNumber] = useState("")
  const [amount, setAmount] = useState(0)
  const [method, setMethod] = useState<PaymentMethod | "">("")
  const [transactionId, setTransactionId] = useState("")
  const [error, setError] = useState("")
  const [selectedMethod, setSelectedMethod] = useState<PaymentMethod>("demo_upi")
  const [submitting, setSubmitting] = useState(false)
  const [cashfreeLoading, setCashfreeLoading] = useState(false)

  // ── Delivery snapshot (server-computed at order placement) ─────────────
  const [distanceKm, setDistanceKm] = useState<number | null>(null)
  const [deliveryCharge, setDeliveryCharge] = useState(0)
  const [deliveryFree, setDeliveryFree] = useState(false)

  // ── Cashback use ───────────────────────────────────────────────────────
  const [cashbackBalance, setCashbackBalance] = useState(0)
  const [useCashback, setUseCashback] = useState(false)
  const [cashbackMode, setCashbackMode] = useState<"full" | "custom">("full")
  const [customCashback, setCustomCashback] = useState("")

  useEffect(() => {
    if (!orderId) return
    let cancelled = false

    api
      .get(`/api/v1/payments/order/${orderId}/status/`)
      .then((res) => {
        if (cancelled) return
        setOrderNumber(res.data.order_number)
        setAmount(Number(res.data.amount))
        setMethod(res.data.payment_method || "")
        setTransactionId(res.data.transaction_id || "")
        setDistanceKm(res.data.distance_km != null ? Number(res.data.distance_km) : null)
        setDeliveryCharge(Number(res.data.delivery_charge) || 0)
        setDeliveryFree(Boolean(res.data.delivery_free))
        if (res.data.payment_status === "paid") {
          setState("paid")
        } else if (res.data.payment_status === "failed") {
          setState("failed")
        } else {
          setState("pending")
        }
      })
      .catch((err) => {
        if (cancelled) return
        setError(toApiError(err).message)
        setState("failed")
      })

    // Balance is non-critical — never block the page on it.
    api
      .get("/api/v1/wallet/balance/")
      .then((res) => {
        if (cancelled) return
        setCashbackBalance(Number(res.data.cashback_balance) || 0)
      })
      .catch(() => {})

    return () => {
      cancelled = true
    }
  }, [orderId])

  // ── Cashback rules (display only — the backend re-validates everything) ─
  const maxUsableCashback = Math.max(0, Math.min(cashbackBalance, amount - 1))
  // Below ₹10 the cashback-use option is hidden entirely.
  const cashbackEligible = state === "pending" && cashbackBalance >= MIN_CASHBACK_USE
  const parsedCustomCashback = Number(customCashback)
  const customCashbackValid =
    !useCashback ||
    cashbackMode === "full" ||
    (customCashback.trim() !== "" &&
      Number.isFinite(parsedCustomCashback) &&
      parsedCustomCashback >= MIN_CASHBACK_USE &&
      parsedCustomCashback <= maxUsableCashback)
  const appliedCashback =
    useCashback && cashbackEligible && customCashbackValid
      ? cashbackMode === "full"
        ? maxUsableCashback
        : Math.min(parsedCustomCashback, maxUsableCashback)
      : 0
  const finalAmount = Math.max(0, Number((amount - appliedCashback).toFixed(2)))

  // ── Delivery summary (distance computed server-side at order time) ─────
  const deliverySummary = (
    <div className="rounded-xl border border-border bg-ink-subtle p-4 text-sm">
      {distanceKm == null ? (
        <div className="flex items-start gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
          <p className="text-xs text-ink">
            Delivery distance could not be determined (delivery location missing), so
            the standard delivery charge of {formatINR(deliveryCharge)} applies.
          </p>
        </div>
      ) : (
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-2 text-ink-muted">
            <MapPin className="h-4 w-4 shrink-0 text-primary" />
            {distanceKm} km from the store
          </span>
          {deliveryFree ? (
            <span className="font-semibold text-success">Free Delivery</span>
          ) : (
            <span className="text-ink">Delivery Charge: {formatINR(deliveryCharge)}</span>
          )}
        </div>
      )}
    </div>
  )

  // ── Demo payment confirmation ──────────────────────────────────────────
  const confirmDemo = async (simulate: "success" | "fail") => {
    if (!orderId || submitting) return
    setSubmitting(true)
    setError("")
    try {
      const res = await api.post("/api/v1/payments/demo/confirm/", {
        order_id: orderId,
        method: selectedMethod,
        simulate,
      })
      if (res.data.success) {
        setOrderNumber(res.data.order.order_number)
        setAmount(Number(res.data.order.grand_total))
        setMethod(res.data.payment?.method ?? selectedMethod)
        setTransactionId(res.data.payment?.transaction_id ?? res.data.transaction_id)
        setState("paid")
      } else {
        setMethod(selectedMethod)
        setError(res.data.message || "Payment failed. Please try again.")
        setState("failed")
      }
    } catch (err) {
      const apiErr = toApiError(err)
      setError(apiErr.message)
      setState("failed")
    } finally {
      setSubmitting(false)
    }
  }

  // ── Cashfree payment initiation ────────────────────────────────────────
  const handleCashfreePayment = async () => {
    if (!orderId || cashfreeLoading) return
    setCashfreeLoading(true)
    setError("")
    try {
      const res = await api.post("/api/v1/payments/cashfree/order/", {
        order_id: orderId,
        ...(appliedCashback > 0 ? { use_cashback: appliedCashback } : {}),
      })
      const { payment_session_id } = res.data

      if (!payment_session_id) {
        throw new Error("Failed to get payment session from Cashfree.")
      }

      // Load Cashfree SDK and redirect to checkout
      loadCashfreeSDK(payment_session_id)
    } catch (err) {
      const apiErr = toApiError(err)
      setError(apiErr.message)
      setCashfreeLoading(false)
    }
  }

  const loadCashfreeSDK = (paymentSessionId: string) => {
    // Check if SDK is already loaded
    if (typeof window !== "undefined" && (window as any).Cashfree) {
      initCashfreeCheckout(paymentSessionId)
      return
    }

    const script = document.createElement("script")
    script.src = "https://sdk.cashfree.com/js/v3/cashfree.js"
    script.onload = () => initCashfreeCheckout(paymentSessionId)
    script.onerror = () => {
      setError("Failed to load Cashfree payment SDK. Please try again.")
      setCashfreeLoading(false)
    }
    document.head.appendChild(script)
  }

  const initCashfreeCheckout = (paymentSessionId: string) => {
    try {
      const Cashfree = (window as any).Cashfree({
        mode: "sandbox", // Change to "production" for live
      })

      Cashfree.checkout({
        paymentSessionId: paymentSessionId,
        redirectTarget: "_self",
      })
        .then((result: any) => {
          if (result?.error) {
            setError(result.error.message || "Payment checkout failed. Please try again.")
          }
          setCashfreeLoading(false)
        })
        .catch(() => {
          setError("Failed to initialize Cashfree checkout. Please try again.")
          setCashfreeLoading(false)
        })
    } catch {
      setError("Failed to initialize Cashfree checkout. Please try again.")
      setCashfreeLoading(false)
    }
  }

  if (state === "loading") {
    return (
      <div className="container-px mx-auto py-8">
        <BackButton to={orderId ? `/track/${orderId}` : "/account/orders"} />
        <div className="flex justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </div>
    )
  }

  return (
    <div className="container-px mx-auto py-8">
      <BackButton to={orderId ? `/track/${orderId}` : "/account/orders"} />
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        className="mx-auto max-w-2xl"
      >
        <h1 className="font-display text-3xl font-bold">Payment</h1>
        <p className="mt-2 text-ink-muted">Order {orderNumber || orderId}</p>

        <div className="mt-4 flex items-center gap-2 rounded-xl bg-ink-subtle p-3 text-xs text-ink-muted">
          <ShieldCheck className="h-4 w-4 shrink-0 text-warning" />
          Cashfree Sandbox — test payments only. No real money is charged.
        </div>

        {/* ── SUCCESS ─────────────────────────────────────────────────────── */}
        {state === "paid" && (
          <div className="mt-6 rounded-2xl border border-border bg-surface p-8 text-center shadow-card">
            <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-full bg-success/10">
              <CheckCircle className="h-10 w-10 text-success" />
            </div>
            <h2 className="font-display text-2xl font-bold">Payment Successful</h2>
            <p className="mt-1 text-sm text-ink-muted">
              Your order has been confirmed. A confirmation has been added to your account.
            </p>

            <div className="mx-auto mt-6 max-w-sm space-y-2 rounded-xl bg-ink-subtle p-4 text-left text-sm">
              <div className="flex justify-between">
                <span className="text-ink-muted">Order</span>
                <span className="font-medium">{orderNumber}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-muted">Amount paid</span>
                <span className="font-semibold">{formatINR(amount)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-muted">Method</span>
                <Badge variant="outline">{methodLabel(method)}</Badge>
              </div>
              {transactionId && (
                <div className="flex justify-between">
                  <span className="text-ink-muted">Transaction ID</span>
                  <span className="font-mono text-xs">{transactionId}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-ink-muted">Delivery</span>
                {deliveryFree ? (
                  <span className="font-medium text-success">Free Delivery</span>
                ) : (
                  <span>{formatINR(deliveryCharge)}</span>
                )}
              </div>
              {distanceKm != null && (
                <div className="flex justify-between">
                  <span className="text-ink-muted">Distance</span>
                  <span>{distanceKm} km from the store</span>
                </div>
              )}
            </div>

            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <Button onClick={() => navigate(`/track/${orderId}`)}>
                View Order
              </Button>
              <Button variant="outline" onClick={() => navigate("/account/orders")}>
                My Orders
              </Button>
            </div>
          </div>
        )}

        {/* ── FAILED ──────────────────────────────────────────────────────── */}
        {state === "failed" && (
          <div className="mt-6 rounded-2xl border border-border bg-surface p-8 text-center shadow-card">
            <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-full bg-danger/10">
              <AlertCircle className="h-10 w-10 text-danger" />
            </div>
            <h2 className="font-display text-2xl font-bold">Payment Failed</h2>
            <p className="mt-1 text-sm text-ink-muted">
              {error || "The payment could not be completed. No money was charged."}
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <Button onClick={() => setState("pending")}>
                <RefreshCw className="mr-2 h-4 w-4" /> Try again
              </Button>
              <Button variant="outline" onClick={() => navigate(-1)}>
                <ArrowLeft className="mr-2 h-4 w-4" /> Back
              </Button>
            </div>
          </div>
        )}

        {/* ── PENDING (choose method + pay) ───────────────────────────────── */}
        {state === "pending" && (
          <div className="mt-6 rounded-2xl border border-border bg-surface p-6 shadow-card">
            {/* ── Cashfree Primary Option ─────────────────────────────────── */}
            <h2 className="font-display text-lg font-semibold mb-4">
              Complete Payment
            </h2>

            {/* ── Delivery distance & charge (server-computed) ───────────── */}
            <div className="mb-4">{deliverySummary}</div>

            {/* ── Use cashback (optional — hidden below ₹10 balance) ─────── */}
            {cashbackEligible && (
              <div className="mb-4 rounded-xl border border-border bg-ink-subtle p-4">
                <label className="flex cursor-pointer items-center gap-3">
                  <input
                    type="checkbox"
                    checked={useCashback}
                    onChange={(e) => {
                      setUseCashback(e.target.checked)
                      setError("")
                    }}
                    className="accent-primary"
                  />
                  <span className="text-sm font-medium">Use Cashback Balance</span>
                  <span className="ml-auto text-sm font-semibold text-success">
                    {formatINR(cashbackBalance)}
                  </span>
                </label>

                {useCashback && (
                  <>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {(["full", "custom"] as const).map((mode) => (
                        <button
                          key={mode}
                          type="button"
                          onClick={() => setCashbackMode(mode)}
                          className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                            cashbackMode === mode
                              ? "bg-primary text-primary-foreground"
                              : "border border-border bg-surface text-ink-muted hover:bg-surface-muted"
                          }`}
                        >
                          {mode === "full"
                            ? `Full balance (${formatINR(maxUsableCashback)})`
                            : "Custom amount"}
                        </button>
                      ))}
                    </div>

                    {cashbackMode === "custom" && (
                      <div className="mt-3 max-w-xs">
                        <Input
                          type="number"
                          min={MIN_CASHBACK_USE}
                          max={maxUsableCashback}
                          step="0.01"
                          placeholder={`Min ${formatINR(MIN_CASHBACK_USE)}, max ${formatINR(maxUsableCashback)}`}
                          value={customCashback}
                          onChange={(e) => setCustomCashback(e.target.value)}
                        />
                        {customCashback.trim() !== "" && !customCashbackValid && (
                          <p className="mt-1 text-xs text-danger">
                            Enter between {formatINR(MIN_CASHBACK_USE)} and{" "}
                            {formatINR(maxUsableCashback)}.
                          </p>
                        )}
                      </div>
                    )}

                    {appliedCashback > 0 && (
                      <p className="mt-3 text-xs text-success">
                        −{formatINR(appliedCashback)} cashback will be deducted from your
                        wallet only after successful payment.
                      </p>
                    )}
                  </>
                )}
              </div>
            )}

            <button
              type="button"
              disabled={cashfreeLoading || (useCashback && !customCashbackValid)}
              onClick={handleCashfreePayment}
              className="mb-4 flex w-full items-center justify-center gap-3 rounded-xl border-2 border-primary bg-primary/5 px-6 py-4 text-sm font-semibold transition-colors hover:bg-primary/10 disabled:opacity-50"
            >
              {cashfreeLoading ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" /> Redirecting to Cashfree…
                </>
              ) : (
                <>
                  <ShieldCheck className="h-5 w-5" />
                  Pay {formatINR(finalAmount)} with Cashfree
                  <ExternalLink className="h-4 w-4 text-ink-muted" />
                </>
              )}
            </button>

            {appliedCashback > 0 && (
              <p className="-mt-2 mb-4 text-center text-xs text-ink-muted">
                Original payable {formatINR(amount)} − cashback {formatINR(appliedCashback)}
              </p>
            )}

            <p className="mb-4 text-center text-xs text-ink-muted">
              UPI, Cards, Net Banking, Wallets — powered by Cashfree Sandbox
            </p>

            {/* ── Demo payment fallback ──────────────────────────────────── */}
            <div className="border-t border-border pt-4">
              <details className="group">
                <summary className="cursor-pointer text-xs text-ink-muted hover:text-ink transition-colors">
                  Or use Demo Payment (simulated, no real gateway)
                </summary>

                <div className="mt-3 space-y-2">
                  {METHODS.map((m) => {
                    const Icon = m.icon
                    return (
                      <label
                        key={m.value}
                        className="flex cursor-pointer items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3 text-sm transition-colors has-[:checked]:border-primary has-[:checked]:bg-primary/5"
                      >
                        <input
                          type="radio"
                          name="method"
                          value={m.value}
                          checked={selectedMethod === m.value}
                          onChange={(e) => setSelectedMethod(e.target.value as PaymentMethod)}
                          className="accent-primary"
                        />
                        <Icon className="h-4 w-4 text-ink-muted" />
                        <span>{m.label}</span>
                        {m.value === "cod" ? (
                          <span className="ml-auto text-xs text-ink-muted">Pay at delivery</span>
                        ) : (
                          <span className="ml-auto text-xs text-ink-muted">Simulated</span>
                        )}
                      </label>
                    )
                  })}
                </div>

                <div className="mt-4 flex items-center justify-between gap-4">
                  <Button variant="outline" onClick={() => navigate(-1)} disabled={submitting}>
                    Back
                  </Button>
                  <Button
                    size="lg"
                    disabled={submitting}
                    onClick={() => void confirmDemo("success")}
                    className="min-w-[180px]"
                  >
                    {submitting ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Processing…
                      </>
                    ) : (
                      <>
                        Pay {formatINR(amount)} (Demo)
                      </>
                    )}
                  </Button>
                </div>

                <div className="mt-4 text-center">
                  <button
                    type="button"
                    disabled={submitting}
                    onClick={() => void confirmDemo("fail")}
                    className="text-xs text-ink-muted underline-offset-2 hover:underline disabled:opacity-50"
                  >
                    Simulate a failed payment (demo)
                  </button>
                </div>
              </details>
            </div>

            {error && (
              <div className="mt-4 rounded-xl bg-danger-muted p-3 text-sm text-danger">{error}</div>
            )}
          </div>
        )}
      </motion.div>
    </div>
  )
}
