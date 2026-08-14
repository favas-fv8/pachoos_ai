import axios, {
  AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from 'axios'
import { tokenStore } from './tokenStore'

export interface ApiErrorBody {
  error?: {
    code?: string
    message?: string
    details?: Record<string, unknown>
  }
}

const BASE_URL: string = import.meta.env.VITE_API_URL ?? ''

export const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 20000,
})

// Attach the access token to every request.
api.interceptors.request.use((config) => {
  const token = tokenStore.getAccess()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // Let the browser set the multipart boundary for FormData uploads. The
  // instance default is application/json; keeping it makes axios serialise
  // FormData into JSON (so `request.FILES` arrives empty on the backend).
  if (config.data instanceof FormData) {
    config.headers.delete('Content-Type')
  }
  return config
})

let refreshPromise: Promise<string | null> | null = null

async function doRefresh(): Promise<string | null> {
  const refresh = tokenStore.getRefresh()
  if (!refresh) return null
  try {
    const res = await axios.post(`${BASE_URL}/api/v1/auth/token/refresh/`, {
      refresh,
    })
    const access: string = res.data.access
    tokenStore.setAccess(access)
    return access
  } catch {
    tokenStore.clear()
    return null
  }
}

// On 401, try to refresh once; if that fails, notify auth listeners.
api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError<ApiErrorBody>) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined
    const status = error.response?.status

    if (status === 401 && original && !original._retried) {
      original._retried = true
      if (!refreshPromise) {
        refreshPromise = doRefresh().finally(() => {
          refreshPromise = null
        })
      }
      const access = await refreshPromise
      if (access) {
        original.headers.Authorization = `Bearer ${access}`
        return api(original)
      }
      window.dispatchEvent(new CustomEvent('pachoos:unauthorized'))
      throw error
    }

    if (status === undefined) {
      // Network / timeout — normalize so UI can show a friendly message.
      throw new ApiError('NETWORK_ERROR', 'Could not reach the server. Please check your connection.', {})
    }

    throw error
  },
)

/** Normalized error with stable code + message parsed from the envelope. */
export class ApiError extends Error {
  code: string
  details: Record<string, unknown>
  status?: number

  constructor(code: string, message: string, details: Record<string, unknown>, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.details = details
    this.status = status
  }
}

/**
 * DRF StandardPagination envelope returned by the backend for list endpoints.
 * Not every list endpoint paginates, so consumers must accept either a bare
 * array or this envelope.
 */
export interface PaginatedEnvelope<T> {
  count: number
  page: number
  num_pages: number
  next: string | null
  previous: string | null
  results: T[]
}

/**
 * Fetch a list endpoint and normalise it to a flat array.
 *
 * List endpoints backed by a `ModelViewSet` inherit DRF's global
 * StandardPagination (page size 24), so the raw response is an envelope like
 * `{ count, next, previous, results }` rather than an array. Unpaginated
 * endpoints return a bare array. This helper follows `next` across every page
 * and returns the combined `results` — callers always receive an array.
 */
export async function fetchListAll<T>(url: string): Promise<T[]> {
  const all: T[] = []
  let nextUrl: string | null = url
  while (nextUrl) {
    const res = await api.get(nextUrl)
    const data = res.data as PaginatedEnvelope<T> | T[]
    if (Array.isArray(data)) {
      all.push(...data)
      return all
    }
    all.push(...(Array.isArray(data.results) ? data.results : []))
    nextUrl = data.next
  }
  return all
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  if (axios.isAxiosError(error)) {
    const body = error.response?.data as ApiErrorBody | Record<string, unknown> | undefined
    const rawError = (body as { error?: unknown } | undefined)?.error
    if (typeof rawError === 'string') {
      // Legacy/manual responses: {"error": "message"}
      return new ApiError('ERROR', rawError, {}, error.response?.status)
    }
    const parsed = rawError as ApiErrorBody['error'] | undefined
    return new ApiError(
      parsed?.code ?? 'ERROR',
      parsed?.message ?? 'Something went wrong.',
      parsed?.details ?? {},
      error.response?.status,
    )
  }
  return new ApiError('ERROR', 'Something went wrong.', {})
}