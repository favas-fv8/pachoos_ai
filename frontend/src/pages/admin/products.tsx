// Admin Products — the single shared catalog section for both admins.
// Merges category management, subcategory management and per-category product
// management into one place: a category grid that drills down into the products
// of the selected category (with search + filters, stock/status operations).
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Check, Pencil, Plus, RefreshCw, Search, Trash2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, toApiError } from '@/lib/api/client'
import { usePolling } from '@/hooks/usePolling'
import { Loader } from './shared'
import { BackButton } from '@/components/ui/back-button'
import {
  ActiveBadge,
  AddButton,
  CategoryForm,
  ProductForm,
  ProductTable,
  StatusToggle,
} from './catalog-components'
import type { AdminProduct, Category, Subcategory } from '@/types'

export default function AdminProducts() {
  // ── Data state ──────────────────────────────────────────────────────────
  const [categories, setCategories] = useState<Category[]>([])
  const [selected, setSelected] = useState<Category | null>(null)
  const [categoryProducts, setCategoryProducts] = useState<AdminProduct[]>([])
  const [loading, setLoading] = useState(true)
  const [productsLoading, setProductsLoading] = useState(false)
  const [error, setError] = useState('')
  const [productsError, setProductsError] = useState('')

  // ── Forms / editing state ───────────────────────────────────────────────
  const [editingCategory, setEditingCategory] = useState<Category | null>(null)
  const [showCategoryForm, setShowCategoryForm] = useState(false)
  const [editingProduct, setEditingProduct] = useState<AdminProduct | null>(null)
  const [showProductForm, setShowProductForm] = useState(false)
  const [subName, setSubName] = useState('')
  const [editingSubcat, setEditingSubcat] = useState<Subcategory | null>(null)
  const [editingSubcatName, setEditingSubcatName] = useState('')

  // ── Filters (category drill-down) ───────────────────────────────────────
  const [search, setSearch] = useState('')
  const [subcatFilter, setSubcatFilter] = useState(0)
  const [statusFilter, setStatusFilter] = useState('all')
  const [stockFilter, setStockFilter] = useState('all')
  const [minPrice, setMinPrice] = useState('')
  const [maxPrice, setMaxPrice] = useState('')

  // ── Race guards ─────────────────────────────────────────────────────────
  const productRequestSeq = useRef(0)
  const lastLoadedCategoryId = useRef<number | null>(null)

  const fetchCategories = useCallback(async () => {
    try {
      const res = await api.get('/api/v1/catalog/admin/categories/')
      const data = Array.isArray(res.data) ? res.data : res.data.results ?? []
      setCategories(data)
      if (selected) {
        const updated = data.find((c: Category) => c.id === selected.id)
        if (updated) setSelected(updated)
      }
      setError('')
    } catch {
      setError('Failed to load categories.')
    } finally {
      setLoading(false)
    }
  }, [selected])

  // Loads the products for the given category. `silent` keeps the current list
  // visible while refetching (no loader, no clearing) so background polls and
  // post-mutation refreshes never make the table flicker.
  const loadProducts = useCallback(async (categoryId: number, silent = false) => {
    const seq = ++productRequestSeq.current
    if (!silent) {
      setProductsLoading(true)
      setProductsError('')
    }
    try {
      const res = await api.get(`/api/v1/catalog/admin/categories/${categoryId}/products/`)
      if (seq !== productRequestSeq.current) return // stale response, ignore
      setCategoryProducts(res.data.results ?? res.data)
      setProductsError('')
    } catch {
      if (seq !== productRequestSeq.current) return
      if (!silent) setProductsError('Failed to load products. Please try again.')
    } finally {
      if (seq === productRequestSeq.current) setProductsLoading(false)
    }
  }, [])

  usePolling(fetchCategories, 20000)
  usePolling(() => {
    if (selected) void loadProducts(selected.id, true)
  }, 15000)

  // On category change (keyed by id, not object reference): drop stale products
  // immediately and load the new category's list.
  const selectedCategoryId = selected?.id ?? null
  useEffect(() => {
    if (selectedCategoryId === null) {
      lastLoadedCategoryId.current = null
      return
    }
    lastLoadedCategoryId.current = selectedCategoryId
    setCategoryProducts([])
    setProductsError('')
    void loadProducts(selectedCategoryId)
  }, [selectedCategoryId, loadProducts])

  const openCategory = (category: Category) => {
    setSelected(category)
    setShowCategoryForm(false)
    setShowProductForm(false)
    setSubcatFilter(0)
    if (lastLoadedCategoryId.current !== category.id) {
      lastLoadedCategoryId.current = category.id
      setCategoryProducts([])
      setProductsError('')
      setProductsLoading(true)
    }
  }

  // ── Filtered products within the drill-down ─────────────────────────────
  const filteredProducts = useMemo(() => {
    const q = search.toLowerCase()
    const min = minPrice === '' ? null : Number(minPrice)
    const max = maxPrice === '' ? null : Number(maxPrice)
    return categoryProducts.filter((p) => {
      if (
        q &&
        !p.name.toLowerCase().includes(q) &&
        !p.pid.toLowerCase().includes(q) &&
        !(p.sku || '').toLowerCase().includes(q)
      ) {
        return false
      }
      if (subcatFilter && p.subcategory !== subcatFilter) return false
      if (statusFilter === 'active' && !p.is_available) return false
      if (statusFilter === 'inactive' && p.is_available) return false
      if (stockFilter === 'in' && p.stock_quantity <= 0) return false
      if (stockFilter === 'out' && p.stock_quantity > 0) return false
      const selling = Number(p.selling_price)
      if (min !== null && selling < min) return false
      if (max !== null && selling > max) return false
      return true
    })
  }, [categoryProducts, search, subcatFilter, statusFilter, stockFilter, minPrice, maxPrice])

  // ── Category actions ────────────────────────────────────────────────────
  const handleDeleteCategory = async (category: Category) => {
    if (!confirm(`Delete category "${category.name}"?`)) return
    try {
      await api.delete(`/api/v1/catalog/admin/categories/${category.id}/`)
      setSelected(null)
    } catch (err) {
      setError(toApiError(err).message)
    }
    await fetchCategories()
  }

  const handleToggleCategory = async (category: Category) => {
    try {
      await api.patch(`/api/v1/catalog/admin/categories/${category.id}/`, {
        is_active: !category.is_active,
      })
      await fetchCategories()
    } catch (err) {
      setError(toApiError(err).message)
    }
  }

  // ── Subcategory actions ─────────────────────────────────────────────────
  const handleAddSubcategory = async () => {
    if (!selected || !subName.trim()) return
    try {
      await api.post(`/api/v1/catalog/admin/categories/${selected.id}/subcategories/`, {
        name: subName.trim(),
      })
      setSubName('')
      await fetchCategories()
    } catch (err) {
      setError(toApiError(err).message)
    }
  }

  const handleRenameSubcategory = async () => {
    if (!selected || !editingSubcat || !editingSubcatName.trim()) return
    try {
      await api.patch(
        `/api/v1/catalog/admin/categories/${selected.id}/subcategories/${editingSubcat.id}/`,
        { name: editingSubcatName.trim() },
      )
      setEditingSubcat(null)
      await fetchCategories()
    } catch (err) {
      setError(toApiError(err).message)
    }
  }

  const handleDeleteSubcategory = async (sub: Subcategory) => {
    if (!selected) return
    if (!confirm(`Delete subcategory "${sub.name}"? Products in it are kept safe.`)) return
    try {
      await api.delete(
        `/api/v1/catalog/admin/categories/${selected.id}/subcategories/${sub.id}/`,
      )
      await fetchCategories()
    } catch (err) {
      setError(toApiError(err).message)
    }
  }

  // ── Product actions ─────────────────────────────────────────────────────
  const handleDeleteProduct = async (product: AdminProduct) => {
    if (!confirm(`Delete product "${product.name}"?`)) return
    try {
      await api.delete(`/api/v1/catalog/admin/products/${product.id}/`)
      if (selected) void loadProducts(selected.id, true)
      void fetchCategories()
    } catch (err) {
      setError(toApiError(err).message)
    }
  }

  const handleStatusChange = async (product: AdminProduct, active: boolean) => {
    try {
      await api.patch(`/api/v1/catalog/admin/products/${product.id}/`, { is_available: active })
      if (selected) void loadProducts(selected.id, true)
    } catch (err) {
      setError(toApiError(err).message)
    }
  }

  const handleStockChange = async (product: AdminProduct, quantity: number) => {
    await api.post(`/api/v1/catalog/admin/products/${product.id}/stock/`, { quantity })
    if (selected) void loadProducts(selected.id, true)
  }

  const closeCategoryForm = () => {
    setShowCategoryForm(false)
    setEditingCategory(null)
  }

  const closeProductForm = () => {
    setShowProductForm(false)
    setEditingProduct(null)
  }

  // ── Category grid view ──────────────────────────────────────────────────
  if (!selected) {
    return (
      <div>
        <BackButton to="/admin/dashboard" homeTo="/admin/dashboard" storeTo="/shop" />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl font-bold">Products</h1>
            <p className="text-sm text-ink-muted">
              Manage categories, subcategories and products. Shared with the other admin.
            </p>
          </div>
          <div className="flex gap-2">
            <AddButton
              label="Category"
              onClick={() => { setEditingCategory(null); setShowCategoryForm((v) => !v) }}
            />
            <AddButton
              label="Product"
              onClick={() => { setEditingProduct(null); setShowProductForm(true) }}
            />
          </div>
        </div>

        {error && <div className="mt-4 rounded-xl bg-danger-muted p-3 text-sm text-danger">{error}</div>}

        {showCategoryForm && (
          <div className="mt-4">
            <BackButton label="Back to Categories" onClick={closeCategoryForm} homeTo="/admin/dashboard" storeTo="/shop" />
            <CategoryForm
              category={editingCategory}
              onSaved={() => { setShowCategoryForm(false); void fetchCategories() }}
              onClose={closeCategoryForm}
              onError={setError}
            />
          </div>
        )}

        {showProductForm && (
          <div className="mt-4">
            <BackButton label="Back to Categories" onClick={closeProductForm} homeTo="/admin/dashboard" storeTo="/shop" />
            <ProductForm
              product={editingProduct}
              categories={categories}
              onSaved={() => { setShowProductForm(false); void fetchCategories() }}
              onClose={closeProductForm}
              onError={setError}
            />
          </div>
        )}

        <div className="mt-4">
          {loading ? (
            <Loader />
          ) : categories.length === 0 ? (
            <p className="py-10 text-center text-ink-muted">No categories yet. Add your first one.</p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {categories.map((c) => (
                <div
                  key={c.id}
                  className="group rounded-2xl border border-border bg-surface p-5 shadow-card transition-shadow hover:shadow-pop"
                >
                  <button
                    type="button"
                    onClick={() => openCategory(c)}
                    className="w-full text-left"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="font-display text-lg font-semibold">{c.name}</h3>
                      <ActiveBadge active={c.is_active} />
                    </div>
                    <p className="mt-1 text-sm text-ink-muted">
                      {c.product_count} product{c.product_count === 1 ? '' : 's'}
                    </p>
                    {c.description && (
                      <p className="mt-1 line-clamp-2 text-xs text-ink-muted">{c.description}</p>
                    )}
                  </button>
                  <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
                    <StatusToggle active={c.is_active} onChange={() => handleToggleCategory(c)} />
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => { setEditingCategory(c); setShowCategoryForm(true) }}
                        aria-label={`Edit ${c.name}`}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteCategory(c)}
                        aria-label={`Delete ${c.name}`}
                      >
                        <Trash2 className="h-4 w-4 text-danger" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  // ── Category drill-down (products inside the category) ──────────────────
  return (
    <div>
      <BackButton label="Back to Categories" onClick={() => setSelected(null)} homeTo="/admin/dashboard" storeTo="/shop" />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-display text-2xl font-bold">{selected.name}</h1>
            <ActiveBadge active={selected.is_active} />
          </div>
          <p className="text-sm text-ink-muted">
            {selected.product_count} product{selected.product_count === 1 ? '' : 's'} in this category
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => { setEditingCategory(selected); setShowCategoryForm(true) }}
          >
            <Pencil className="mr-1 h-4 w-4" /> Edit Category
          </Button>
          <AddButton
            label="Product"
            onClick={() => { setEditingProduct(null); setShowProductForm(true) }}
          />
        </div>
      </div>

      {error && <div className="mt-4 rounded-xl bg-danger-muted p-3 text-sm text-danger">{error}</div>}

      {showCategoryForm && (
        <div className="mt-4">
          <BackButton label="Back to Products" onClick={closeCategoryForm} homeTo="/admin/dashboard" storeTo="/shop" />
          <CategoryForm
            category={selected}
            onSaved={() => { setShowCategoryForm(false); void fetchCategories() }}
            onClose={closeCategoryForm}
            onError={setError}
          />
        </div>
      )}

      {showProductForm && (
        <div className="mt-4">
          <BackButton label="Back to Products" onClick={closeProductForm} homeTo="/admin/dashboard" storeTo="/shop" />
          <ProductForm
            product={editingProduct}
            categories={categories}
            defaultCategoryId={selected.id}
            defaultSubcategoryId={editingProduct?.subcategory}
            onSaved={() => { setShowProductForm(false); void fetchCategories(); if (selected) void loadProducts(selected.id, true) }}
            onClose={closeProductForm}
            onError={setError}
          />
        </div>
      )}

      {/* Subcategory management */}
      <div className="mt-4 rounded-2xl border border-border bg-surface p-4">
        <BackButton label="Back to Categories" onClick={() => setSelected(null)} homeTo="/admin/dashboard" storeTo="/shop" />
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-ink-muted">Subcategories:</span>
          {selected.subcategories.map((s) =>
            editingSubcat?.id === s.id ? (
              <div key={s.id} className="flex items-center gap-1">
                <Input
                  className="h-8 w-44 rounded-full px-3 text-xs"
                  value={editingSubcatName}
                  onChange={(e) => setEditingSubcatName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') void handleRenameSubcategory()
                  }}
                  autoFocus
                />
                <Button size="sm" variant="ghost" onClick={handleRenameSubcategory} aria-label="Save subcategory">
                  <Check className="h-3 w-3 text-success" />
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setEditingSubcat(null)} aria-label="Cancel rename">
                  <X className="h-3 w-3" />
                </Button>
              </div>
            ) : (
              <span
                key={s.id}
                className="inline-flex items-center gap-1 rounded-full bg-ink-subtle px-3 py-1 text-xs font-medium"
              >
                {s.name}
                <button
                  type="button"
                  onClick={() => { setEditingSubcat(s); setEditingSubcatName(s.name) }}
                  aria-label={`Rename ${s.name}`}
                  className="text-ink-muted hover:text-ink"
                >
                  <Pencil className="h-3 w-3" />
                </button>
                <button
                  type="button"
                  onClick={() => handleDeleteSubcategory(s)}
                  aria-label={`Delete ${s.name}`}
                  className="text-ink-muted hover:text-danger"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </span>
            ),
          )}
          <div className="flex items-center gap-1">
            <Input
              placeholder="New subcategory…"
              value={subName}
              onChange={(e) => setSubName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void handleAddSubcategory()
              }}
              className="h-8 w-44 rounded-full px-3 text-xs"
            />
            <Button size="sm" variant="outline" onClick={handleAddSubcategory} aria-label="Add subcategory">
              <Plus className="h-3 w-3" />
            </Button>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-52">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" />
          <Input
            placeholder="Search products…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>
        <select
          className="h-11 rounded-xl border border-border bg-surface px-3 text-sm text-ink"
          value={subcatFilter}
          onChange={(e) => setSubcatFilter(Number(e.target.value))}
          aria-label="Filter by subcategory"
        >
          <option value={0}>All subcategories</option>
          {selected.subcategories.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
        <select
          className="h-11 rounded-xl border border-border bg-surface px-3 text-sm text-ink"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="Filter by status"
        >
          <option value="all">All statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
        <select
          className="h-11 rounded-xl border border-border bg-surface px-3 text-sm text-ink"
          value={stockFilter}
          onChange={(e) => setStockFilter(e.target.value)}
          aria-label="Filter by stock"
        >
          <option value="all">Any stock</option>
          <option value="in">In stock</option>
          <option value="out">Out of stock</option>
        </select>
        <div className="flex items-center gap-1">
          <Input
            type="number"
            placeholder="Min ₹"
            value={minPrice}
            onChange={(e) => setMinPrice(e.target.value)}
            className="h-11 w-24"
            aria-label="Minimum price"
          />
          <span className="text-ink-muted">–</span>
          <Input
            type="number"
            placeholder="Max ₹"
            value={maxPrice}
            onChange={(e) => setMaxPrice(e.target.value)}
            className="h-11 w-24"
            aria-label="Maximum price"
          />
        </div>
      </div>

      <div className="mt-4">
        {productsLoading && categoryProducts.length === 0 ? (
          <Loader />
        ) : productsError ? (
          <div className="flex flex-col items-center gap-3 rounded-2xl border border-danger/30 bg-danger-muted p-8 text-center">
            <p className="text-sm text-danger">{productsError}</p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setProductsError('')
                void loadProducts(selected.id)
              }}
            >
              <RefreshCw className="mr-1 h-4 w-4" /> Retry
            </Button>
          </div>
        ) : (
          <ProductTable
            products={filteredProducts}
            onEdit={(p) => { setEditingProduct(p); setShowProductForm(true) }}
            onDelete={handleDeleteProduct}
            onStatusChange={handleStatusChange}
            onStockChange={handleStockChange}
          />
        )}
        {!productsLoading && !productsError && categoryProducts.length > 0 && filteredProducts.length === 0 && (
          <p className="py-8 text-center text-sm text-ink-muted">No products match your filters.</p>
        )}
      </div>
    </div>
  )
}
