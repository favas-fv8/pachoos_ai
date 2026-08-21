// Payment result page — shown after Cashfree checkout redirect.
// Reads order_id from query params, verifies payment with backend,
// and shows success/failure/pending status.
import { useState, useEffect } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { motion } from "framer-motion"
import {
  CheckCircle,
  AlertCircle,
  Clock,
  Loader2,
  ArrowLeft,
  RefreshCw,
  XCircle,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { BackButton } from "@/components/ui/back-button"
import { api, toApiError } from "@/lib/api/client"
import { formatINR } from "@/lib/utils"

type PageState = "verifying" | "paid" | "failed" | "dropped" | "pending" | "no-order"

export default function PaymentResultPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const [state, setState] = useState<PageState>("verifying")
  const [orderNumber, setOrderNumber] = useState("")
  const [orderId, setOrderId] = useState("")
  const [amount, setAmount] = useState(0)
  const [transactionId, setTransactionId] = useState("")
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")

  useEffect(() => {
    const orderIdParam = searchParams.get("order_id")
    if (!orderIdParam) {
      setState("no-order")
      return
    }
    setOrderId(orderIdParam)

    let cancelled = false
    let retries = 0
    const maxRetries = 5
    const retryDelay = 2000

    const verifyPayment = async () => {
      try {
        const res = await api.get(
          `/api/v1/payments/cashfree/verify/?order_id=${orderIdParam}`
        )
        if (cancelled) return

        setOrderNumber(res.data.order_number || "")
        setAmount(Number(res.data.amount) || 0)
        setTransactionId(res.data.transaction_id || "")

        if (res.data.paid) {
          setState("paid")
          setMessage(res.data.message || "Payment successful.")
        } else if (res.data.cf_payment_status === "USER_DROPPED") {
          setState("dropped")
          setMessage(res.data.message || "Payment was cancelled.")
        } else if (
          // Fresh Cashfree statuses are authoritative and must be checked
          // BEFORE the persisted Django payment_status, which can be a stale
          // "failed" left over from a previous attempt after Try Again.
          res.data.cf_order_status === "EXPIRED" ||
          res.data.cf_order_status === "TERMINATED" ||
          res.data.cf_payment_status === "FAILED" ||
          res.data.cf_payment_status === "CANCELLED" ||
          res.data.cf_payment_status === "VOID"
        ) {
          setState("failed")
          setMessage(res.data.message || "Payment was not completed.")
        } else if (res.data.cf_payment_status === "PENDING") {
          // Cashfree confirms payment is still processing — show pending UI immediately
          setState("pending")
          setMessage(
            res.data.message ||
              "Payment is still processing. Please wait or check back later."
          )
        } else if (retries < maxRetries) {
          // Genuinely indeterminate — retry after delay
          retries++
          setTimeout(verifyPayment, retryDelay)
        } else if (res.data.payment_status === "failed") {
          // Last resort only — reached when Cashfree returned no definitive
          // status after all retries. Never overrides a fresh Cashfree status.
          setState("failed")
          setMessage(res.data.message || "Payment was not completed.")
        } else {
          // Max retries reached — show pending
          setState("pending")
          setMessage(
            res.data.message ||
              "Payment is still being processed. Please check your order history."
          )
        }
      } catch (err) {
        if (cancelled) return
        const apiErr = toApiError(err)
        setError(apiErr.message)
        setState("failed")
      }
    }

    verifyPayment()

    return () => {
      cancelled = true
    }
  }, [searchParams])

  // Back returns to the previous in-app screen (e.g. the payment page);
  // when the page was landed on directly (Cashfree redirect), fall back to
  // the payment retry page for this order, or the orders list.
  const backTo = orderId ? `/payment/${orderId}` : "/account/orders"

  if (state === "verifying") {
    return (
      <div className="container-px mx-auto py-8">
        <BackButton to={backTo} />
        <div className="flex flex-col items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="mt-4 text-sm text-ink-muted">
            Verifying your payment...
          </p>
        </div>
      </div>
    )
  }

  if (state === "no-order") {
    return (
      <div className="container-px mx-auto py-8">
        <BackButton to={backTo} />
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="mx-auto max-w-2xl text-center"
        >
          <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-full bg-danger/10">
            <AlertCircle className="h-10 w-10 text-danger" />
          </div>
          <h1 className="font-display text-2xl font-bold">
            No Order Found
          </h1>
          <p className="mt-2 text-sm text-ink-muted">
            No order ID was provided. Please try again from your orders.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Button onClick={() => navigate("/account/orders")}>
              My Orders
            </Button>
            <Button variant="outline" onClick={() => navigate("/")}>
              <ArrowLeft className="mr-2 h-4 w-4" /> Home
            </Button>
          </div>
        </motion.div>
      </div>
    )
  }

  return (
    <div className="container-px mx-auto py-8">
      <BackButton to={backTo} />
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        className="mx-auto max-w-2xl"
      >
        {/* ── SUCCESS ─────────────────────────────────────────────────────── */}
        {state === "paid" && (
          <div className="rounded-2xl border border-border bg-surface p-8 text-center shadow-card">
            <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-full bg-success/10">
              <CheckCircle className="h-10 w-10 text-success" />
            </div>
            <h1 className="font-display text-2xl font-bold">
              Payment Successful
            </h1>
            <p className="mt-1 text-sm text-ink-muted">
              Your order has been confirmed. A confirmation has been added to
              your account.
            </p>

            <div className="mx-auto mt-6 max-w-sm space-y-2 rounded-xl bg-ink-subtle p-4 text-left text-sm">
              {orderNumber && (
                <div className="flex justify-between">
                  <span className="text-ink-muted">Order</span>
                  <span className="font-medium">{orderNumber}</span>
                </div>
              )}
              {amount > 0 && (
                <div className="flex justify-between">
                  <span className="text-ink-muted">Amount paid</span>
                  <span className="font-semibold">{formatINR(amount)}</span>
                </div>
              )}
              {transactionId && (
                <div className="flex justify-between">
                  <span className="text-ink-muted">Transaction ID</span>
                  <span className="font-mono text-xs">{transactionId}</span>
                </div>
              )}
            </div>

            <div className="mt-6 flex flex-wrap justify-center gap-3">
              {orderId && (
                <Button onClick={() => navigate(`/track/${orderId}`)}>
                  View Order
                </Button>
              )}
              <Button
                variant="outline"
                onClick={() => navigate("/account/orders")}
              >
                My Orders
              </Button>
            </div>
          </div>
        )}

        {/* ── FAILED ──────────────────────────────────────────────────────── */}
        {state === "failed" && (
          <div className="rounded-2xl border border-border bg-surface p-8 text-center shadow-card">
            <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-full bg-danger/10">
              <AlertCircle className="h-10 w-10 text-danger" />
            </div>
            <h1 className="font-display text-2xl font-bold">
              Payment Failed
            </h1>
            <p className="mt-1 text-sm text-ink-muted">
              {error || message || "The payment could not be completed. No money was charged."}
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              {orderId && (
                <Button onClick={() => navigate(`/payment/${orderId}`)}>
                  <RefreshCw className="mr-2 h-4 w-4" /> Try again
                </Button>
              )}
              <Button variant="outline" onClick={() => navigate("/account/orders")}>
                My Orders
              </Button>
            </div>
          </div>
        )}

        {/* ── DROPPED / CANCELLED ────────────────────────────────────────── */}
        {state === "dropped" && (
          <div className="rounded-2xl border border-border bg-surface p-8 text-center shadow-card">
            <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-full bg-warning/10">
              <XCircle className="h-10 w-10 text-warning" />
            </div>
            <h1 className="font-display text-2xl font-bold">
              Payment Cancelled
            </h1>
            <p className="mt-1 text-sm text-ink-muted">
              {message || "You cancelled the payment. No money was charged."}
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              {orderId && (
                <Button onClick={() => navigate(`/payment/${orderId}`)}>
                  <RefreshCw className="mr-2 h-4 w-4" /> Try again
                </Button>
              )}
              <Button variant="outline" onClick={() => navigate("/account/orders")}>
                My Orders
              </Button>
            </div>
          </div>
        )}

        {/* ── PENDING ─────────────────────────────────────────────────────── */}
        {state === "pending" && (
          <div className="rounded-2xl border border-border bg-surface p-8 text-center shadow-card">
            <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-full bg-warning/10">
              <Clock className="h-8 w-8 text-warning" />
            </div>
            <h1 className="font-display text-2xl font-bold">
              Payment Processing
            </h1>
            <p className="mt-1 text-sm text-ink-muted">
              {message ||
                "Your payment is still being processed. Please check your order history."}
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              {orderId && (
                <Button onClick={() => navigate(`/track/${orderId}`)}>
                  View Order
                </Button>
              )}
              <Button
                variant="outline"
                onClick={() => navigate("/account/orders")}
              >
                My Orders
              </Button>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  )
}
