import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api/client'
import type { AdminNotification, NotificationsResponse } from '@/types'

/**
 * Fetches the other admin's activity notifications on an interval.
 * The backend DB is the single source of truth, so Admin 1 sees Admin 2's
 * changes on the next poll without any dedicated sync system.
 */
export function useAdminNotifications(intervalMs = 15000) {
  const [notifications, setNotifications] = useState<AdminNotification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchNotifications = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const res = await api.get<NotificationsResponse>('/api/v1/admin-dashboard/notifications/')
      setNotifications(res.data.results)
      setUnreadCount(res.data.unread_count)
    } catch {
      // Keep last known state; the badge just won't update this round.
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchNotifications()
    intervalRef.current = setInterval(() => void fetchNotifications(true), intervalMs)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [fetchNotifications, intervalMs])

  const markRead = useCallback(
    async (id?: number) => {
      try {
        await api.post('/api/v1/admin-dashboard/notifications/read/', { id })
        await fetchNotifications(true)
      } catch {
        // Ignore mark-read failures; data stays consistent on next poll.
      }
    },
    [fetchNotifications],
  )

  return { notifications, unreadCount, loading, markRead, refresh: fetchNotifications }
}
