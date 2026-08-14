import { AnimatePresence, motion } from 'framer-motion'
import { CheckCircle2, Info, X, XCircle } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { useAppDispatch, useAppSelector } from '@/store/hooks'
import { dismissToast } from '@/store/slices/uiSlice'

/** Popup messages disappear on their own after this long (within 3–5 seconds). */
const AUTO_DISMISS_MS = 4000

const icons = {
  default: Info,
  success: CheckCircle2,
  error: XCircle,
}

const iconColors = {
  default: 'text-primary',
  success: 'text-success',
  error: 'text-danger',
}

export function Toaster() {
  const toasts = useAppSelector((s) => s.ui.toasts)
  const dispatch = useAppDispatch()
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>())

  // Clear every pending timer when the toaster unmounts.
  useEffect(() => {
    const pending = timers.current
    return () => {
      pending.forEach(clearTimeout)
      pending.clear()
    }
  }, [])

  // Schedule auto-dismiss for each toast once; the manual close button can
  // dismiss a toast early.
  useEffect(() => {
    for (const toast of toasts) {
      if (timers.current.has(toast.id)) continue
      const timer = setTimeout(() => {
        timers.current.delete(toast.id)
        dispatch(dismissToast(toast.id))
      }, AUTO_DISMISS_MS)
      timers.current.set(toast.id, timer)
    }
  }, [toasts, dispatch])

  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed bottom-4 left-1/2 z-[100] flex w-full max-w-sm -translate-x-1/2 flex-col gap-2 px-4 sm:bottom-6"
    >
      <AnimatePresence>
        {toasts.map((toast) => {
          const Icon = icons[toast.variant]
          return (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, y: 16, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.98 }}
              transition={{ duration: 0.18 }}
              className="pointer-events-auto flex items-start gap-3 rounded-2xl border border-border bg-surface p-4 shadow-pop"
              role="status"
            >
              <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${iconColors[toast.variant]}`} />
              <p className="flex-1 text-sm text-ink">{toast.message}</p>
              <button
                onClick={() => dispatch(dismissToast(toast.id))}
                aria-label="Dismiss"
                className="rounded-lg p-1 text-ink-muted hover:bg-surface-muted"
              >
                <X className="h-4 w-4" />
              </button>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}