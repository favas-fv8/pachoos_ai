// Payment page — Razorpay checkout, webhook status, and order management.
import { useState, useEffect, useRef } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { motion } from "framer-motion"
import {
  CreditCard,
  Loader2,
  CheckCircle,
  AlertCircle,
  Clock,
  Smartphone,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { api } from "@/lib/api/client"
import { useAppSelector } from "@/store/hooks"

interface PaymentData {
  razorpay_order_id: string
  amount: number
  currency: string
  status: string
  method: string
  payment_id?: string
  signature?: string
}

interface PaymentStatus {
  status: "created" | "authorized" | "captured" | "failed" | "refunded"
  paymentId?: string
  lastChecked?: Date
}

export default function PaymentPage() {
  const navigate = useNavigate()
  const { orderId } = useParams<{ orderId: string }>()
  const user = useAppSelector((state) => state.auth.user)

  const [paymentData, setPaymentData] = useState<PaymentData | null>(null)
  const [paymentStatus, setPaymentStatus] = useState<PaymentStatus>({ status: "created" })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [timeRemaining, setTimeRemaining] = useState(300)

  const pollIntervalRef = useRef<NodeJS.Timeout>()

  useEffect(() => {
    if (!user) {
      navigate("/login")
      return
    }

    initializePayment()

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [orderId, user, navigate])

  useEffect(() => {
    if (paymentStatus.status === "created" && paymentData?.razorpay_order_id) {
      pollPaymentStatus()

      const timer = setInterval(() => {
        setTimeRemaining((prev) => {
          if (prev <= 1) {
            clearInterval(timer)
            return 0
          }
          return prev - 1
        })
      }, 1000)

      return () => clearInterval(timer)
    } else {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [paymentStatus.status, paymentData])

  const initializePayment = async () => {
    setLoading(true)
    setError("")

    try {
      const response = await api.post("/api/v1/payments/razorpay/order/", {
        order_id: orderId,
      })

      if (response.data.id) {
        setPaymentData({
          razorpay_order_id: response.data.id,
          amount: response.data.amount / 100,
          currency: response.data.currency,
          status: response.data.status,
          method: "upi",
        })
      } else {
        setError("Failed to initialize payment. Please try again.")
      }
    } catch (err: any) {
      const msg = err?.response?.data?.error?.message || "Payment initialization failed"
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const pollPaymentStatus = async () => {
    if (!paymentData?.razorpay_order_id) return

    try {
      const response = await api.get(
        `/api/v1/orders/${orderId}/payment/?payment_id=${paymentData.razorpay_order_id}`,
      )

      const updatedStatus = response.data.status as PaymentStatus["status"]
      setPaymentStatus({
        status: updatedStatus,
        paymentId: response.data.razorpay_payment_id,
        lastChecked: new Date(),
      })

      if (updatedStatus === "captured") {
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current)
        }
      } else if (updatedStatus === "failed") {
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current)
        }
        setError("Payment failed. Please try again.")
      }
    } catch (err) {
      console.error("Error polling payment status:", err)
    }
  }

  const handleRazorpayPayment = () => {
    const razorpayKey = process.env.RAZORPAY_KEY_ID || "rzp_test_demo"

    const options = {
      key: razorpayKey,
      amount: paymentData!.amount * 100,
      currency: paymentData!.currency,
      name: "PACHOOS",
      description: `Order ${orderId}`,
      order_id: paymentData!.razorpay_order_id,
      handler: async (response: any) => {
        try {
          await api.post("/api/v1/payments/razorpay/webhook/", {
            event: "payment.captured",
            payload: {
              payment: {
                id: response.razorpay_payment_id,
                amount: response.amount,
                method: response.method,
                order: {
                  id: response.razorpay_order_id,
                },
              },
            },
            signature: response.razorpay_signature,
          })

          setPaymentStatus({
            status: "captured",
            paymentId: response.razorpay_payment_id,
            lastChecked: new Date(),
          })

          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current)
          }
        } catch (err) {
          setError("Payment verification failed. Please contact support.")
        }
      },
      prefill: {
        name: user?.full_name || "",
        email: user?.email || "",
        contact: user?.phone || "",
      },
      notes: {
        order_id: orderId,
        customer_id: user?.id || "",
      },
      theme: {
        color: "#10B981",
      },
    }

    const razorpay = new (window as any).Razorpay(options)

    razorpay.on("payment.failed", async (response: any) => {
      try {
        await api.post("/api/v1/payments/razorpay/webhook/", {
          event: "payment.failed",
          payload: {
            payment: {
              id: response.error.metadata.payment_id,
              order: {
                id: response.error.metadata.order_id,
              },
            },
          },
          signature: response.error.code || "",
        })
      } catch (err) {
        console.error("Error logging payment failure:", err)
      }

      setPaymentStatus({
        status: "failed",
        paymentId: response.error.metadata.payment_id,
        lastChecked: new Date(),
      })
      setError(response.error.description || "Payment failed. Please try again.")
    })

    razorpay.open()
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  return (
    <div className="container-px mx-auto py-8">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        className="mx-auto max-w-2xl"
      >
        <h1 className="font-display text-3xl font-bold">Secure Payment</h1>
        <p className="mt-2 text-ink-muted">Order #{orderId} • {paymentData?.amount.toFixed(2)}</p>

        {error && (
          <div className="mt-4 rounded-xl bg-danger-muted p-4 text-sm text-danger">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5" /> {error}
            </div>
          </div>
        )}

        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <section className="rounded-2xl border border-border bg-surface p-6 shadow-card">
            <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
              <CreditCard className="h-5 w-5 text-primary" /> Payment Details
            </h2>

            <div className="space-y-4">
              <div className="flex items-center justify-between rounded-xl bg-ink-subtle p-4">
                <span className="text-ink-muted">Order Amount</span>
                <span className="font-semibold">₹{paymentData?.amount.toFixed(2)}</span>
              </div>

              <div className="flex items-center justify-between rounded-xl bg-ink-subtle p-4">
                <span className="text-ink-muted">Payment Method</span>
                <Badge variant="outline" className="flex items-center gap-1">
                  <Smartphone className="h-3 w-3" /> UPI
                </Badge>
              </div>

              <div className="flex items-center justify-between rounded-xl bg-ink-subtle p-4">
                <span className="text-ink-muted">Status</span>
                <Badge
                  variant={
                    paymentStatus.status === "captured"
                      ? "success"
                      : paymentStatus.status === "failed"
                        ? "danger"
                        : "warning"
                  }
                  className="flex items-center gap-1"
                >
                  {paymentStatus.status === "created" && <Loader2 className="h-3 w-3 animate-spin" />}
                  {paymentStatus.status === "captured" && <CheckCircle className="h-3 w-3" />}
                  {paymentStatus.status === "failed" && <AlertCircle className="h-3 w-3" />}
                  {paymentStatus.status === "authorized" && <Clock className="h-3 w-3" />}
                  {paymentStatus.status.charAt(0).toUpperCase() + paymentStatus.status.slice(1)}
                </Badge>
              </div>

              {timeRemaining > 0 && paymentStatus.status === "created" && (
                <div className="flex items-center justify-between rounded-xl bg-warning-muted p-4">
                  <span className="text-ink-muted">Time Remaining</span>
                  <span className="font-mono text-warning">00:{formatTime(timeRemaining)}</span>
                </div>
              )}

              {paymentStatus.lastChecked && (
                <div className="text-xs text-ink-muted">
                  Last checked: {paymentStatus.lastChecked.toLocaleTimeString()}
                </div>
              )}
            </div>
          </section>

          <section className="rounded-2xl border border-border bg-surface p-6 shadow-card">
            <h2 className="font-display text-lg font-semibold mb-4">Payment Security</h2>

            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <div className="rounded-full bg-success-muted p-2">
                  <CheckCircle className="h-4 w-4 text-success" />
                </div>
                <span className="text-sm">SSL encrypted payments</span>
              </div>

              <div className="flex items-center gap-3">
                <div className="rounded-full bg-success-muted p-2">
                  <CheckCircle className="h-4 w-4 text-success" />
                </div>
                <span className="text-sm">PCI DSS compliant</span>
              </div>

              <div className="flex items-center gap-3">
                <div className="rounded-full bg-success-muted p-2">
                  <CheckCircle className="h-4 w-4 text-success" />
                </div>
                <span className="text-sm">Razorpay secure gateway</span>
              </div>

              <div className="mt-4 rounded-xl bg-ink-subtle p-3">
                <p className="text-xs text-ink-muted">
                  Your payment information is protected with bank-grade encryption. We never store your card details.
                </p>
              </div>
            </div>
          </section>
        </div>

        <div className="mt-8 flex justify-between">
          <Button
            variant="outline"
            onClick={() => navigate(-1)}
            disabled={loading}
          >
            Back
          </Button>

          {paymentStatus.status === "created" && (
            <Button
              onClick={handleRazorpayPayment}
              disabled={loading}
              className="min-w-[150px]"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Initializing...
                </>
              ) : (
                <>Pay Now - ₹{paymentData?.amount.toFixed(2)}</>
              )}
            </Button>
          )}

          {paymentStatus.status === "captured" && (
            <Button
              variant="outline"
              onClick={() => navigate("/account/orders")}
            >
              View Order
            </Button>
          )}

          {paymentStatus.status === "failed" && (
            <Button
              onClick={initializePayment}
              disabled={loading}
            >
              Try Again
            </Button>
          )}
        </div>
      </motion.div>
    </div>
  )
}