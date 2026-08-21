// Shared admin catalog components — product table/form, category form.
// Used by both the Products page and the Categories drill-down page so both
// admins manage the same data through the same UI (single source of truth).
import { useEffect, useMemo, useState } from 'react'
import { Loader2, Pencil, Plus, Save, Trash2, X, ImagePlus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { api, toApiError } from '@/lib/api/client'
import { stockUnitLabel } from './constants'
import type { AdminProduct, Category, ProductVariant } from '@/types'

/** Variant row in the admin product form — id is absent for newly added rows. */
type VariantDraft = Omit<ProductVariant, 'id'> & { id?: number }

// ─── Image upload rules (mirror the backend validation) ────────────────────

/** Formats accepted by the backend image upload endpoints. */
const IMAGE_ACCEPT = 'image/jpeg,image/png,image/webp'
const IMAGE_ACCEPT_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const IMAGE_ACCEPT_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']
/** Size ceiling enforced by the backend (DATA_UPLOAD_MAX_MEMORY_SIZE = 10 MB). */
const IMAGE_MAX_BYTES = 10 * 1024 * 1024

function validateImageFile(file: File): string | null {
  const ext = `.${file.name.split('.').pop()?.toLowerCase() ?? ''}`
  const typeOk = IMAGE_ACCEPT_TYPES.includes(file.type)
  const extOk = IMAGE_ACCEPT_EXTENSIONS.includes(ext)
  if (!typeOk && !extOk) {
    return 'Unsupported image type. Use JPG, JPEG, PNG or WEBP.'
  }
  if (file.size > IMAGE_MAX_BYTES) {
    return `Image is too large (${(file.size / (1024 * 1024)).toFixed(1)} MB). Maximum size is ${IMAGE_MAX_BYTES / (1024 * 1024)} MB.`
  }
  return null
}

// ─── Status toggle ─────────────────────────────────────────────────────────

export function StatusToggle({
  active,
  onChange,
  busy,
}: {
  active: boolean
  onChange: () => void
  busy?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onChange}
      disabled={busy}
      aria-label={active ? 'Deactivate' : 'Activate'}
      className="inline-flex items-center gap-2 disabled:opacity-50"
    >
      <span
        className={`relative h-5 w-9 rounded-full transition-colors ${
          active ? 'bg-success' : 'bg-ink-subtle'
        }`}
      >
        <span
          className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all ${
            active ? 'left-[18px]' : 'left-0.5'
          }`}
        />
      </span>
      {busy ? <Loader2 className="h-3 w-3 animate-spin text-ink-muted" /> : null}
    </button>
  )
}

export function ActiveBadge({ active }: { active: boolean }) {
  return <Badge variant={active ? 'success' : 'danger'}>{active ? 'Active' : 'Inactive'}</Badge>
}

// ─── Category form ─────────────────────────────────────────────────────────

export function CategoryForm({
  category,
  onSaved,
  onClose,
  onError,
}: {
  category: Pick<Category, 'id' | 'name' | 'description' | 'image_url' | 'is_active'> | null
  onSaved: () => void
  onClose: () => void
  onError: (msg: string) => void
}) {
  const [name, setName] = useState(category?.name ?? '')
  const [description, setDescription] = useState(category?.description ?? '')
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(
    category?.image_url ?? null,
  )
  const [isActive, setIsActive] = useState(category?.is_active ?? true)
  const [saving, setSaving] = useState(false)

  const selectFile = (file: File | null) => {
    if (!file) {
      setImageFile(null)
      setImagePreview(category?.image_url ?? null)
      return
    }
    const error = validateImageFile(file)
    if (error) {
      onError(error)
      return
    }
    setImageFile(file)
    const reader = new FileReader()
    reader.onload = () => setImagePreview(String(reader.result))
    reader.readAsDataURL(file)
  }

  const handleSave = async () => {
    if (!name.trim()) {
      onError('Category name is required.')
      return
    }
    setSaving(true)
    try {
      const payload = { name: name.trim(), description, is_active: isActive }
      let categoryId = category?.id
      if (category) {
        await api.patch(`/api/v1/catalog/admin/categories/${category.id}/`, payload)
      } else {
        const res = await api.post('/api/v1/catalog/admin/categories/', payload)
        categoryId = res.data.id
      }
      if (imageFile && categoryId) {
        const fd = new FormData()
        fd.append('image', imageFile)
        await api.post(`/api/v1/catalog/admin/categories/${categoryId}/image/`, fd)
      }
      onSaved()
    } catch (err) {
      onError(toApiError(err).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mb-6 rounded-2xl border border-border bg-surface p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-semibold">{category ? 'Edit Category' : 'Add Category'}</h3>
        <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="mb-4 flex items-center gap-4">
        <div className="grid h-16 w-16 place-items-center overflow-hidden rounded-xl border border-border bg-ink-subtle">
          {imagePreview ? (
            <img src={imagePreview} alt="Category preview" className="h-full w-full object-cover" />
          ) : (
            <ImagePlus className="h-5 w-5 text-ink-muted" />
          )}
        </div>
        <div className="text-sm">
          <label className="block text-xs text-ink-muted">Category image</label>
          <label className="mt-1 inline-flex cursor-pointer items-center gap-1 rounded-lg border border-border bg-surface-muted px-3 py-1.5 text-sm text-ink hover:bg-ink-subtle">
            <ImagePlus className="h-4 w-4" />
            {imageFile ? imageFile.name : 'Choose image'}
            <input
              type="file"
              accept={IMAGE_ACCEPT}
              className="hidden"
              onChange={(e) => selectFile(e.target.files?.[0] ?? null)}
            />
          </label>
          {imagePreview && (
            <button type="button" onClick={() => selectFile(null)} className="ml-2 text-xs text-danger">
              Remove
            </button>
          )}
          <p className="mt-1 text-xs text-ink-muted">JPG, JPEG, PNG or WEBP · max 10 MB</p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-xs text-ink-muted">Category name</span>
          <Input placeholder="e.g. Fresh Produce" value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="block sm:col-span-2">
          <span className="mb-1 block text-xs text-ink-muted">Description</span>
          <Input
            placeholder="Optional short description of this category"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <span className="text-sm text-ink-muted">Active</span>
        <StatusToggle
          active={isActive}
          onChange={() => setIsActive((v) => !v)}
        />
      </div>
      <div className="mt-4 flex gap-2">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Save className="mr-1 h-4 w-4" />}
          {category ? 'Update' : 'Create'}
        </Button>
        <Button variant="outline" onClick={onClose}>Cancel</Button>
      </div>
    </div>
  )
}

// ─── Product variants editor ───────────────────────────────────────────────

export function VariantEditor({
  variants,
  onChange,
}: {
  variants: VariantDraft[]
  onChange: (variants: VariantDraft[]) => void
}) {
  const update = (index: number, patch: Partial<VariantDraft>) => {
    const next = variants.map((v, i) => (i === index ? { ...v, ...patch } : v))
    onChange(next)
  }

  const remove = (index: number) => onChange(variants.filter((_, i) => i !== index))

  const add = () =>
    onChange([
      ...variants,
      {
        id: undefined,
        name: '',
        sku: '',
        price: 0,
        discount_percent: 0,
        effective_price: 0,
        stock_quantity: 0,
        is_active: true,
      },
    ])

  return (
    <div className="sm:col-span-2">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs text-ink-muted">Variants (size / weight)</span>
        <Button variant="outline" size="sm" type="button" onClick={add}>
          <Plus className="mr-1 h-4 w-4" /> Add variant
        </Button>
      </div>
      <p className="mb-2 text-xs text-ink-muted">
        Variants share the product's price and stock set above.
      </p>
      {variants.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border bg-surface-muted px-3 py-3 text-sm text-ink-muted">
          No variants. The product sells as a single unit.
        </p>
      ) : (
        <div className="space-y-3">
          {variants.map((v, i) => (
            <div key={v.id ?? i} className="rounded-xl border border-border bg-surface-muted p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-xs text-ink-muted">Variant {i + 1}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  type="button"
                  onClick={() => remove(i)}
                  aria-label={`Remove variant ${v.name || i + 1}`}
                >
                  <Trash2 className="h-4 w-4 text-danger" />
                </Button>
              </div>
              <div className="grid gap-2 sm:col-span-2 sm:grid-cols-3">
                <label className="block">
                  <span className="mb-1 block text-xs text-ink-muted">Name</span>
                  <Input
                    placeholder="e.g. 200g"
                    value={v.name}
                    onChange={(e) => update(i, { name: e.target.value })}
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-xs text-ink-muted">SKU</span>
                  <Input
                    placeholder="SKU"
                    value={v.sku}
                    onChange={(e) => update(i, { sku: e.target.value })}
                  />
                </label>
                <label className="flex items-end gap-2 pb-2 text-sm text-ink-muted">
                  <input
                    type="checkbox"
                    className="h-4 w-4"
                    checked={v.is_active}
                    onChange={(e) => update(i, { is_active: e.target.checked })}
                  />
                  Active
                </label>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Product form ──────────────────────────────────────────────────────────

export function ProductForm({
  product,
  categories,
  defaultCategoryId,
  defaultSubcategoryId,
  onSaved,
  onClose,
  onError,
}: {
  product: AdminProduct | null
  categories: Category[]
  defaultCategoryId?: number
  defaultSubcategoryId?: number
  onSaved: () => void
  onClose: () => void
  onError: (msg: string) => void
}) {
  const [form, setForm] = useState<{
  name: string
  pid: string
  subcategory: number
  base_price: string
  selling_price: string
  discount_percent: string
  stock_quantity: number
  stock_unit: 'kg' | 'count'
  is_available: boolean
  description: string
  freshness: string
  brand: string
  sku: string
  ingredients: string
  tags: string
  nutritional_info: string
  variants: VariantDraft[]
}>({
    name: product?.name ?? '',
    pid: product?.pid ?? '',
    subcategory: product?.subcategory ?? defaultSubcategoryId ?? 0,
    base_price: product?.base_price ?? '',
    selling_price: product?.selling_price ?? '',
    discount_percent: product?.discount_percent ?? '',
    stock_quantity: product?.stock_quantity ?? 0,
    stock_unit: product?.stock_unit ?? 'count',
    is_available: product?.is_available ?? true,
    description: product?.description ?? '',
    freshness: product?.freshness ?? 'fresh',
    brand: product?.brand ?? '',
    sku: product?.sku ?? '',
    ingredients: product?.ingredients ?? '',
    tags: (product?.tags ?? []).map((t) => t.name).join(', '),
    nutritional_info: product?.nutritional_info
      ? JSON.stringify(product.nutritional_info, null, 2)
      : '',
    variants: product?.variants ?? [],
  })
  const [categoryId, setCategoryId] = useState<number>(
    product?.category ?? defaultCategoryId ?? (categories[0]?.id as number | undefined) ?? 0,
  )
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(
    product?.images[0]?.image_url ?? null,
  )
  const [saving, setSaving] = useState(false)

  const subcategories = useMemo(
    () => categories.find((c) => c.id === categoryId)?.subcategories ?? [],
    [categories, categoryId],
  )

  useEffect(() => {
    // Keep the selected subcategory valid when the category changes.
    const ids = subcategories.map((s) => s.id)
    if (form.subcategory && !ids.includes(form.subcategory)) {
      setForm((f) => ({ ...f, subcategory: ids[0] ?? 0 }))
    }
  }, [subcategories, form.subcategory])

  const selectFile = (file: File | null) => {
    if (!file) {
      setImageFile(null)
      setImagePreview(product?.images[0]?.image_url ?? null)
      return
    }
    const error = validateImageFile(file)
    if (error) {
      onError(error)
      return
    }
    setImageFile(file)
    const reader = new FileReader()
    reader.onload = () => setImagePreview(String(reader.result))
    reader.readAsDataURL(file)
  }

  const uploadImage = async (productId: number) => {
    if (!imageFile) return
    const fd = new FormData()
    fd.append('image', imageFile)
    fd.append('is_primary', 'true')
    await api.post(`/api/v1/catalog/admin/products/${productId}/images/`, fd)
  }

  const handleSave = async () => {
    if (!form.name.trim() || !form.subcategory) {
      onError('Product name and subcategory are required.')
      return
    }
    const real = parseFloat(form.base_price)
    const selling = form.selling_price !== '' ? parseFloat(form.selling_price) : real
    if (Number.isNaN(real) || real < 0) {
      onError('Enter a valid real price.')
      return
    }
    const discount = real > 0 ? Math.round((1 - selling / real) * 10000) / 100 : 0

    let tags: string[] = []
    if (form.tags.trim()) {
      tags = form.tags
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean)
    }

    let nutritional_info: Record<string, unknown> | null = null
    if (form.nutritional_info.trim()) {
      try {
        const parsed = JSON.parse(form.nutritional_info)
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
          onError('Nutritional info must be a JSON object.')
          return
        }
        nutritional_info = parsed
      } catch {
        onError('Nutritional info must be valid JSON.')
        return
      }
    }

    setSaving(true)
    try {
      const payload = {
        name: form.name.trim(),
        pid: form.pid.trim() || undefined,
        subcategory: form.subcategory,
        description: form.description,
        base_price: real,
        discount_percent: discount,
        stock_quantity: Number(form.stock_quantity) || 0,
        stock_unit: form.stock_unit,
        is_available: form.is_available,
        freshness: form.freshness,
        brand: form.brand.trim(),
        sku: form.sku.trim(),
        ingredients: form.ingredients,
        tags,
        nutritional_info,
        variants: form.variants.map((v) => ({
          id: v.id ?? undefined,
          name: v.name,
          sku: v.sku,
          is_active: v.is_active,
        })),
      }
      if (product) {
        await api.patch(`/api/v1/catalog/admin/products/${product.id}/`, payload)
        if (imageFile) await uploadImage(product.id)
      } else {
        const res = await api.post('/api/v1/catalog/admin/products/', payload)
        if (imageFile) await uploadImage(res.data.id)
      }
      onSaved()
    } catch (err) {
      onError(toApiError(err).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mb-6 rounded-2xl border border-border bg-surface p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-semibold">{product ? 'Edit Product' : 'Add Product'}</h3>
        <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="mb-4 flex items-center gap-4">
        <div className="grid h-16 w-16 place-items-center overflow-hidden rounded-xl border border-border bg-ink-subtle">
          {imagePreview ? (
            <img src={imagePreview} alt="Product preview" className="h-full w-full object-cover" />
          ) : (
            <ImagePlus className="h-5 w-5 text-ink-muted" />
          )}
        </div>
        <div className="text-sm">
          <label className="block text-xs text-ink-muted">Product image</label>
          <label className="mt-1 inline-flex cursor-pointer items-center gap-1 rounded-lg border border-border bg-surface-muted px-3 py-1.5 text-sm text-ink hover:bg-ink-subtle">
            <ImagePlus className="h-4 w-4" />
            {imageFile ? imageFile.name : 'Choose image'}
            <input
              type="file"
              accept={IMAGE_ACCEPT}
              className="hidden"
              onChange={(e) => selectFile(e.target.files?.[0] ?? null)}
            />
          </label>
          {imagePreview && (
            <button type="button" onClick={() => selectFile(null)} className="ml-2 text-xs text-danger">
              Remove
            </button>
          )}
          <p className="mt-1 text-xs text-ink-muted">JPG, JPEG, PNG or WEBP · max 10 MB</p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-xs text-ink-muted">Product name</span>
          <Input placeholder="e.g. Fresh Tomatoes" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-ink-muted">PID (optional)</span>
          <Input placeholder="Unique product code" value={form.pid} onChange={(e) => setForm({ ...form, pid: e.target.value })} />
        </label>

        <label className="block">
          <span className="mb-1 block text-xs text-ink-muted">Category</span>
          <select
            className="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-ink"
            value={categoryId}
            onChange={(e) => setCategoryId(Number(e.target.value))}
          >
            <option value={0} disabled>Select category</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-ink-muted">Subcategory</span>
          <select
            className="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-ink"
            value={form.subcategory}
            onChange={(e) => setForm({ ...form, subcategory: Number(e.target.value) })}
          >
            <option value={0} disabled>Select subcategory</option>
            {subcategories.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
          {subcategories.length === 0 && (
            <span className="mt-1 block text-xs text-warning">Add a subcategory to this category first.</span>
          )}
        </label>

        <label className="block">
          <span className="mb-1 block text-xs text-ink-muted">Real price (₹)</span>
          <Input
            type="number"
            placeholder="0.00"
            value={form.base_price}
            onChange={(e) => setForm({ ...form, base_price: e.target.value })}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-ink-muted">Selling price (₹)</span>
          <Input
            type="number"
            placeholder="0.00"
            value={form.selling_price}
            onChange={(e) => setForm({ ...form, selling_price: e.target.value })}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-ink-muted">Stock quantity</span>
          <Input
            type="number"
            placeholder="0"
            value={form.stock_quantity}
            onChange={(e) => setForm({ ...form, stock_quantity: Number(e.target.value) })}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-ink-muted">Stock unit</span>
          <select
            className="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-ink"
            value={form.stock_unit}
            onChange={(e) => setForm({ ...form, stock_unit: e.target.value as 'kg' | 'count' })}
          >
            <option value="kg">kg (weight-based)</option>
            <option value="count">count (piece-based)</option>
          </select>
        </label>
        <label className="block sm:col-span-2">
          <span className="mb-1 block text-xs text-ink-muted">Description</span>
          <Input
            placeholder="Optional product description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-ink-muted">Brand (optional)</span>
          <Input
            placeholder="e.g. Organic Farms"
            value={form.brand}
            onChange={(e) => setForm({ ...form, brand: e.target.value })}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-ink-muted">SKU (optional)</span>
          <Input
            placeholder="Stock keeping unit"
            value={form.sku}
            onChange={(e) => setForm({ ...form, sku: e.target.value })}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-ink-muted">Freshness</span>
          <select
            className="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-ink"
            value={form.freshness}
            onChange={(e) => setForm({ ...form, freshness: e.target.value })}
          >
            <option value="fresh">Fresh</option>
            <option value="frozen">Frozen</option>
            <option value="bakery">Bakery</option>
            <option value="dry">Dry</option>
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-ink-muted">Tags (comma separated)</span>
          <Input
            placeholder="e.g. organic, new, bestseller"
            value={form.tags}
            onChange={(e) => setForm({ ...form, tags: e.target.value })}
          />
        </label>
        <label className="block sm:col-span-2">
          <span className="mb-1 block text-xs text-ink-muted">Ingredients (optional)</span>
          <Input
            placeholder="Comma-separated ingredients"
            value={form.ingredients}
            onChange={(e) => setForm({ ...form, ingredients: e.target.value })}
          />
        </label>
        <label className="block sm:col-span-2">
          <span className="mb-1 block text-xs text-ink-muted">Nutritional info (optional)</span>
          <textarea
            placeholder={'JSON object, e.g. {"calories":"200 kcal","protein":"5g"}'}
            className="min-h-20 w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm text-ink"
            value={form.nutritional_info}
            onChange={(e) => setForm({ ...form, nutritional_info: e.target.value })}
          />
        </label>
        <VariantEditor
          variants={form.variants}
          onChange={(variants) => setForm((f) => ({ ...f, variants }))}
        />
      </div>

      <div className="mt-4 flex items-center gap-3">
        <span className="text-sm text-ink-muted">Available for sale</span>
        <StatusToggle
          active={form.is_available}
          onChange={() => setForm((f) => ({ ...f, is_available: !f.is_available }))}
        />
      </div>

      <div className="mt-4 flex gap-2">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Save className="mr-1 h-4 w-4" />}
          {product ? 'Update' : 'Create'}
        </Button>
        <Button variant="outline" onClick={onClose}>Cancel</Button>
      </div>
    </div>
  )
}

// ─── Product table ─────────────────────────────────────────────────────────

export function ProductTable({
  products,
  loading,
  onEdit,
  onDelete,
  onStatusChange,
  onStockChange,
}: {
  products: AdminProduct[]
  loading?: boolean
  onEdit: (product: AdminProduct) => void
  onDelete: (product: AdminProduct) => void
  onStatusChange: (product: AdminProduct, active: boolean) => void
  onStockChange: (product: AdminProduct, quantity: number) => Promise<void>
}) {
  const [busy, setBusy] = useState<Record<string, string>>({})

  const handleStock = async (product: AdminProduct, value: string) => {
    const qty = Number(value)
    if (Number.isNaN(qty)) return
    setBusy((b) => ({ ...b, [product.id]: 'stock' }))
    try {
      await onStockChange(product, qty)
    } finally {
      setBusy((b) => {
        const next = { ...b }
        delete next[product.id]
        return next
      })
    }
  }

  return (
    <div className="rounded-2xl border border-border bg-surface overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-ink-subtle">
          <tr>
            <th className="px-4 py-3 text-left font-medium">Image</th>
            <th className="px-4 py-3 text-left font-medium">Name / PID</th>
            <th className="px-4 py-3 text-left font-medium">Real Price</th>
            <th className="px-4 py-3 text-left font-medium">Selling Price</th>
            <th className="px-4 py-3 text-left font-medium">Stock</th>
            <th className="px-4 py-3 text-left font-medium">Status</th>
            <th className="px-4 py-3 text-right font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr><td colSpan={7} className="px-4 py-10 text-center text-ink-muted">Loading…</td></tr>
          ) : products.length === 0 ? (
            <tr><td colSpan={7} className="px-4 py-10 text-center text-ink-muted">No products found.</td></tr>
          ) : (
            products.map((p) => (
              <tr key={p.id} className="border-t border-border">
                <td className="px-4 py-3">
                  <div className="grid h-11 w-11 place-items-center overflow-hidden rounded-lg border border-border bg-ink-subtle">
                    {p.images[0]?.image_url ? (
                      <img src={p.images[0].image_url} alt={p.name} className="h-full w-full object-cover" />
                    ) : (
                      <span className="text-xs text-ink-muted">—</span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <p className="font-medium">{p.name}</p>
                  <p className="text-xs text-ink-muted">
                    {p.pid} {p.category_name ? `• ${p.category_name}` : ''}
                  </p>
                </td>
                <td className="px-4 py-3">₹{p.base_price}</td>
                <td className="px-4 py-3 font-semibold">₹{p.selling_price}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      className="w-16 rounded-lg border border-border bg-background px-2 py-1 text-sm"
                      defaultValue={p.stock_quantity}
                      onBlur={(e) => {
                        if (Number(e.target.value) !== p.stock_quantity) void handleStock(p, e.target.value)
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
                      }}
                      aria-label={`Update stock for ${p.name}`}
                    />
                    <span className="text-xs text-ink-muted">{stockUnitLabel(p.stock_unit)}</span>
                    {busy[p.id] === 'stock' ? <Loader2 className="h-3 w-3 animate-spin text-ink-muted" /> : null}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <ActiveBadge active={p.is_available} />
                    <StatusToggle
                      active={p.is_available}
                      busy={busy[p.id] === 'status'}
                      onChange={() => onStatusChange(p, !p.is_available)}
                    />
                  </div>
                </td>
                <td className="px-4 py-3 text-right">
                  <Button variant="ghost" size="sm" onClick={() => onEdit(p)} aria-label={`Edit ${p.name}`}>
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => onDelete(p)} aria-label={`Delete ${p.name}`}>
                    <Trash2 className="h-4 w-4 text-danger" />
                  </Button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}

// ─── Add button (dynamic "+") ──────────────────────────────────────────────

export function AddButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <Button onClick={onClick}>
      <Plus className="mr-1 h-4 w-4" /> {label}
    </Button>
  )
}
