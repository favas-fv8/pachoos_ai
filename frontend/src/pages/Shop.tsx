import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import { Search, SlidersHorizontal } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ProductCard } from "@/components/product/ProductCard"
import { api } from "@/lib/api/client"
import type { Product } from "@/types"

const SORT_OPTIONS = [
  { value: "popularity", label: "Popular" },
  { value: "newest", label: "Newest" },
  { value: "price_asc", label: "Price: Low → High" },
  { value: "price_desc", label: "Price: High → Low" },
  { value: "discount", label: "Discount" },
  { value: "rating", label: "Rating" },
]

export default function Shop() {
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState("")
  const [sortBy, setSortBy] = useState("popularity")
  const [category, setCategory] = useState("")
  const [freshness, setFreshness] = useState("")
  const [availableOnly, setAvailableOnly] = useState(false)
  const [total, setTotal] = useState(0)

  const fetchProducts = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (query) params.set("q", query)
      if (category) params.set("category", category)
      if (freshness) params.set("freshness", freshness)
      if (availableOnly) params.set("available", "true")
      params.set("sort_by", sortBy)

      const res = await api.get(`/api/v1/catalog/products/?${params.toString()}`)
      setProducts(res.data.results)
      setTotal(res.data.count)
    } catch {
      // fallback to empty — real data arrives when backend is live
      setProducts([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const debounce = setTimeout(fetchProducts, 300)
    return () => clearTimeout(debounce)
  }, [query, sortBy, category, freshness, availableOnly])

  return (
    <div className="container-px mx-auto py-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold">Shop</h1>
          <p className="text-sm text-ink-muted">
            {total} product{total !== 1 ? "s" : ""}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="rounded-xl border border-border bg-surface px-3 py-2 text-sm text-ink shadow-sm focus-visible:ring-2 focus-visible:ring-ring/40"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <Button variant="outline" size="icon" aria-label="Filters">
            <SlidersHorizontal className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Search bar */}
      <div className="relative mt-6">
        <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" />
        <Input
          placeholder="Search products, brands, categories…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="pl-11"
        />
      </div>

      {/* Filter chips */}
      <div className="mt-4 flex flex-wrap gap-2">
        {["fresh", "bakery", "fruit"].map((f) => (
          <button
            key={f}
            onClick={() => setFreshness(freshness === f ? "" : f)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              freshness === f
                ? "bg-primary text-primary-foreground"
                : "border border-border bg-surface text-ink-muted hover:bg-surface-muted"
            }`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
        <label className="flex cursor-pointer items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium text-ink-muted hover:bg-surface-muted">
          <input
            type="checkbox"
            checked={availableOnly}
            onChange={(e) => setAvailableOnly(e.target.checked)}
            className="accent-primary"
          />
          In stock only
        </label>
      </div>

      {/* Product grid */}
      {loading ? (
        <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="rounded-2xl border border-border bg-surface p-4">
              <div className="aspect-square rounded-xl bg-surface-muted animate-pulse" />
              <div className="mt-3 h-4 w-3/4 rounded bg-surface-muted animate-pulse" />
              <div className="mt-2 h-4 w-1/4 rounded bg-surface-muted animate-pulse" />
            </div>
          ))}
        </div>
      ) : products.length === 0 ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mt-12 flex flex-col items-center text-center"
        >
          <p className="text-ink-muted">No products match your search.</p>
          <Button variant="link" onClick={() => { setQuery(""); setCategory(""); setFreshness(""); }}>
            Clear filters
          </Button>
        </motion.div>
      ) : (
        <motion.div
          className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
        >
          {products.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </motion.div>
      )}
    </div>
  )
}