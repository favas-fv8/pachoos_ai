// Recommendations — product recommendations section.
import { useState, useEffect } from "react"
import { Sparkles, ArrowRight, Loader2 } from "lucide-react"
import { ButtonLink } from "@/components/ui/button"
import { api } from "@/lib/api/client"
import { formatINR } from "@/lib/utils"
import { motion } from "framer-motion"
import type { Product } from "@/types"

interface RecommendationsProps {
  productId?: string
  title?: string
  limit?: number
}

export function Recommendations({ productId, title = "Recommended for you", limit = 8 }: RecommendationsProps) {
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (productId) params.set("product_id", productId)

    api.get(`/api/v1/ai/recommendations/?${params}`)
      .then((res) => setProducts(res.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [productId, limit])

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    )
  }

  if (products.length === 0) return null

  return (
    <section className="mt-8">
      <div className="flex items-center gap-2 mb-4">
        <Sparkles className="h-5 w-5 text-primary" />
        <h2 className="font-display text-xl font-bold">{title}</h2>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
        {products.map((product, i) => (
          <motion.div
            key={product.id}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className="flex"
          >
            <ButtonLink
              href={`/product/${product.slug}`}
              variant="outline"
              className="h-full w-full flex-col items-start justify-between rounded-2xl border border-border bg-surface p-4 text-left shadow-card hover:shadow-pop"
            >
              <div className="mb-2 aspect-square w-full overflow-hidden rounded-xl bg-ink-subtle">
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
              </div>
              <p className="text-sm font-medium line-clamp-2">{product.name}</p>
              <div className="mt-1 flex items-center gap-2">
                <span className="text-sm font-bold text-primary">
                  {formatINR(Number(product.effective_price))}
                </span>
                {Number(product.discount_percent) > 0 && (
                  <span className="text-xs text-ink-muted line-through">
                    {formatINR(Number(product.base_price))}
                  </span>
                )}
              </div>
              {product.avg_rating != null && Number(product.avg_rating) > 0 && (
                <p className="mt-1 text-xs text-ink-muted">
                  {"★".repeat(Math.round(Number(product.avg_rating)))} ({product.avg_rating})
                </p>
              )}
            </ButtonLink>
          </motion.div>
        ))}
      </div>

      <div className="mt-4 text-center">
        <ButtonLink href="/shop" variant="ghost" className="gap-1">
          View all products <ArrowRight className="h-4 w-4" />
        </ButtonLink>
      </div>
    </section>
  )
}
