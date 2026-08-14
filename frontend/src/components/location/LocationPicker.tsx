import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { Loader2, LocateFixed, MapPin, Search, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAppDispatch, useAppSelector } from '@/store/hooks'
import { setDeliveryAddress, pushToast } from '@/store/slices/uiSlice'
import { detectCurrentPosition, reverseGeocode, searchLocations, type DeliveryAddress } from '@/lib/geocode'

const DEBOUNCE_MS = 350

export function LocationPicker({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const dispatch = useAppDispatch()
  const current = useAppSelector((s) => s.ui.deliveryAddress)

  const [query, setQuery] = useState('')
  const [results, setResults] = useState<DeliveryAddress[]>([])
  const [searching, setSearching] = useState(false)
  const [detecting, setDetecting] = useState(false)
  const [selected, setSelected] = useState<DeliveryAddress | null>(current)

  const queryRef = useRef(query)
  queryRef.current = query

  // Debounced autocomplete search.
  useEffect(() => {
    if (!open) return
    const trimmed = query.trim()
    if (trimmed.length < 3) {
      setResults([])
      return
    }
    setSearching(true)
    const timer = setTimeout(async () => {
      try {
        const found = await searchLocations(queryRef.current)
        if (queryRef.current === query) setResults(found)
      } catch {
        setResults([])
      } finally {
        if (queryRef.current === query) setSearching(false)
      }
    }, DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [query, open])

  useEffect(() => {
    if (open) setSelected(current)
  }, [open, current])

  const handleDetect = async () => {
    setDetecting(true)
    try {
      const pos = await detectCurrentPosition()
      const addr = await reverseGeocode(pos.lat, pos.lon)
      if (!addr) throw new Error('Could not find a nearby address.')
      setSelected(addr)
      setQuery(addr.label)
      dispatch(pushToast({ message: `Delivering to ${addr.label}`, variant: 'success' }))
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not detect your location.'
      dispatch(pushToast({ message, variant: 'error' }))
    } finally {
      setDetecting(false)
    }
  }

  const handleSelect = (addr: DeliveryAddress) => {
    setSelected(addr)
    setQuery(addr.label)
    setResults([])
  }

  const handleConfirm = () => {
    if (!selected) return
    dispatch(setDeliveryAddress(selected))
    onClose()
  }

  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[90] flex items-center justify-center p-4">
          <motion.div
            className="absolute inset-0 bg-ink/40 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.18 }}
            className="relative w-full max-w-md rounded-3xl border border-border bg-surface p-6 shadow-pop"
            role="dialog"
            aria-modal="true"
            aria-label="Choose delivery location"
          >
            <div className="flex items-center justify-between">
              <h2 className="font-display text-lg font-semibold">Deliver to</h2>
              <button
                onClick={onClose}
                aria-label="Close"
                className="rounded-lg p-2 text-ink-muted hover:bg-surface-muted"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <Button
              variant="outline"
              className="mt-4 w-full"
              onClick={handleDetect}
              disabled={detecting}
            >
              {detecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <LocateFixed className="h-4 w-4" />}
              {detecting ? 'Detecting location…' : 'Auto-detect my location'}
            </Button>

            <div className="relative mt-4">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" />
              <Input
                className="pl-11"
                placeholder="Search your area, street or city"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                aria-label="Search location"
              />
              {searching && (
                <Loader2 className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-ink-muted" />
              )}
              {results.length > 0 && (
                <ul className="absolute inset-x-0 top-full z-10 mt-2 max-h-64 overflow-auto rounded-2xl border border-border bg-surface shadow-pop">
                  {results.map((r) => (
                    <li key={r.placeId}>
                      <button
                        onClick={() => handleSelect(r)}
                        className="flex w-full items-start gap-3 px-4 py-3 text-left text-sm hover:bg-surface-muted"
                      >
                        <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                        <span>
                          <span className="block font-medium text-ink">{r.label}</span>
                          <span className="block text-xs text-ink-muted">{r.full}</span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {selected && (
              <div className="mt-4 flex items-start gap-3 rounded-2xl border border-border bg-surface-muted/60 p-4">
                <MapPin className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-ink">{selected.label}</p>
                  <p className="mt-0.5 text-xs text-ink-muted">{selected.full}</p>
                </div>
              </div>
            )}

            <div className="mt-6 flex gap-3">
              <Button variant="outline" className="flex-1" onClick={onClose}>
                Cancel
              </Button>
              <Button className="flex-1" onClick={handleConfirm} disabled={!selected}>
                Confirm location
              </Button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  )
}