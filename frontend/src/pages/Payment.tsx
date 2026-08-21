// Payment page — supports both Demo Payment (simulated) and Cashfree (real sandbox).
// The confirmers in apps.orders.services are idempotent, so double-clicks and
// page refreshes can never double-charge or double-deduct.
import { useState, useEffect } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { motion } from "framer-motion"
import {
  CheckCircle,
  AlertCircle,
  Loader2,
  Smartphone,
  CreditCard,
  Wallet,
  RefreshCw,
  ArrowLeft,
  ShieldCheck,
  ExternalLink,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { BackButton } from "@/components/ui/back-button"
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

    return () => {
      cancelled = true
    }
  }, [orderId])

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

            <button
              type="button"
              disabled={cashfreeLoading}
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
                  Pay {formatINR(amount)} with Cashfree
                  <ExternalLink className="h-4 w-4 text-ink-muted" />
                </>
              )}
            </button>

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
