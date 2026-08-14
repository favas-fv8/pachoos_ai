// Recommendations — product recommendations section.
import { useState, useEffect } from "react"
import { Sparkles, ArrowRight, Loader2 } from "lucide-react"
import { ButtonLink } from "@/components/ui/button"
import { api } from "@/lib/api/client"
import { formatINR } from "@/lib/utils"
import { motion } from "framer-motion"

interface Product {
  id: string
  name: string
  slug: string
  base_price: string
  discount_percent: string
  avg_rating: number | string
  times_sold: number
  images?: { image_url: string; alt_text: string }[]
}

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
          >
            <ButtonLink
              href={`/product/${product.slug}`}
              variant="outline"
              className="h-full flex-col items-start rounded-2xl border border-border bg-surface p-4 text-left shadow-card hover:shadow-pop"
            >
              <div className="mb-2 h-32 w-full overflow-hidden rounded-xl bg-ink-subtle">
                {product.images?.[0] ? (
                  <img
                    src={product.images[0].image_url}
                    alt={product.images[0].alt_text || product.name}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="grid h-full w-full place-items-center text-ink-muted text-sm">
                    No image
                  </div>
                )}
              </div>
              <p className="text-sm font-medium line-clamp-2">{product.name}</p>
              <div className="mt-1 flex items-center gap-2">
                <span className="text-sm font-bold text-primary">
                  {formatINR(parseFloat(product.base_price) * (1 - parseFloat(product.discount_percent) / 100))}
                </span>
                {parseFloat(product.discount_percent) > 0 && (
                  <span className="text-xs text-ink-muted line-through">
                    {formatINR(parseFloat(product.base_price))}
                  </span>
                )}
              </div>
              {parseFloat(String(product.avg_rating)) > 0 && (
                <p className="mt-1 text-xs text-ink-muted">
                  {"★".repeat(Math.round(parseFloat(String(product.avg_rating))))} ({product.avg_rating})
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
