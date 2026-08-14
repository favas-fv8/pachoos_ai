// Admin Notifications — activity performed by the *other* admin on the shared
// dashboard. Persisted in the backend (AdminNotification) so history survives
// logout/restart, and both admins always see each other's catalog actions.
import { useMemo } from 'react'
import { Bell, CheckCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { BackButton } from '@/components/ui/back-button'
import { useAdminNotifications } from '@/hooks/useAdminNotifications'
import { Loader } from './shared'

const ACTION_LABELS: Record<string, { label: string; variant: 'default' | 'secondary' | 'warning' | 'danger' | 'success' | 'muted' }> = {
  product_added: { label: 'Product added', variant: 'success' },
  product_updated: { label: 'Product updated', variant: 'default' },
  product_deleted: { label: 'Product deleted', variant: 'danger' },
  product_activated: { label: 'Product activated', variant: 'success' },
  product_deactivated: { label: 'Product deactivated', variant: 'warning' },
  product_image_updated: { label: 'Product image updated', variant: 'default' },
  stock_changed: { label: 'Stock changed', variant: 'default' },
  category_added: { label: 'Category added', variant: 'success' },
  category_updated: { label: 'Category updated', variant: 'default' },
  category_deleted: { label: 'Category deleted', variant: 'danger' },
  category_activated: { label: 'Category activated', variant: 'success' },
  category_deactivated: { label: 'Category deactivated', variant: 'warning' },
  subcategory_added: { label: 'Subcategory added', variant: 'success' },
}

export default function AdminNotifications() {
  const { notifications, unreadCount, loading, markRead } = useAdminNotifications(15000)

  const sorted = useMemo(
    () => [...notifications].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [notifications],
  )

  return (
    <div>
      <BackButton to="/admin/dashboard" homeTo="/admin/dashboard" storeTo="/shop" />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold">Notifications</h1>
          <p className="text-sm text-ink-muted">Activity performed by the other admin on the shared dashboard.</p>
        </div>
        {unreadCount > 0 && (
          <Button variant="outline" onClick={() => markRead()}>
            <CheckCheck className="mr-1 h-4 w-4" /> Mark all read
          </Button>
        )}
      </div>

      <div className="mt-6">
        {loading && notifications.length === 0 ? (
          <Loader />
        ) : sorted.length === 0 ? (
          <div className="rounded-2xl border border-border bg-surface p-10 text-center">
            <Bell className="mx-auto h-8 w-8 text-ink-muted" />
            <p className="mt-2 text-sm text-ink-muted">No activity yet. Changes made by the other admin will appear here.</p>
          </div>
        ) : (
          <ul className="space-y-3">
            {sorted.map((n) => {
              const meta = ACTION_LABELS[n.action] ?? { label: n.action, variant: 'muted' as const }
              return (
                <li
                  key={n.id}
                  className={`rounded-2xl border bg-surface p-4 transition-colors ${
                    n.is_read ? 'border-border' : 'border-primary/40 bg-primary/5'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className={`grid h-9 w-9 shrink-0 place-items-center rounded-full ${n.is_read ? 'bg-ink-subtle' : 'bg-primary/15'}`}>
                      <Bell className="h-4 w-4 text-primary" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={meta.variant}>{meta.label}</Badge>
                        <span className="text-xs text-ink-muted">{timeAgo(n.created_at)}</span>
                        {!n.is_read && <span className="h-2 w-2 rounded-full bg-primary" />}
                      </div>
                      <p className="mt-1 text-sm">{n.description}</p>
                      <p className="mt-0.5 text-xs text-ink-muted">by {n.actor_name}</p>
                    </div>
                    {!n.is_read && (
                      <Button variant="ghost" size="sm" onClick={() => markRead(n.id)}>
                        Mark read
                      </Button>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}

function timeAgo(iso: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000))
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  return new Date(iso).toLocaleDateString()
}
