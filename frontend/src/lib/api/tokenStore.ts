const ACCESS_KEY = 'pachoos.access'
const REFRESH_KEY = 'pachoos.refresh'
const USER_KEY = 'pachoos.user'

export interface StoredUser {
  id: number
  phone?: string | null
  email?: string | null
  full_name: string
  role: string
  avatar_url?: string
  referral_code?: string | null
  is_verified: boolean
  has_password?: boolean
}

/** Minimal, dependency-free token + user storage (survives reloads). */
export const tokenStore = {
  getAccess(): string | null {
    return localStorage.getItem(ACCESS_KEY)
  },
  getRefresh(): string | null {
    return localStorage.getItem(REFRESH_KEY)
  },
  getUser(): StoredUser | null {
    const raw = localStorage.getItem(USER_KEY)
    if (!raw) return null
    try {
      return JSON.parse(raw) as StoredUser
    } catch {
      return null
    }
  },
  set(access: string, refresh: string): void {
    localStorage.setItem(ACCESS_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
  },
  setAccess(access: string): void {
    localStorage.setItem(ACCESS_KEY, access)
  },
  setUser(user: StoredUser): void {
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  },
  clear(): void {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
    localStorage.removeItem(USER_KEY)
  },
}