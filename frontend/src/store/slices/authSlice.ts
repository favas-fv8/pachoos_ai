import { createSlice, type PayloadAction } from '@reduxjs/toolkit'
import { tokenStore } from '@/lib/api/tokenStore'

export interface AuthState {
  access: string | null
  refresh: string | null
  user: {
    id: number
    phone?: string | null
    email?: string | null
    full_name: string
    role: string
    avatar_url?: string
    referral_code?: string | null
    is_verified: boolean
    has_password?: boolean
  } | null
  isAuthenticated: boolean
  isLoading: boolean
}

const initialState: AuthState = {
  access: tokenStore.getAccess(),
  refresh: tokenStore.getRefresh(),
  user: tokenStore.getUser(),
  isAuthenticated: Boolean(tokenStore.getAccess() && tokenStore.getUser()),
  isLoading: false,
}

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    setCredentials(state, action: PayloadAction<{ access: string; refresh: string; user: AuthState['user'] }>) {
      state.access = action.payload.access
      state.refresh = action.payload.refresh
      state.user = action.payload.user
      state.isAuthenticated = true
      tokenStore.set(action.payload.access, action.payload.refresh)
      if (action.payload.user) {
        tokenStore.setUser(action.payload.user)
      }
    },
    setUser(state, action: PayloadAction<AuthState['user']>) {
      state.user = action.payload
      if (action.payload) {
        tokenStore.setUser(action.payload)
      } else {
        localStorage.removeItem('pachoos.user')
      }
    },
    logout(state) {
      state.access = null
      state.refresh = null
      state.user = null
      state.isAuthenticated = false
      tokenStore.clear()
    },
    setLoading(state, action: PayloadAction<boolean>) {
      state.isLoading = action.payload
    },
  },
})

export const { setCredentials, setUser, logout, setLoading } = authSlice.actions
export default authSlice.reducer