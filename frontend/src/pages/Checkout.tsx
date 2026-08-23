import { useState, useEffect, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { MapPin, CreditCard, Tag, ArrowRight, Loader2, AlertTriangle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api, toApiError } from "@/lib/api/client"
import { useAppDispatch, useAppSelector } from "@/store/hooks"
import { pushToast } from "@/store/slices/uiSlice"
import { formatINR } from "@/lib/utils"
import type { CartSummary } from "@/types"

const PAYMENT_METHODS = [
  { value: "demo_upi", label: "Demo UPI" },
  { value: "demo_card", label: "Demo Card" },
  { value: "demo_gpay", label: "Demo GPay" },
  { value: "demo_phonepe", label: "Demo PhonePe" },
  { value: "demo_paytm", label: "Demo Paytm" },
  { value: "cod", label: "Cash on Delivery" },
]

export default function Checkout() {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const deliveryAddress = useAppSelector((s) => s.ui.deliveryAddress)
  const [summary, setSummary] = useState<CartSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [addressId, setAddressId] = useState("")
  const [couponCode, setCouponCode] = useState("")
  const [voucherCode, setVoucherCode] = useState("")
  const [paymentMethod, setPaymentMethod] = useState("demo_upi")
  const [placing, setPlacing] = useState(false)

  const loadSummary = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const cartRes = await api.get("/api/v1/cart/carts/current/")
      const params = new URLSearchParams()
      if (couponCode.trim()) params.set("coupon_code", couponCode.trim())
      if (voucherCode.trim()) params.set("voucher_code", voucherCode.trim())
      // The backend computes the delivery distance from these coordinates —
      // never send a distance value.
      if (deliveryAddress) {
        params.set("customer_lat", String(deliveryAddress.lat))
        params.set("customer_lon", String(deliveryAddress.lon))
      }
      const summaryRes = await api.get(`/api/v1/cart/carts/${cartRes.data.id}/summary/?${params.toString()}`)
      setSummary(summaryRes.data)
    } catch (err) {
      const apiErr = toApiError(err)
      setError(apiErr.message)
      setSummary((prev) => prev)
    } finally {
      setLoading(false)
    }
  }, [couponCode, voucherCode, deliveryAddress])

  useEffect(() => {
    void loadSummary()
  }, [loadSummary])

  const handlePlaceOrder = async () => {
    setPlacing(true)
    setError("")
    try {
      const res = await api.post("/api/v1/orders/", {
        delivery_address_id: addressId ? parseInt(addressId, 10) : 1,
        ...(deliveryAddress
          ? { customer_lat: deliveryAddress.lat, customer_lon: deliveryAddress.lon }
          : {}),
        coupon_code: couponCode.trim() || undefined,
        voucher_code: voucherCode.trim() || undefined,
        payment_method: paymentMethod,
      })
      dispatch(pushToast({ message: "Order placed! Choose your payment method.", variant: "success" }))
      navigate(`/payment/${res.data.id}`)
    } catch (err) {
      const apiErr = toApiError(err)
      setError(apiErr.message)
      dispatch(pushToast({ message: apiErr.message, variant: "error" }))
    } finally {
      setPlacing(false)
    }
  }

  if (loading) {
    return (
      <div className="container-px mx-auto py-8">
        <h1 className="font-display text-3xl font-bold">Checkout</h1>
        <div className="flex justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </div>
    )
  }

  if (!summary || summary.items.length === 0) {
    return (
      <div className="container-px mx-auto py-8">
        <h1 className="font-display text-3xl font-bold">Checkout</h1>
        <div className="mt-6 rounded-2xl border border-border bg-surface p-10 text-center text-ink-muted">
          <AlertTriangle className="mx-auto mb-3 h-10 w-10 opacity-40" />
          <p>Your cart is empty.</p>
          <Button onClick={() => navigate("/shop")} className="mt-4">Go shopping</Button>
        </div>
      </div>
    )
  }

  return (
    <div className="container-px mx-auto py-8">
      <h1 className="font-display text-3xl font-bold">Checkout</h1>

      {error && (
        <div className="mt-4 rounded-xl bg-danger-muted p-3 text-sm text-danger">
          {error}
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {/* Delivery */}
        <section className="rounded-2xl border border-border bg-surface p-6 shadow-card">
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <MapPin className="h-5 w-5 text-primary" /> Delivery
          </h2>
          <div className="space-y-3">
            <Input
              placeholder="Address ID (for demo)"
              value={addressId}
              onChange={(e) => setAddressId(e.target.value)}
            />
            {deliveryAddress ? (
              <div className="rounded-xl border border-border bg-surface-muted/60 p-3 text-sm">
                <p className="font-medium text-ink">{deliveryAddress.label}</p>
                {summary?.distance_km != null && (
                  <p className="mt-0.5 text-xs text-ink-muted">
                    {summary.distance_km} km from the store ·{" "}
                    {summary.delivery_free ? "Free Delivery" : `Delivery charge ${formatINR(summary.delivery_charge)}`}
                  </p>
                )}
              </div>
            ) : (
              <div className="flex items-start gap-2 rounded-xl border border-warning/40 bg-warning/10 p-3 text-xs text-ink">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                No delivery location set. Use “Deliver to” in the header — without it we
                cannot calculate the distance and the standard delivery charge applies.
              </div>
            )}
            <p className="text-xs text-ink-muted">
              Free delivery within 2 km of the store. Beyond 2 km: ₹40 delivery charge.
            </p>
          </div>
        </section>

        {/* Payment */}
        <section className="rounded-2xl border border-border bg-surface p-6 shadow-card">
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <CreditCard className="h-5 w-5 text-primary" /> Payment Method
          </h2>
          <div className="space-y-2">
            {PAYMENT_METHODS.map((m) => (
              <label
                key={m.value}
                className="flex cursor-pointer items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3 text-sm transition-colors has-[:checked]:border-primary has-[:checked]:bg-primary/5"
              >
                <input
                  type="radio"
                  name="paymentMethod"
                  value={m.value}
                  checked={paymentMethod === m.value}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                  className="accent-primary"
                />
                <span>{m.label}</span>
                {m.value === "cod" ? (
                  <span className="ml-auto text-xs text-ink-muted">Pay at delivery</span>
                ) : (
                  <span className="ml-auto text-xs text-ink-muted">Simulated</span>
                )}
              </label>
            ))}
          </div>
          <p className="mt-3 rounded-lg bg-ink-subtle p-3 text-xs text-ink-muted">
            Demo Payment — no real money is charged. This is a simulation until a real
            payment gateway is connected.
          </p>
        </section>

        {/* Discounts */}
        <section className="rounded-2xl border border-border bg-surface p-6 shadow-card">
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <Tag className="h-5 w-5 text-primary" /> Discounts
          </h2>
          <div className="space-y-3">
            <Input
              placeholder="Coupon code"
              value={couponCode}
              onChange={(e) => setCouponCode(e.target.value)}
            />
            <Input
              placeholder="Voucher code"
              value={voucherCode}
              onChange={(e) => setVoucherCode(e.target.value)}
            />
            <p className="text-xs text-ink-muted">
              Totals update automatically as you change codes; delivery is based on your
              selected location.
            </p>
          </div>
        </section>

        {/* Order summary */}
        <section className="rounded-2xl border border-border bg-surface p-6 shadow-card">
          <h2 className="font-display text-lg font-semibold mb-4">Order Summary</h2>
          <div className="max-h-48 space-y-1.5 overflow-auto pr-1 text-sm">
            {summary.items.map((item) => (
              <div key={item.id} className="flex justify-between gap-3">
                <span className="text-ink-muted">
                  {item.product_name}
                  {item.variant_name ? ` (${item.variant_name})` : ""} × {item.quantity}
                </span>
                <span className="shrink-0">{formatINR(item.line_total)}</span>
              </div>
            ))}
          </div>
          <hr className="my-4 border-border" />
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-ink-muted">Subtotal</span>
              <span>{formatINR(summary.subtotal)}</span>
            </div>
            {summary.product_discount > 0 && (
              <div className="flex justify-between text-success">
                <span>Product discounts</span>
                <span>-{formatINR(summary.product_discount)}</span>
              </div>
            )}
            {summary.coupon_discount > 0 && (
              <div className="flex justify-between text-success">
                <span>Coupon ({couponCode})</span>
                <span>-{formatINR(summary.coupon_discount)}</span>
              </div>
            )}
            {summary.voucher_discount > 0 && (
              <div className="flex justify-between text-success">
                <span>Voucher ({voucherCode})</span>
                <span>-{formatINR(summary.voucher_discount)}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-ink-muted">Delivery</span>
              <span className={summary.delivery_free ? "text-success" : ""}>
                {summary.delivery_free ? "FREE" : formatINR(summary.delivery_charge)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-muted">GST</span>
              <span>{formatINR(summary.tax_total)}</span>
            </div>
            <hr className="border-border" />
            <div className="flex justify-between font-semibold">
              <span>Total</span>
              <span>{formatINR(summary.grand_total)}</span>
            </div>
          </div>
          <Button onClick={handlePlaceOrder} disabled={placing} className="mt-4 w-full">
            {placing ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Placing order…
              </>
            ) : (
              <>
                Place Order <ArrowRight className="ml-2 h-4 w-4" />
              </>
            )}
          </Button>
        </section>
      </div>
    </div>
  )
}