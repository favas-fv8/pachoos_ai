import { useEffect, useRef } from 'react'

/**
 * Re-runs a fetch callback every `intervalMs` and on window focus, so the
 * shared admin dashboard reflects the other admin's latest changes without
 * any websocket infrastructure (reliable API polling per requirements).
 */
export function usePolling(fetchFn: () => void | Promise<void>, intervalMs: number) {
  const fnRef = useRef(fetchFn)
  fnRef.current = fetchFn

  useEffect(() => {
    const run = () => void fnRef.current()
    const onFocus = () => void fnRef.current()
    run()
    const id = setInterval(run, intervalMs)
    window.addEventListener('focus', onFocus)
    return () => {
      clearInterval(id)
      window.removeEventListener('focus', onFocus)
    }
  }, [intervalMs])
}
