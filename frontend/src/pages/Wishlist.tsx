import { useState, useEffect, useCallback } from "react"
import { Link } from "react-router-dom"
import { motion } from "framer-motion"
import { Heart, Trash2, ShoppingCart, Loader2, ShoppingBag } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { BackButton } from "@/components/ui/back-button"
import { api, toApiError } from "@/lib/api/client"
import { useAppDispatch } from "@/store/hooks"
import { pushToast } from "@/store/slices/uiSlice"
import { formatINR } from "@/lib/utils"
import type { WishlistItem } from "@/types"

export default function Wishlist() {
  const dispatch = useAppDispatch()
  const [items, setItems] = useState<WishlistItem[]>([])
  const [loading, setLoading] = useState(true)
  const [removingId, setRemovingId] = useState<number | null>(null)

  const fetchWishlist = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get("/api/v1/catalog/wishlist/")
      setItems(res.data)
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchWishlist()
  }, [fetchWishlist])

  const handleRemove = async (item: WishlistItem) => {
    if (removingId !== null) return
    setRemovingId(item.product)
    try {
      await api.delete(`/api/v1/catalog/wishlist/${item.product}/`)
      setItems((prev) => prev.filter((i) => i.product !== item.product))
      dispatch(pushToast({ message: "Removed from wishlist", variant: "success" }))
    } catch (err) {
      dispatch(pushToast({ message: toApiError(err).message, variant: "error" }))
    } finally {
      setRemovingId(null)
    }
  }

  if (loading) {
    return (
      <div className="container-px mx-auto py-8">
        <BackButton to="/shop" className="mb-4" />
        <h1 className="font-display text-3xl font-bold">My Wishlist</h1>
        <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-2xl border border-border bg-surface p-4">
              <div className="aspect-square rounded-xl bg-surface-muted animate-pulse" />
              <div className="mt-3 h-4 w-3/4 rounded bg-surface-muted animate-pulse" />
              <div className="mt-2 h-4 w-1/4 rounded bg-surface-muted animate-pulse" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="container-px mx-auto py-8">
      <BackButton to="/shop" className="mb-4" />
      <div className="flex items-center gap-3">
        <Heart className="h-7 w-7 text-danger fill-danger" />
        <h1 className="font-display text-3xl font-bold">My Wishlist</h1>
      </div>
      <p className="mt-1 text-sm text-ink-muted">
        {items.length} product{items.length !== 1 ? "s" : ""} saved
      </p>

      {items.length === 0 ? (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-16 flex flex-col items-center text-center"
        >
          <div className="grid h-20 w-20 place-items-center rounded-full bg-danger/10">
            <Heart className="h-10 w-10 text-danger/40" />
          </div>
          <p className="mt-4 text-lg font-medium text-ink">Your Wishlist is Empty</p>
          <p className="mt-1 text-sm text-ink-muted">
            Save your favourite products here for quick access later.
          </p>
          <Button asChild className="mt-6">
            <Link to="/shop">
              <ShoppingBag className="mr-2 h-4 w-4" />
              Continue Shopping
            </Link>
          </Button>
        </motion.div>
      ) : (
        <motion.div
          className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
        >
          {items.map((item) => {
            const hasDiscount = item.discount_percent > 0
            const isRemoving = removingId === item.product

            return (
              <motion.div
                key={item.id}
                layout
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="group relative flex flex-col rounded-2xl border border-border bg-surface shadow-card transition-shadow hover:shadow-lg"
              >
                {/* Image */}
                <Link
                  to={`/product/${item.product_slug}`}
                  className="relative aspect-square overflow-hidden rounded-t-2xl bg-surface-muted"
                >
                  {item.primary_image ? (
                    <img
                      src={item.primary_image}
                      alt={item.product_name}
                      loading="lazy"
                      className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center text-4xl">
                      🎂
                    </div>
                  )}
                  {hasDiscount && (
                    <Badge variant="danger" className="absolute left-3 top-3">
                      -{item.discount_percent}%
                    </Badge>
                  )}
                  {!item.is_available && (
                    <div className="absolute inset-0 flex items-center justify-center bg-ink/50">
                      <Badge variant="muted">Out of stock</Badge>
                    </div>
                  )}
                </Link>

                {/* Info */}
                <div className="flex flex-1 flex-col p-4">
                  <p className="text-xs text-ink-muted">
                    {item.category_name} → {item.subcategory_name}
                  </p>
                  <Link
                    to={`/product/${item.product_slug}`}
                    className="mt-1 font-medium text-ink line-clamp-1 hover:text-primary"
                  >
                    {item.product_name}
                  </Link>

                  <div className="mt-auto">
                    <div className="mt-3 flex items-baseline gap-2">
                      <span className="text-lg font-semibold">
                        {formatINR(item.effective_price)}
                      </span>
                      {hasDiscount && (
                        <span className="text-sm text-ink-muted line-through">
                          {formatINR(item.base_price)}
                        </span>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="mt-3 flex gap-2">
                      <Button
                        asChild
                        variant="default"
                        size="sm"
                        className="flex-1"
                        disabled={!item.is_available}
                      >
                        <Link to={`/product/${item.product_slug}`}>
                          <ShoppingCart className="mr-1.5 h-3.5 w-3.5" />
                          View
                        </Link>
                      </Button>
                      <Button
                        variant="outline"
                        size="icon"
                        className="h-9 w-9 shrink-0 text-danger hover:bg-danger/10 hover:text-danger"
                        aria-label="Remove from wishlist"
                        onClick={() => handleRemove(item)}
                        disabled={isRemoving}
                      >
                        {isRemoving ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </div>
                </div>
              </motion.div>
            )
          })}
        </motion.div>
      )}
    </div>
  )
}
