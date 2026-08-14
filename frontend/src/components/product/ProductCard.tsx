import { Link } from "react-router-dom"
import { motion } from "framer-motion"
import { Star, ShoppingCart, Heart } from "lucide-react"
import { Button, ButtonLink } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { formatINR, formatRating } from "@/lib/utils"
import type { Product } from "@/types"

interface ProductCardProps {
  product: Product
}

export function ProductCard({ product }: ProductCardProps) {
  const discountPrice = product.effective_price
  const hasDiscount = product.discount_percent > 0
  const ratingLabel = formatRating(product.avg_rating, product.rating_count)
  const hasRating = ratingLabel !== "No ratings"

  return (
    <motion.div
      whileHover={{ y: -4 }}
      transition={{ duration: 0.2 }}
    >
      <Link
        to={`/product/${product.slug}`}
        className="block rounded-2xl border border-border bg-surface shadow-card transition-shadow hover:shadow-lg"
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
          {!product.is_available && (
            <div className="absolute inset-0 flex items-center justify-center bg-ink/50">
              <Badge variant="muted">Out of stock</Badge>
            </div>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-3 top-3 rounded-full bg-surface/80"
            aria-label="Add to wishlist"
          >
            <Heart className="h-4 w-4" />
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
          <ButtonLink
            variant="default"
            size="sm"
            className="mt-3 w-full"
            href={`/product/${product.slug}`}
          >
            <ShoppingCart className="mr-2 h-4 w-4" />
            {product.is_available ? "Add to cart" : "Unavailable"}
          </ButtonLink>
        </div>
      </Link>
    </motion.div>
  )
}