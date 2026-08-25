import { useState, useEffect, useCallback, useRef } from "react"
import { motion } from "framer-motion"
import { Link, useNavigate } from "react-router-dom"
import {
  ShoppingBag,
  ArrowRight,
  Loader2,
  Trash2,
  AlertTriangle,
  RefreshCw,
  Minus,
  Plus,
} from "lucide-react"
import { Button, ButtonLink } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { BackButton } from "@/components/ui/back-button"
import { api, toApiError } from "@/lib/api/client"
import { useAppDispatch, useAppSelector } from "@/store/hooks"
import { pushToast, setCartItemCount } from "@/store/slices/uiSlice"
import { formatINR } from "@/lib/utils"
import type { CartSummary } from "@/types"

export default function Cart() {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const isAuthenticated = useAppSelector((s) => s.auth.isAuthenticated)
  // The "Deliver To" location (header picker) — its coordinates drive the
  // server-side delivery-distance calculation at order placement.
  const deliveryAddress = useAppSelector((s) => s.ui.deliveryAddress)

  const [summary, setSummary] = useState<CartSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [updatingItem, setUpdatingItem] = useState<number | null>(null)
  const [placing, setPlacing] = useState(false)
  const cartIdRef = useRef<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const cartRes = await api.get("/api/v1/cart/carts/current/")
      cartIdRef.current = cartRes.data.id
      const summaryRes = await api.get(`/api/v1/cart/carts/${cartRes.data.id}/summary/`)
      setSummary(summaryRes.data)
      dispatch(setCartItemCount(summaryRes.data.item_count ?? 0))
    } catch (err) {
      setError(toApiError(err).message)
    } finally {
      setLoading(false)
    }
  }, [dispatch])

  useEffect(() => {
    void load()
  }, [load])

  const changeQuantity = async (itemId: number, quantity: number) => {
    if (quantity < 1) return
    setUpdatingItem(itemId)
    try {
      await api.post(`/api/v1/cart/carts/${cartIdRef.current}/update_item/`, {
        item_id: itemId,
        quantity,
      })
      await load()
    } catch (err) {
      dispatch(pushToast({ message: toApiError(err).message, variant: "error" }))
    } finally {
      setUpdatingItem(null)
    }
  }

  const removeItem = async (itemId: number) => {
    setUpdatingItem(itemId)
    try {
      await api.post(`/api/v1/cart/carts/${cartIdRef.current}/remove_item/`, { item_id: itemId })
      await load()
    } catch (err) {
      dispatch(pushToast({ message: toApiError(err).message, variant: "error" }))
    } finally {
      setUpdatingItem(null)
    }
  }

  // Places the order from the cart (the server snapshots every item,
  // quantity, variant, price, discount, delivery charge and cashback) and
  // jumps straight into the same /payment/<order-id> flow used by Buy Now.
  const handleProceedToCheckout = async () => {
    if (placing || !summary || summary.items.length === 0) return
    setPlacing(true)
    try {
      const res = await api.post("/api/v1/orders/", {
        delivery_address_id: 0,
        ...(deliveryAddress
          ? { customer_lat: deliveryAddress.lat, customer_lon: deliveryAddress.lon }
          : {}),
        payment_method: "cashfree",
      })
      // The cart itself is intentionally left untouched — items are only
      // removed by the customer via the Remove button, never by checkout or
      // any payment outcome.
      dispatch(pushToast({ message: "Order placed! Choose your payment method.", variant: "success" }))
      navigate(`/payment/${res.data.id}`)
    } catch (err) {
      dispatch(pushToast({ message: toApiError(err).message, variant: "error" }))
      // Stock or cart state may have changed — refresh the summary.
      await load()
    } finally {
      setPlacing(false)
    }
  }

  if (!isAuthenticated) {
    return (
      <div className="container-px mx-auto py-8">
        <BackButton to="/shop" className="mb-4" />
        <h1 className="font-display text-3xl font-bold">Cart</h1>
        <div className="mt-6 flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-surface py-20 text-center">
          <ShoppingBag className="mb-4 h-12 w-12 text-ink-muted" />
          <p className="text-ink-muted">Please sign in to view your cart.</p>
          <ButtonLink href="/login" className="mt-4">
            Sign in <ArrowRight className="ml-2 h-4 w-4" />
          </ButtonLink>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="container-px mx-auto py-8">
        <BackButton to="/shop" className="mb-4" />
        <h1 className="font-display text-3xl font-bold">Cart</h1>
        <div className="flex justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container-px mx-auto py-8">
        <BackButton to="/shop" className="mb-4" />
        <h1 className="font-display text-3xl font-bold">Cart</h1>
        <div className="mt-6 rounded-2xl border border-danger/30 bg-danger-muted p-6 text-center">
          <AlertTriangle className="mx-auto mb-2 h-8 w-8 text-danger" />
          <p className="text-sm text-danger">{error}</p>
          <Button variant="secondary" size="sm" className="mt-3" onClick={() => void load()}>
            <RefreshCw className="h-4 w-4" /> Retry
          </Button>
        </div>
      </div>
    )
  }

  if (!summary || summary.items.length === 0) {
    return (
      <div className="container-px mx-auto py-8">
        <BackButton to="/shop" className="mb-4" />
        <h1 className="font-display text-3xl font-bold">Cart</h1>
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="mt-6 flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-surface py-20 text-center"
        >
          <ShoppingBag className="mb-4 h-12 w-12 text-ink-muted" />
          <p className="text-ink-muted">Your cart is empty.</p>
          <ButtonLink href="/shop" className="mt-4">
            Start shopping <ArrowRight className="ml-2 h-4 w-4" />
          </ButtonLink>
        </motion.div>
      </div>
    )
  }

  return (
    <div className="container-px mx-auto py-8">
      <BackButton to="/shop" className="mb-4" />
      <div className="flex items-end justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold">Cart</h1>
          <p className="mt-1 text-sm text-ink-muted">
            {summary.item_count} item{summary.item_count === 1 ? "" : "s"} in your cart
          </p>
        </div>
        <ButtonLink variant="ghost" size="sm" href="/shop">
          Continue shopping
        </ButtonLink>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_360px]">
        {/* Items */}
        <div className="space-y-3">
          {summary.items.map((item) => (
            <Link
              key={item.id}
              to={`/product/${item.product_slug}`}
              className="flex gap-4 rounded-2xl border border-border bg-surface p-4 shadow-card transition-shadow hover:shadow-lg"
            >
              <div className="h-24 w-24 shrink-0 overflow-hidden rounded-xl bg-surface-muted">
                {item.image_url ? (
                  <img src={item.image_url} alt={item.product_name} className="h-full w-full object-cover" />
                ) : (
                  <div className="grid h-full w-full place-items-center text-3xl">🎂</div>
                )}
              </div>

              <div className="flex flex-1 flex-col">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">{item.product_name}</p>
                    {item.variant_name && (
                      <p className="text-xs text-ink-muted">{item.variant_name}</p>
                    )}
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <span className="font-medium">{formatINR(item.unit_price)}</span>
                      {item.discount_percent > 0 && (
                        <>
                          <span className="text-xs text-ink-muted line-through">
                            {formatINR(item.base_price)}
                          </span>
                          <span className="text-xs text-success">-{item.discount_percent}%</span>
                        </>
                      )}
                    </div>
                  </div>
                  <p className="font-semibold">{formatINR(item.line_total)}</p>
                </div>

                <div className="mt-auto flex items-center gap-3 pt-3">
                  <div
                    className="flex items-center gap-2 rounded-xl border border-border bg-surface px-2 py-1"
                    onClick={(e) => e.preventDefault()}
                  >
                    <button
                      type="button"
                      aria-label="Decrease quantity"
                      disabled={updatingItem === item.id || item.quantity <= 1}
                      onClick={() => changeQuantity(item.id, item.quantity - 1)}
                      className="grid h-7 w-7 place-items-center rounded-lg text-ink transition-colors hover:bg-surface-muted disabled:opacity-40"
                    >
                      <Minus className="h-4 w-4" />
                    </button>
                    <Input
                      type="number"
                      min={1}
                      value={item.quantity}
                      disabled={updatingItem === item.id}
                      onChange={(e) => {
                        const qty = parseInt(e.target.value, 10)
                        if (qty >= 1) void changeQuantity(item.id, qty)
                      }}
                      className="w-14 border-0 bg-transparent px-0 text-center shadow-none focus-visible:ring-0"
                    />
                    <button
                      type="button"
                      aria-label="Increase quantity"
                      disabled={updatingItem === item.id}
                      onClick={() => changeQuantity(item.id, item.quantity + 1)}
                      className="grid h-7 w-7 place-items-center rounded-lg text-ink transition-colors hover:bg-surface-muted disabled:opacity-40"
                    >
                      <Plus className="h-4 w-4" />
                    </button>
                  </div>
                  <span className="text-xs text-ink-muted">
                    {item.unit === "kg" ? "per kg" : "per piece"}
                  </span>
                  <button
                    type="button"
                    onClick={(e) => { e.preventDefault(); void removeItem(item.id) }}
                    disabled={updatingItem === item.id}
                    className="ml-auto flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-danger transition-colors hover:bg-danger/10 disabled:opacity-50"
                  >
                    <Trash2 className="h-4 w-4" /> Remove
                  </button>
                </div>
              </div>
            </Link>
          ))}
        </div>

        {/* Summary */}
        <div className="h-fit rounded-2xl border border-border bg-surface p-6 shadow-card lg:sticky lg:top-24">
          <h2 className="font-display text-lg font-semibold">Order Summary</h2>
          <div className="mt-4 space-y-2 text-sm">
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
                <span>Coupon</span>
                <span>-{formatINR(summary.coupon_discount)}</span>
              </div>
            )}
            {summary.voucher_discount > 0 && (
              <div className="flex justify-between text-success">
                <span>Voucher</span>
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
            <div className="flex justify-between text-base font-semibold">
              <span>Total</span>
              <span>{formatINR(summary.grand_total)}</span>
            </div>
          </div>
          <p className="mt-3 text-xs text-ink-muted">
            Free delivery over ₹99 within 2 km. Cashback can be applied on the payment page.
          </p>
          <Button
            size="lg"
            className="mt-4 w-full"
            disabled={placing}
            onClick={() => void handleProceedToCheckout()}
          >
            {placing ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Placing order…
              </>
            ) : (
              <>
                Proceed to Checkout <ArrowRight className="ml-2 h-4 w-4" />
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}