// Admin Dashboard — revenue charts, order stats, top products, inventory alerts.
import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import {
  DollarSign,
  ShoppingCart,
  Users,
  Package,
  AlertTriangle,
  TrendingUp,
  Loader2,
  Clock,
  Eye,
  X,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { BackButton } from "@/components/ui/back-button"
import { api } from "@/lib/api/client"
import { usePolling } from "@/hooks/usePolling"
import { StatusBadge } from "./shared"

interface DashboardStats {
  revenue: { total: string; monthly: string; weekly: string }
  orders: { total: number; monthly: number; pending: number }
  customers: { total: number; new_this_month: number }
  products: { total: number; low_stock: number }
  avg_order_value: string
}

interface TopProduct {
  id: string
  name: string
  total_sold: number
  total_revenue: string
  avg_rating: string
  stock_quantity: number
}

interface LowStock {
  id: string
  name: string
  stock_quantity: number
  stock_unit: "kg" | "count"
}

interface RecentOrder {
  id: string
  order_number: string
  user_name: string
  user_phone: string
  status: string
  grand_total: string
  created_at: string
}

interface RevenueDay {
  date: string
  revenue: string
  orders: number
}

export default function AdminDashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [topProducts, setTopProducts] = useState<TopProduct[]>([])
  const [lowStock, setLowStock] = useState<LowStock[]>([])
  const [recentOrders, setRecentOrders] = useState<RecentOrder[]>([])
  const [revenueChart, setRevenueChart] = useState<RevenueDay[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [showChartModal, setShowChartModal] = useState(false)

  useEffect(() => {
    void fetchDashboardData()
  }, [])

  const fetchDashboardData = async (silent = false) => {
    if (!silent) setLoading(true)
    setError("")
    try {
      const [statsRes, topRes, lowRes, ordersRes, chartRes] = await Promise.all([
        api.get("/api/v1/admin-dashboard/stats/"),
        api.get("/api/v1/admin-dashboard/top-products/?limit=5"),
        api.get("/api/v1/admin-dashboard/low-stock/"),
        api.get("/api/v1/admin-dashboard/recent-orders/?limit=5"),
        api.get("/api/v1/admin-dashboard/revenue-chart/?month=true"),
      ])
      setStats(statsRes.data)
      setTopProducts(topRes.data)
      setLowStock(lowRes.data)
      setRecentOrders(ordersRes.data)
      setRevenueChart(chartRes.data)
    } catch {
      setError("Failed to load dashboard data.")
    } finally {
      if (!silent) setLoading(false)
    }
  }

  // Real-time refresh — stock changes (sales / admin updates), new orders and
  // revenue land on the dashboard within 30s without any user interaction.
  usePolling(() => void fetchDashboardData(true), 30000)

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div>
      <BackButton to="/shop" homeTo="/admin/dashboard" storeTo="/shop" />
      <h1 className="font-display text-2xl font-bold">Overview</h1>

      {error && (
        <div className="mt-4 rounded-xl bg-danger-muted p-3 text-sm text-danger">{error}</div>
      )}

      {/* Stat Cards */}
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { icon: DollarSign, label: "Monthly Revenue", value: `₹${Number(stats?.revenue.monthly ?? 0).toFixed(2)}`, color: "success" },
          { icon: ShoppingCart, label: "Monthly Orders", value: stats?.orders.monthly || "0", color: "primary" },
          { icon: Users, label: "Total Customers", value: stats?.customers.total || "0", color: "secondary" },
          { icon: Package, label: "Low Stock Items", value: stats?.products.low_stock || "0", color: "warning" },
        ].map((card, i) => (
          <motion.div
            key={card.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className="rounded-2xl border border-border bg-surface p-5 shadow-card"
          >
            <div className="flex items-center gap-3">
              <div className={`grid h-10 w-10 place-items-center rounded-xl bg-${card.color}/10 text-${card.color}`}>
                <card.icon className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm text-ink-muted">{card.label}</p>
                <p className="text-2xl font-bold">{card.value}</p>
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {/* Monthly Revenue chart (current calendar month, paid orders only) */}
        <section className="rounded-2xl border border-border bg-surface p-6 shadow-card">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="font-display text-lg font-semibold flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-primary" /> Monthly Revenue
            </h2>
            <button
              type="button"
              onClick={() => setShowChartModal(true)}
              title="View larger chart"
              className="rounded-lg p-1.5 text-ink-muted transition-colors hover:bg-ink-subtle hover:text-ink"
            >
              <Eye className="h-4 w-4" />
            </button>
          </div>
          {revenueChart.length === 0 ? (
            <p className="py-10 text-center text-sm text-ink-muted">
              No paid orders yet this month.
            </p>
          ) : (
            <div className="h-40">
              <RevenueLineChart data={revenueChart} />
            </div>
          )}
        </section>

        {/* Low Stock Alerts */}
        <section className="rounded-2xl border border-border bg-surface p-6 shadow-card">
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-warning" /> Low Stock Alerts
          </h2>
          {lowStock.length === 0 ? (
            <p className="text-sm text-ink-muted">All products well stocked!</p>
          ) : (
            <div className="max-h-64 space-y-2 overflow-y-auto pr-1">
              {lowStock.map((p) => (
                <div key={p.id} className="flex items-center justify-between rounded-xl bg-warning-muted px-4 py-3">
                  <div>
                    <p className="text-sm font-medium">{p.name}</p>
                    <p className="text-xs text-ink-muted">{p.stock_unit === "kg" ? "Weighted item (kg)" : "Counted item"}</p>
                  </div>
                  <Badge variant={p.stock_quantity === 0 ? "danger" : "warning"}>
                    {p.stock_quantity} left
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {/* Top Products */}
        <section className="rounded-2xl border border-border bg-surface p-6 shadow-card">
          <h2 className="font-display text-lg font-semibold mb-4">Top Products</h2>
          <div className="space-y-3">
            {topProducts.map((p, i) => (
              <div key={p.id} className="flex items-center justify-between rounded-xl bg-ink-subtle px-4 py-3">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-bold text-primary">#{i + 1}</span>
                  <div>
                    <p className="text-sm font-medium">{p.name}</p>
                    <p className="text-xs text-ink-muted">Sold: {p.total_sold}</p>
                  </div>
                </div>
                <span className="text-sm font-semibold">₹{Number(p.total_revenue).toFixed(2)}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Recent Orders */}
        <section className="rounded-2xl border border-border bg-surface p-6 shadow-card">
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <Clock className="h-5 w-5 text-primary" /> Recent Orders
          </h2>
          <div className="space-y-2">
            {recentOrders.map((o) => (
              <div key={o.id} className="flex items-center justify-between rounded-xl bg-ink-subtle px-4 py-3">
                <div>
                  <p className="text-sm font-medium">{o.order_number}</p>
                  <p className="text-xs text-ink-muted">
                    {o.user_name} • {new Date(o.created_at).toLocaleDateString()}
                  </p>
                </div>
                <div className="text-right">
                  <StatusBadge status={o.status} />
                  <p className="text-sm font-semibold">₹{o.grand_total}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* Larger monthly revenue view */}
      {showChartModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setShowChartModal(false)}
        >
          <div
            className="w-full max-w-3xl rounded-2xl border border-border bg-surface p-6 shadow-card"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-6 flex items-center justify-between gap-3">
              <h2 className="font-display text-lg font-semibold flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-primary" /> Monthly Revenue
              </h2>
              <Button variant="ghost" size="sm" onClick={() => setShowChartModal(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            {revenueChart.length === 0 ? (
              <p className="py-16 text-center text-sm text-ink-muted">
                No paid orders yet this month.
              </p>
            ) : (
              <div className="h-72">
                <RevenueLineChart data={revenueChart} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

/** Compact money label for the Y axis (₹1.2k / ₹850). */
function fmtAxisRevenue(value: number): string {
  if (value >= 1000) {
    const k = value / 1000
    return `₹${k % 1 === 0 ? k : k.toFixed(1)}k`
  }
  return `₹${Math.round(value)}`
}

/**
 * Daily revenue line chart for the current calendar month.
 *
 * X-axis: every day of the month up to today (days without paid orders are
 * zero-filled so the trend is honest). Y-axis: revenue. Paid-order data only —
 * the backend endpoint already excludes failed/pending/dropped payments.
 * Renders as an SVG polyline stretched over a fixed-size container
 * (vector-effect keeps the stroke width uniform at any size); data points are
 * HTML dots positioned in percentages so they stay perfectly circular.
 */
function RevenueLineChart({ data }: { data: RevenueDay[] }) {
  // Zero-filled series: day 1..today of the current month.
  const today = new Date().getDate()
  const byDay = new Map(
    data.map((d) => [Number(d.date.slice(8, 10)), parseFloat(d.revenue) || 0]),
  )
  const days = Array.from({ length: today }, (_, i) => ({
    day: i + 1,
    revenue: byDay.get(i + 1) ?? 0,
  }))

  const maxRev = Math.max(...days.map((d) => d.revenue), 1)
  // X position across the month (single-day months center their point).
  const xPct = (day: number) =>
    days.length > 1 ? ((day - 1) / (days.length - 1)) * 100 : 50
  // Y position: max touches the top edge, ₹0 sits on the baseline.
  const yPct = (revenue: number) => (1 - revenue / maxRev) * 100

  const points = days.map((d) => `${xPct(d.day)},${yPct(d.revenue)}`)

  // Sparse X tick labels (~6) so up-to-31 labels never crowd the axis.
  const labelStep = Math.max(1, Math.ceil(days.length / 6))

  return (
    <div className="flex h-full w-full flex-col">
      <div className="flex min-h-0 flex-1 gap-2">
        {/* Y-axis labels aligned with the top / mid / baseline gridlines */}
        <div className="flex w-10 shrink-0 flex-col items-end justify-between text-right text-[10px] leading-none text-ink-muted">
          <span>{fmtAxisRevenue(maxRev)}</span>
          <span>{fmtAxisRevenue(maxRev / 2)}</span>
          <span>₹0</span>
        </div>
        {/* Plot area — border-b doubles as the ₹0 baseline */}
        <div className="relative min-w-0 flex-1 border-b border-border">
          <svg
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            className="h-full w-full overflow-visible text-primary"
          >
            <line
              x1="0"
              y1="50"
              x2="100"
              y2="50"
              className="text-border"
              stroke="currentColor"
              strokeWidth="1"
              strokeDasharray="3 3"
              vectorEffect="non-scaling-stroke"
            />
            {points.length > 1 && (
              <polyline
                points={points.join(" ")}
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinejoin="round"
                strokeLinecap="round"
                vectorEffect="non-scaling-stroke"
              />
            )}
          </svg>
          {/* Data points (HTML so they stay round under non-uniform scaling) */}
          {days.map((d) => (
            <span
              key={d.day}
              className="absolute h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary"
              style={{ left: `${xPct(d.day)}%`, top: `${yPct(d.revenue)}%` }}
              title={`Day ${d.day} — ₹${d.revenue.toFixed(2)}`}
            />
          ))}
        </div>
      </div>
      {/* X-axis: day-of-month labels pinned under their exact plot positions
          (ml-12 = Y-axis gutter w-10 + gap-2) */}
      <div className="relative ml-12 mt-1 h-3 text-[10px] leading-none text-ink-muted">
        {days.map((d) =>
          d.day === 1 || d.day % labelStep === 0 || d.day === days.length ? (
            <span
              key={d.day}
              className="absolute top-0 -translate-x-1/2"
              style={{ left: `${xPct(d.day)}%` }}
            >
              {d.day}
            </span>
          ) : null,
        )}
      </div>
    </div>
  )
}
