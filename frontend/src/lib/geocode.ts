export interface DeliveryAddress {
  label: string
  full: string
  lat: number
  lon: number
  placeId: string
}

interface NominatimResult {
  place_id: number
  display_name: string
  lat: string
  lon: string
  address?: Record<string, string>
}

const NOMINATIM_BASE = 'https://nominatim.openstreetmap.org'

const toAddress = (r: NominatimResult): DeliveryAddress => ({
  label: shortLabel(r),
  full: r.display_name,
  lat: Number(r.lat),
  lon: Number(r.lon),
  placeId: String(r.place_id),
})

function shortLabel(r: NominatimResult): string {
  const a = r.address
  if (!a) return r.display_name
  const parts = [a.road, a.suburb, a.city || a.town || a.village, a.state, a.country].filter(Boolean)
  return parts.slice(0, 3).join(', ')
}

async function nominatim<T>(path: string, params: Record<string, string>): Promise<T> {
  const url = new URL(path, NOMINATIM_BASE)
  for (const [key, value] of Object.entries(params)) url.searchParams.set(key, value)
  const res = await fetch(url.toString(), {
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) throw new Error(`Geocoding request failed (${res.status})`)
  return (await res.json()) as T
}

/** Search places by free-text query (debounce before calling). */
export async function searchLocations(query: string): Promise<DeliveryAddress[]> {
  const trimmed = query.trim()
  if (trimmed.length < 3) return []
  const data = await nominatim<NominatimResult[] | { error?: string }>('/search', {
    format: 'jsonv2',
    addressdetails: '1',
    limit: '6',
    q: trimmed,
  })
  if (!Array.isArray(data)) return []
  return data.map(toAddress)
}

/** Turn a lat/lon pair into a human-readable address. */
export async function reverseGeocode(lat: number, lon: number): Promise<DeliveryAddress | null> {
  const data = await nominatim<NominatimResult | { error?: string }>('/reverse', {
    format: 'jsonv2',
    addressdetails: '1',
    lat: String(lat),
    lon: String(lon),
  })
  if (!data || 'error' in data || !('place_id' in data)) return null
  return toAddress(data as NominatimResult)
}

/** Browser geolocation — returns the device position (lat/lon). */
export function detectCurrentPosition(): Promise<{ lat: number; lon: number }> {
  return new Promise((resolve, reject) => {
    if (!('geolocation' in navigator)) {
      reject(new Error('Geolocation is not supported by this browser.'))
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      (err) => reject(new Error(geolocationErrorMessage(err.code))),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    )
  })
}

function geolocationErrorMessage(code: number): string {
  switch (code) {
    case 1:
      return 'Location permission was denied. Allow access to use auto-detect.'
    case 2:
      return 'Location is currently unavailable. Try again or search manually.'
    case 3:
      return 'Location request timed out. Try again or search manually.'
    default:
      return 'Could not detect your location.'
  }
}
