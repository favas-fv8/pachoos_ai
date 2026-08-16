import { useState, useEffect, useCallback } from "react"
import { api, toApiError } from "@/lib/api/client"
import { useAppSelector } from "@/store/hooks"

let cachedIds: Set<number> | null = null
let fetchPromise: Promise<Set<number>> | null = null

function fetchWishlistIds(): Promise<Set<number>> {
  if (fetchPromise) return fetchPromise
  fetchPromise = api
    .get("/api/v1/catalog/wishlist/")
    .then((res) => new Set<number>(res.data.map((item: { product: number }) => item.product)))
    .catch(() => new Set<number>())
    .finally(() => {
      fetchPromise = null
    })
  return fetchPromise
}

export function useWishlist() {
  const isAuthenticated = useAppSelector((s) => s.auth.isAuthenticated)
  const [wishlistIds, setWishlistIds] = useState<Set<number>>(cachedIds ?? new Set())

  useEffect(() => {
    if (!isAuthenticated) {
      setWishlistIds(new Set())
      cachedIds = null
      return
    }
    if (cachedIds) {
      setWishlistIds(new Set(cachedIds))
      return
    }
    fetchWishlistIds().then((ids) => {
      cachedIds = ids
      setWishlistIds(new Set(ids))
    })
  }, [isAuthenticated])

  const toggleWishlist = useCallback(
    async (productId: number): Promise<{ success: boolean; error?: string }> => {
      const isCurrentlyWishlisted = wishlistIds.has(productId)

      // Optimistic update
      const newIds = new Set(wishlistIds)
      if (isCurrentlyWishlisted) {
        newIds.delete(productId)
      } else {
        newIds.add(productId)
      }
      setWishlistIds(newIds)
      cachedIds = newIds

      try {
        if (isCurrentlyWishlisted) {
          await api.delete(`/api/v1/catalog/wishlist/${productId}/`)
        } else {
          await api.post("/api/v1/catalog/wishlist/", { product_id: productId })
        }
        return { success: true }
      } catch (err) {
        // Revert on error
        setWishlistIds(wishlistIds)
        cachedIds = wishlistIds
        return { success: false, error: toApiError(err).message }
      }
    },
    [wishlistIds],
  )

  const isWishlisted = useCallback((productId: number) => wishlistIds.has(productId), [wishlistIds])

  return { wishlistIds, toggleWishlist, isWishlisted }
}
