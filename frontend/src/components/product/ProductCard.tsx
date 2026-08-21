import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { motion } from "framer-motion"
import { Star, ShoppingCart, Heart, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn, formatINR, formatRating } from "@/lib/utils"
import { api, toApiError } from "@/lib/api/client"
import { useAppDispatch, useAppSelector } from "@/store/hooks"
import { pushToast, setCartItemCount } from "@/store/slices/uiSlice"
import { useWishlist } from "@/hooks/useWishlist"
import type { Product } from "@/types"

interface ProductCardProps {
  product: Product
}

async function ensureCartId(): Promise<{ id: number; itemCount: number }> {
  const res = await api.get("/api/v1/cart/carts/current/")
  return { id: Number(res.data.id), itemCount: res.data.item_count ?? 0 }
}

export function ProductCard({ product }: ProductCardProps) {
  const navigate = useNavigate()
  const dispatch = useAppDispatch()
  const isAuthenticated = useAppSelector((s) => s.auth.isAuthenticated)
  const { toggleWishlist, isWishlisted } = useWishlist()

  const [cartStatus, setCartStatus] = useState<"idle" | "adding">("idle")
  const [wishlistLoading, setWishlistLoading] = useState(false)

  const discountPrice = product.effective_price
  const hasDiscount = product.discount_percent > 0
  const ratingLabel = formatRating(product.avg_rating, product.rating_count)
  const hasRating = ratingLabel !== "No ratings"
  const wishlisted = isWishlisted(product.id)
  // Availability follows the live stock count managed in /admin/products.
  const inStock = product.is_available && product.stock_quantity > 0

  const handleAddToCart = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (cartStatus !== "idle" || !inStock) return

    if (!isAuthenticated) {
      dispatch(pushToast({ message: "Please sign in to continue.", variant: "error" }))
      navigate("/login")
      return
    }

    setCartStatus("adding")
    try {
      const { id: cartId } = await ensureCartId()
      await api.post(`/api/v1/cart/carts/${cartId}/add_item/`, {
        product_id: product.id,
        quantity: 1,
      })
      const countRes = await api.get("/api/v1/cart/carts/current/")
      dispatch(setCartItemCount(countRes.data.item_count ?? 0))
      dispatch(pushToast({ message: "Added to cart", variant: "success" }))
    } catch (err) {
      dispatch(pushToast({ message: toApiError(err).message, variant: "error" }))
    } finally {
      setCartStatus("idle")
    }
  }

  const handleToggleWishlist = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (wishlistLoading) return

    if (!isAuthenticated) {
      dispatch(pushToast({ message: "Please sign in to add to wishlist.", variant: "error" }))
      navigate("/login")
      return
    }

    setWishlistLoading(true)
    const result = await toggleWishlist(product.id)
    if (result.success) {
      dispatch(
        pushToast({
          message: wishlisted ? "Removed from wishlist" : "Added to wishlist",
          variant: "success",
        }),
      )
    } else {
      dispatch(pushToast({ message: result.error || "Something went wrong.", variant: "error" }))
    }
    setWishlistLoading(false)
  }

  return (
    <motion.div
      whileHover={{ y: -4 }}
      transition={{ duration: 0.2 }}
      className="block cursor-pointer rounded-2xl border border-border bg-surface shadow-card transition-shadow hover:shadow-lg"
      onClick={() => navigate(`/product/${product.slug}`)}
    >
      {/* Image placeholder */}
      <div className="relative aspect-square overflow-hidden rounded-t-2xl bg-surface-muted">
        {product.primary_image ? (
          <img
            src={product.primary_image}
            alt={product.name}
            loading="lazy"
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-4xl">
            🎂
          </div>
        )}
        {hasDiscount && (
          <Badge variant="danger" className="absolute left-3 top-3">
            -{product.discount_percent}%
          </Badge>
        )}
        {!inStock && (
          <div className="absolute inset-0 flex items-center justify-center bg-ink/50">
            <Badge variant="muted">Out of stock</Badge>
          </div>
        )}
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            "absolute right-3 top-3 rounded-full bg-surface/80",
            wishlisted && "text-danger",
          )}
          aria-label={wishlisted ? "Remove from wishlist" : "Add to wishlist"}
          onClick={handleToggleWishlist}
          disabled={wishlistLoading}
        >
          {wishlistLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Heart className={cn("h-4 w-4", wishlisted && "fill-danger")} />
          )}
        </Button>
      </div>

      {/* Info */}
      <div className="p-4">
        <p className="text-xs text-ink-muted">
          {product.category_name} → {product.subcategory_name}
        </p>
        <h3 className="mt-1 font-medium text-ink line-clamp-1">{product.name}</h3>
        <div className="mt-2 flex items-center gap-1">
          <Star className="h-3.5 w-3.5 fill-warning text-warning" />
          <span className="text-xs text-ink-muted">
            {hasRating ? `${ratingLabel} (${product.rating_count})` : "No ratings"}
          </span>
        </div>
        <div className="mt-3 flex items-baseline gap-2">
          <span className="text-lg font-semibold">
            {formatINR(discountPrice)}
          </span>
          {hasDiscount && (
            <span className="text-sm text-ink-muted line-through">
              {formatINR(product.base_price)}
            </span>
          )}
        </div>
        <Button
          variant="default"
          size="sm"
          className="mt-3 w-full"
          disabled={!inStock || cartStatus !== "idle"}
          onClick={handleAddToCart}
        >
          {cartStatus === "adding" ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <ShoppingCart className="mr-2 h-4 w-4" />
          )}
          {inStock ? "Add to cart" : "Unavailable"}
        </Button>
      </div>
    </motion.div>
  )
}
