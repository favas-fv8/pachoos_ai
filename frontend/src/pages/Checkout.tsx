import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { MapPin, CreditCard, Tag, ArrowRight, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api/client"
import { useAppDispatch } from "@/store/hooks"
import { pushToast } from "@/store/slices/uiSlice"

export default function Checkout() {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const [addressId, setAddressId] = useState("")
  const [couponCode, setCouponCode] = useState("")
  const [voucherCode, setVoucherCode] = useState("")
  const [distanceKm, setDistanceKm] = useState(1.0)
  const [paymentMethod, setPaymentMethod] = useState("upi")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  const handlePlaceOrder = async () => {
    setLoading(true)
    setError("")
    try {
      const res = await api.post("/api/v1/orders/", {
        delivery_address_id: addressId || 1,
        distance_km: distanceKm,
        coupon_code: couponCode || undefined,
        voucher_code: voucherCode || undefined,
        payment_method: paymentMethod,
      })
      dispatch(pushToast({ message: "Order placed! Redirecting to payment...", variant: "success" }))
      navigate(`/payment/${res.data.id}`)
    } catch (err: any) {
      const msg = err?.response?.data?.error?.message || "Failed to place order."
      setError(msg)
    } finally {
      setLoading(false)
    }
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
            <Input placeholder="Address ID (for demo)" value={addressId} onChange={(e) => setAddressId(e.target.value)} />
            <Input
              type="number"
              placeholder="Distance (km)"
              value={distanceKm}
              onChange={(e) => setDistanceKm(parseFloat(e.target.value) || 1)}
            />
            <p className="text-xs text-ink-muted">
              Free delivery if subtotal ≥ ₹99 and distance ≤ 2 km. Otherwise ₹20.
            </p>
          </div>
        </section>

        {/* Payment */}
        <section className="rounded-2xl border border-border bg-surface p-6 shadow-card">
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <CreditCard className="h-5 w-5 text-primary" /> Payment
          </h2>
          <div className="space-y-3">
            <select
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value)}
              className="w-full rounded-xl border border-border bg-surface px-4 py-2 text-sm shadow-sm focus-visible:ring-2 focus-visible:ring-ring/40"
            >
              <option value="upi">UPI</option>
              <option value="card">Card</option>
              <option value="netbanking">Net Banking</option>
              <option value="wallet">Wallet</option>
            </select>
          </div>
        </section>

        {/* Coupon / Voucher */}
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
          </div>
        </section>

        {/* Order summary */}
        <section className="rounded-2xl border border-border bg-surface p-6 shadow-card">
          <h2 className="font-display text-lg font-semibold mb-4">Order Summary</h2>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-ink-muted">Subtotal</span>
              <span>₹0.00</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-muted">Delivery</span>
              <span>₹20.00</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-muted">Tax (GST)</span>
              <span>₹0.00</span>
            </div>
            <hr className="border-border" />
            <div className="flex justify-between font-semibold">
              <span>Total</span>
              <span>₹20.00</span>
            </div>
          </div>
          <Button onClick={handlePlaceOrder} disabled={loading} className="mt-4 w-full">
            {loading ? (
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