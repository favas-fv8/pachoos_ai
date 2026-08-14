import { createSlice, type PayloadAction } from '@reduxjs/toolkit'
import type { DeliveryAddress } from '@/lib/geocode'

type Theme = 'light' | 'dark'

interface UiState {
  theme: Theme
  mobileNavOpen: boolean
  deliveryAddress: DeliveryAddress | null
  toasts: { id: string; message: string; variant: 'default' | 'error' | 'success' }[]
}

function initialTheme(): Theme {
  const stored = localStorage.getItem('pachoos.theme')
  if (stored === 'light' || stored === 'dark') return stored
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function initialDeliveryAddress(): DeliveryAddress | null {
  const stored = localStorage.getItem('pachoos.deliveryAddress')
  if (!stored) return null
  try {
    const parsed = JSON.parse(stored) as DeliveryAddress
    if (parsed && typeof parsed.lat === 'number' && typeof parsed.lon === 'number') return parsed
    return null
  } catch {
    return null
  }
}

const initialState: UiState = {
  theme: initialTheme(),
  mobileNavOpen: false,
  deliveryAddress: initialDeliveryAddress(),
  toasts: [],
}

let toastSeq = 0

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    toggleTheme(state) {
      state.theme = state.theme === 'dark' ? 'light' : 'dark'
    },
    setTheme(state, action: PayloadAction<Theme>) {
      state.theme = action.payload
    },
    setMobileNavOpen(state, action: PayloadAction<boolean>) {
      state.mobileNavOpen = action.payload
    },
    setDeliveryAddress(state, action: PayloadAction<DeliveryAddress | null>) {
      state.deliveryAddress = action.payload
      if (action.payload) {
        localStorage.setItem('pachoos.deliveryAddress', JSON.stringify(action.payload))
      } else {
        localStorage.removeItem('pachoos.deliveryAddress')
      }
    },
    pushToast(state, action: PayloadAction<Omit<UiState['toasts'][number], 'id'>>) {
      const id = `t-${++toastSeq}`
      state.toasts.push({ ...action.payload, id })
    },
    dismissToast(state, action: PayloadAction<string>) {
      state.toasts = state.toasts.filter((t) => t.id !== action.payload)
    },
  },
})

export const { setTheme, setMobileNavOpen, setDeliveryAddress, pushToast, dismissToast, toggleTheme } = uiSlice.actions

// Sync the document theme whenever the slice changes.
export function applyTheme(theme: Theme) {
  const root = document.documentElement
  root.classList.toggle('dark', theme === 'dark')
  localStorage.setItem('pachoos.theme', theme)
}

export default uiSlice.reducer