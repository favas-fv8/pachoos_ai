import { useState, useEffect } from "react"
import { useParams, useNavigate } from "react-router-dom"
import {
  ArrowLeft,
  ShoppingCart,
  Zap,
  Star,
  Truck,
  Shield,
  Leaf,
  Loader2,
  AlertTriangle,
  RefreshCw,
  ShoppingBag,
} from "lucide-react"
import { Button, ButtonLink } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { BackButton } from "@/components/ui/back-button"
import { ProductCard } from "@/components/product/ProductCard"
import { cn, formatINR, formatRating } from "@/lib/utils"
import { api, toApiError } from "@/lib/api/client"
import { useAppDispatch, useAppSelector } from "@/store/hooks"
import { pushToast, setCartItemCount } from "@/store/slices/uiSlice"
import type { Product, ProductVariant, ProductImage } from "@/types"

type CartStatus = "idle" | "adding" | "buying"

/** Find the user's active cart, creating one if none exists yet. */
async function ensureCartId(): Promise<{ id: number; itemCount: number }> {
  const res = await api.get("/api/v1/cart/carts/current/")
  return { id: Number(res.data.id), itemCount: res.data.item_count ?? 0 }
}

export default function ProductDetail() {
  const { slug } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const dispatch = useAppDispatch()
  const isAuthenticated = useAppSelector((s) => s.auth.isAuthenticated)

  const [product, setProduct] = useState<Product | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  const [selectedVariantId, setSelectedVariantId] = useState<number | null>(null)
  const [quantity, setQuantity] = useState(1)
  const [activeImage, setActiveImage] = useState(0)

  const [related, setRelated] = useState<Product[]>([])
  const [relatedLoading, setRelatedLoading] = useState(false)
  const [cartStatus, setCartStatus] = useState<CartStatus>("idle")

  // Load the product. Works for direct URL visits and browser refresh because
  // the fetch is driven purely by the :slug route param.
  useEffect(() => {
    if (!slug) return
    let cancelled = false
    setLoading(true)
    setNotFound(false)
    setError(null)
    setProduct(null)
    setRelated([])
    setQuantity(1)
    setSelectedVariantId(null)
    setActiveImage(0)

    api
      .get(`/api/v1/catalog/products/${slug}/`)
      .then((res) => {
        if (cancelled) return
        setProduct(res.data)
        setSelectedVariantId(res.data.variants?.[0]?.id ?? null)
      })
      .catch((err) => {
        if (cancelled) return
        const apiErr = toApiError(err)
        if (apiErr.status === 404) {
          setNotFound(true)
        } else {
          setError(apiErr.message)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [slug, reloadKey])

  // Related / recommended products (best-effort, reuses the catalog related API).
  useEffect(() => {
    if (!product?.id) return
    let cancelled = false
    setRelatedLoading(true)
    api
      .get(`/api/v1/catalog/products/${product.slug}/related/`)
      .then((res) => {
        if (!cancelled) setRelated(res.data)
      })
      .catch(() => {
        /* best-effort — hide the section on failure */
      })
      .finally(() => {
        if (!cancelled) setRelatedLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [product?.id, product?.slug])

  const variant = product?.variants?.find((v) => v.id === selectedVariantId) ?? null
  const price = variant?.effective_price ?? product?.effective_price ?? 0
  const basePrice = product?.base_price ?? 0
  const stock = variant?.stock_quantity ?? product?.stock_quantity ?? 0
  const unit = product?.stock_unit ?? "count"
  const outOfStock = !product || !product.is_available || stock <= 0
  const maxQuantity = Math.max(1, stock)

  const retry = () => setReloadKey((k) => k + 1)

  const requireAuth = () => {
    dispatch(pushToast({ message: "Please sign in to continue.", variant: "error" }))
    navigate("/login")
  }

  /** Add the current selection to the user's cart. Returns false if not signed in. */
  const addCurrentItemToCart = async (): Promise<boolean> => {
    if (!product) return false
    if (!isAuthenticated) {
      requireAuth()
      return false
    }
    const { id: cartId, itemCount } = await ensureCartId()
    await api.post(`/api/v1/cart/carts/${cartId}/add_item/`, {
      product_id: product.id,
      variant_id: variant?.id ?? undefined,
      quantity,
    })
    /* Update the cart item count in Redux so the navbar badge
       reflects the new total immediately without page refresh. */
    dispatch(setCartItemCount(itemCount + quantity))
    return true
  }

  const handleAddToCart = async () => {
    if (cartStatus !== "idle") return
    setCartStatus("adding")
    try {
      const added = await addCurrentItemToCart()
      if (added) {
        dispatch(pushToast({ message: "Added to cart", variant: "success" }))
        /* Refresh cart state so the navbar badge and any
           visible cart count update immediately without page refresh. */
        void ensureCartId()
      }
    } catch (err) {
      dispatch(pushToast({ message: toApiError(err).message, variant: "error" }))
    } finally {
      setCartStatus("idle")
    }
  }

  const handleBuyNow = async () => {
    if (cartStatus !== "idle") return
    if (!product) return
    if (!isAuthenticated) {
      requireAuth()
      return
    }
    setCartStatus("buying")
    try {
      const res = await api.post("/api/v1/orders/direct/", {
        product_id: product.id,
        variant_id: variant?.id ?? null,
        quantity,
        delivery_address_id: 0,
        distance_km: 1.0,
        payment_method: "cashfree",
      })
      navigate(`/payment/${res.data.id}`)
    } catch (err) {
      dispatch(pushToast({ message: toApiError(err).message, variant: "error" }))
      setCartStatus("idle")
    }
  }

  // ── Loading state ────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="container-px mx-auto py-8">
        <Skeleton className="mb-6 h-9 w-28" />
        <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
          <Skeleton className="aspect-square w-full rounded-2xl" />
          <div className="space-y-4">
            <Skeleton className="h-8 w-1/2" />
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-10 w-2/3" />
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-11 w-full" />
          </div>
        </div>
      </div>
    )
  }

  // ── Product not found / invalid id ───────────────────────────────────────
  if (notFound || (!product && !error)) {
    return (
      <div className="container-px mx-auto py-16 text-center">
        <AlertTriangle className="mx-auto mb-4 h-12 w-12 text-warning" />
        <h2 className="font-display text-2xl font-bold">Product not found</h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-ink-muted">
          The product you are looking for does not exist or is no longer
          available. It may have been removed by the shop.
        </p>
        <ButtonLink variant="link" className="mt-4" href="/shop">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to shop
        </ButtonLink>
      </div>
    )
  }

  // ── API / network error ──────────────────────────────────────────────────
  if (!product && error) {
    return (
      <div className="container-px mx-auto py-16 text-center">
        <AlertTriangle className="mx-auto mb-4 h-12 w-12 text-danger" />
        <h2 className="font-display text-2xl font-bold">Something went wrong</h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-ink-muted">{error}</p>
        <div className="mt-6 flex items-center justify-center gap-3">
          <Button onClick={retry}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Try again
          </Button>
          <ButtonLink variant="outline" href="/shop">
            Back to shop
          </ButtonLink>
        </div>
      </div>
    )
  }

  if (!product) return null

  const images = product.images ?? []
  const ratingLabel = formatRating(product.avg_rating, product.rating_count)
  const hasRating = ratingLabel !== "No ratings"
  const unitLabel = unit === "kg" ? "per kg" : "per piece"

  return (
    <div className="container-px mx-auto py-8">
      <BackButton to="/shop" className="mb-6" />

      <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
        {/* ── Gallery ─────────────────────────────────────────────────────── */}
        <div className="space-y-4">
          <div className="aspect-square overflow-hidden rounded-2xl bg-surface-muted">
            {images[activeImage]?.image_url ? (
              <img
                src={images[activeImage].image_url}
                alt={images[activeImage].alt_text || product.name}
                className="h-full w-full object-cover"
              />
            ) : product.primary_image ? (
              <img
                src={product.primary_image}
                alt={product.name}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full items-center justify-center text-6xl">
                🎂
              </div>
            )}
          </div>
          {images.length > 1 && (
            <div className="flex gap-2 overflow-x-auto">
              {images.map((img: ProductImage, i: number) => (
                <button
                  key={img.id ?? i}
                  type="button"
                  onClick={() => setActiveImage(i)}
                  className={cn(
                    "h-20 w-20 shrink-0 overflow-hidden rounded-xl bg-surface-muted border-2 transition-colors",
                    i === activeImage
                      ? "border-primary"
                      : "border-transparent hover:border-border",
                  )}
                >
                  <img
                    src={img.image_url}
                    alt={img.alt_text || product.name}
                    className="h-full w-full rounded-xl object-cover"
                  />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* ── Details ─────────────────────────────────────────────────────── */}
        <div className="space-y-5">
          <div>
            {product.category_name && (
              <Badge variant="outline" className="mb-2">
                {product.category_name}
                {product.subcategory_name ? ` → ${product.subcategory_name}` : ""}
              </Badge>
            )}
            <h1 className="font-display text-3xl font-bold">{product.name}</h1>

            <div className="mt-2 flex items-center gap-2">
              <Star className="h-4 w-4 fill-warning text-warning" />
              {hasRating ? (
                <>
                  <span className="text-sm font-medium">{ratingLabel}</span>
                  <span className="text-sm text-ink-muted">
                    ({product.rating_count} review{product.rating_count === 1 ? "" : "s"})
                  </span>
                </>
              ) : (
                <span className="text-sm text-ink-muted">No ratings yet</span>
              )}
            </div>

            {product.pid && (
              <p className="mt-2 text-xs text-ink-muted">Product ID: {product.pid}</p>
            )}
          </div>

          {/* Price */}
          <div className="flex flex-wrap items-baseline gap-3">
            <span className="text-3xl font-bold">{formatINR(price)}</span>
            <span className="text-sm text-ink-muted">{unitLabel}</span>
            {product.discount_percent > 0 && (
              <>
                <span className="text-lg text-ink-muted line-through">
                  {formatINR(basePrice)}
                </span>
                <Badge variant="danger">-{product.discount_percent}% off</Badge>
              </>
            )}
          </div>

          {/* Description */}
          {product.description && (
            <div>
              <h4 className="font-display font-semibold">Description</h4>
              <p className="mt-1 text-sm text-ink-muted whitespace-pre-line">
                {product.description}
              </p>
            </div>
          )}

          {/* Variant selector */}
          {product.variants && product.variants.length > 0 && (
            <div>
              <h4 className="font-display font-semibold">Size / Weight</h4>
              <div className="mt-2 flex flex-wrap gap-2">
                {product.variants.map((v: ProductVariant) => (
                  <button
                    key={v.id}
                    type="button"
                    onClick={() => setSelectedVariantId(v.id)}
                    className={cn(
                      "rounded-full border px-4 py-1.5 text-sm font-medium transition-colors",
                      selectedVariantId === v.id
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border bg-surface text-ink hover:bg-surface-muted",
                    )}
                  >
                    {v.name} — {formatINR(v.effective_price)}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Stock & freshness */}
          <div className="flex flex-wrap items-center gap-4">
            <Badge variant={outOfStock ? "danger" : "success"}>
              {outOfStock ? "Out of stock" : "In stock"}
            </Badge>
            <Badge variant="outline">{product.freshness}</Badge>
            {!outOfStock && stock <= 5 && (
              <Badge variant="warning">Only {stock} {unit} left</Badge>
            )}
            {product.stock_quantity > 0 && (
              <span className="text-xs text-ink-muted">
                {stock > 0 ? `${stock} ${unit} available` : ""}
              </span>
            )}
          </div>

          {/* Quantity + actions */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 rounded-xl border border-border bg-surface px-2 py-1">
              <button
                type="button"
                aria-label="Decrease quantity"
                disabled={outOfStock || quantity <= 1}
                onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                className="grid h-8 w-8 place-items-center rounded-lg text-lg text-ink transition-colors hover:bg-surface-muted disabled:opacity-40"
              >
                −
              </button>
              <Input
                type="number"
                min={1}
                max={maxQuantity}
                value={quantity}
                disabled={outOfStock}
                onChange={(e) =>
                  setQuantity(
                    Math.max(1, Math.min(maxQuantity, parseInt(e.target.value) || 1)),
                  )
                }
                className="w-16 border-0 bg-transparent px-0 text-center shadow-none focus-visible:ring-0"
              />
              <button
                type="button"
                aria-label="Increase quantity"
                disabled={outOfStock || quantity >= maxQuantity}
                onClick={() => setQuantity((q) => Math.min(maxQuantity, q + 1))}
                className="grid h-8 w-8 place-items-center rounded-lg text-lg text-ink transition-colors hover:bg-surface-muted disabled:opacity-40"
              >
                +
              </button>
            </div>

            <Button
              size="lg"
              className="flex-1"
              disabled={outOfStock || cartStatus !== "idle"}
              onClick={handleAddToCart}
            >
              {cartStatus === "adding" ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <ShoppingCart className="mr-2 h-4 w-4" />
              )}
              {outOfStock ? "Out of stock" : "Add to cart"}
            </Button>

            <Button
              size="lg"
              variant="secondary"
              className="flex-1"
              disabled={outOfStock || cartStatus !== "idle"}
              onClick={handleBuyNow}
            >
              {cartStatus === "buying" ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Zap className="mr-2 h-4 w-4" />
              )}
              Buy now
            </Button>
          </div>

          {/* Trust badges */}
          <div className="flex flex-wrap gap-4 pt-2 text-sm text-ink-muted">
            <span className="flex items-center gap-1">
              <Truck className="h-4 w-4 text-primary" /> Free delivery
            </span>
            <span className="flex items-center gap-1">
              <Shield className="h-4 w-4 text-primary" /> Secure payment
            </span>
            <span className="flex items-center gap-1">
              <Leaf className="h-4 w-4 text-primary" /> Fresh guarantee
            </span>
          </div>

          {/* Product information */}
          <div className="space-y-4 border-t border-border pt-5">
            {product.ingredients && (
              <div>
                <h4 className="font-display font-semibold">Ingredients</h4>
                <p className="mt-1 text-sm text-ink-muted">{product.ingredients}</p>
              </div>
            )}

            {product.brand && (
              <div>
                <h4 className="font-display font-semibold">Brand</h4>
                <p className="mt-1 text-sm text-ink-muted">{product.brand}</p>
              </div>
            )}

            {product.sku && (
              <div>
                <h4 className="font-display font-semibold">SKU</h4>
                <p className="mt-1 text-sm text-ink-muted">{product.sku}</p>
              </div>
            )}

            {product.tags && product.tags.length > 0 && (
              <div>
                <h4 className="font-display font-semibold">Tags</h4>
                <div className="mt-2 flex flex-wrap gap-2">
                  {product.tags.map((tag) => (
                    <Badge key={tag.id} variant="muted">
                      {tag.name}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {product.nutritional_info && (
              <div>
                <h4 className="font-display font-semibold">Nutritional Info</h4>
                <pre className="mt-1 whitespace-pre-wrap text-sm text-ink-muted">
                  {JSON.stringify(product.nutritional_info, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Related products ─────────────────────────────────────────────── */}
      <section className="mt-14">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-xl font-bold">Related products</h2>
          <ButtonLink variant="ghost" size="sm" href="/shop" className="gap-1">
            View all products <ArrowLeft className="h-4 w-4 rotate-180" />
          </ButtonLink>
        </div>

        {relatedLoading ? (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="rounded-2xl border border-border bg-surface p-4">
                <Skeleton className="aspect-square w-full rounded-xl" />
                <Skeleton className="mt-3 h-4 w-3/4" />
                <Skeleton className="mt-2 h-4 w-1/3" />
              </div>
            ))}
          </div>
        ) : related.length > 0 ? (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {related.map((item) => (
              <ProductCard key={item.id} product={item} />
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center rounded-2xl border border-dashed border-border bg-surface py-10 text-center">
            <ShoppingBag className="mb-2 h-8 w-8 text-ink-muted" />
            <p className="text-sm text-ink-muted">No related products found.</p>
            <ButtonLink href="/shop" variant="link" className="mt-2">
              Browse the full shop
            </ButtonLink>
          </div>
        )}
      </section>
    </div>
  )
}
