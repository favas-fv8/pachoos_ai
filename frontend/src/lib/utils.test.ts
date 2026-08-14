import { describe, expect, it } from 'vitest'
import { formatRating } from '@/lib/utils'

describe('formatRating', () => {
  it('formats a valid numeric rating', () => {
    expect(formatRating(4.5, 12)).toBe('4.5')
    expect(formatRating(4, 1)).toBe('4.0')
  })

  it('handles string numeric ratings', () => {
    expect(formatRating('4.5', 12)).toBe('4.5')
    expect(formatRating('4', 1)).toBe('4.0')
  })

  it('returns "No ratings" for null/undefined ratings', () => {
    expect(formatRating(null, 1)).toBe('No ratings')
    expect(formatRating(undefined, 1)).toBe('No ratings')
  })

  it('returns "No ratings" for non-numeric strings', () => {
    expect(formatRating('abc', 1)).toBe('No ratings')
    expect(formatRating('', 1)).toBe('No ratings')
  })

  it('returns "No ratings" for products with no reviews', () => {
    expect(formatRating(0, 0)).toBe('No ratings')
    expect(formatRating(4.5, 0)).toBe('No ratings')
    expect(formatRating(undefined, undefined)).toBe('No ratings')
  })

  it('returns "No ratings" for zero or negative ratings', () => {
    expect(formatRating(0, 3)).toBe('No ratings')
    expect(formatRating(-1, 3)).toBe('No ratings')
  })
})