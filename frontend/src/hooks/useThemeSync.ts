import { useEffect } from 'react'
import { useAppSelector } from '@/store/hooks'
import { applyTheme } from '@/store/slices/uiSlice'

/** Keeps the <html data-theme> in sync with the Redux theme slice. */
export function useThemeSync() {
  const theme = useAppSelector((s) => s.ui.theme)
  useEffect(() => {
    applyTheme(theme)
  }, [theme])
}