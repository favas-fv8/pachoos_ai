import { useState, useEffect, useCallback } from "react"
import { useSearchParams } from "react-router-dom"
import { motion } from "framer-motion"
import { Search } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ProductCard } from "@/components/product/ProductCard"
import { BackButton } from "@/components/ui/back-button"
import { api, fetchListAll } from "@/lib/api/client"
import { usePolling } from "@/hooks/usePolling"
import type { Product } from "@/types"

const SORT_OPTIONS = [
  { value: "popularity", label: "Popular" },
  { value: "newest", label: "Newest" },
  { value: "price_asc", label: "Price: Low → High" },
  { value: "price_desc", label: "Price: High → Low" },
  { value: "discount", label: "Discount" },
  { value: "rating", label: "Rating" },
]

/** Category fields served by the public catalog endpoint. */
interface ShopCategory {
  id: number
  name: string
  slug: string
}

export default function Shop() {
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<ShopCategory[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState("")
  const [sortBy, setSortBy] = useState("popularity")
  const [category, setCategory] = useState("")
  const [total, setTotal] = useState(0)
  const [searchParams] = useSearchParams()

  // Deep links like /shop?category=<slug> (Home "Shop by category" cards)
  // drive the category filter — the slug maps 1:1 to the admin-created
  // category on the backend.
  const categoryParam = searchParams.get("category") ?? ""
  useEffect(() => {
    setCategory(categoryParam)
  }, [categoryParam])

  // Live admin-managed categories — created/removed in /admin/products show
  // up here automatically (chips key off the same slug the products API
  // filters by, so every category maps to exactly its own products).
  const loadCategories =
    useCallback(async (): Promise<ShopCategory[] | null> => {
      try {
        const cats = await fetchListAll<ShopCategory>(
          "/api/v1/catalog/categories/",
        )
        setCategories(cats)
        // Drop a selection whose category was removed/deactivated by the
        // Admin, so the grid never stays stuck on an empty dead filter.
        setCategory((current) =>
          current && !cats.some((c) => c.slug === current) ? "" : current,
        )
        return cats
      } catch {
        return null
      }
    }, [])

  useEffect(() => {
    void loadCategories()
  }, [loadCategories])

  const fetchProducts = async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const params = new URLSearchParams()
      if (query) params.set("q", query)
      if (category) params.set("category", category)
      params.set("sort_by", sortBy)

      const res = await api.get(`/api/v1/catalog/products/?${params.toString()}`)
      setProducts(res.data.results)
      setTotal(res.data.count)
    } catch {
      // fallback to empty — real data arrives when backend is live
      if (!silent) setProducts([])
    } finally {
      if (!silent) setLoading(false)
    }
  }

  useEffect(() => {
    const debounce = setTimeout(() => void fetchProducts(), 300)
    return () => clearTimeout(debounce)
  }, [query, sortBy, category])

  // Silent refresh so admin price/stock/category changes reach the shop
  // without any user interaction.
  usePolling(() => {
    void loadCategories()
    void fetchProducts(true)
  }, 15000)

  return (
    <div className="container-px mx-auto py-8">
      <BackButton to="/" className="mb-4" />
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

      {/* Category filters — live from the admin-managed catalog */}
      {categories.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {categories.map((cat) => {
            const isActive = category === cat.slug
            return (
              <button
                key={cat.id}
                onClick={() => setCategory(isActive ? "" : cat.slug)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "border border-border bg-surface text-ink-muted hover:bg-surface-muted"
                }`}
              >
                {cat.name}
              </button>
            )
          })}
        </div>
      )}

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
          <Button variant="link" onClick={() => { setQuery(""); setCategory(""); }}>
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