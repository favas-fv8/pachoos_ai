import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatINR(amount: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: amount % 1 === 0 ? 0 : 2,
  }).format(amount)
}

export function formatDistanceKm(km: number): string {
  return `${km.toFixed(1)} km`
}

/**
 * Format a product average rating for display.
 * Accepts numeric or string ratings and gracefully falls back to "No ratings"
 * for null/undefined/invalid values and products with no reviews.
 */
export function formatRating(
  rating: number | string | null | undefined,
  ratingCount?: number | null,
): string {
  if (ratingCount !== undefined && ratingCount !== null && ratingCount <= 0) {
    return "No ratings"
  }
  const num = typeof rating === "number" ? rating : Number(rating)
  if (
    rating === null ||
    rating === undefined ||
    rating === "" ||
    Number.isNaN(num) ||
    !Number.isFinite(num) ||
    num <= 0
  ) {
    return "No ratings"
  }
  return num.toFixed(1)
}

export function getInitials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')
}
