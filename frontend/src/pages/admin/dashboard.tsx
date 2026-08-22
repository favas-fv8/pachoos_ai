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
            <div className="flex items-end gap-1 h-40">
              <RevenueBars data={revenueChart} />
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
              <div className="flex items-end gap-1.5 h-72">
                <RevenueBars data={revenueChart} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function RevenueBars({ data }: { data: RevenueDay[] }) {
  const maxRev = Math.max(...data.map((x) => parseFloat(x.revenue) || 0), 1)
  return (
    <>
      {data.map((d) => {
        const height = (parseFloat(d.revenue) / maxRev) * 100
        return (
          <div
            key={d.date}
            className="min-w-0 flex-1 flex flex-col items-center"
            title={`${d.date} — ₹${Number(d.revenue).toFixed(2)}`}
          >
            <div
              className="w-full bg-primary rounded-t"
              style={{ height: `${Math.max(height, 4)}%` }}
            />
            <span className="text-[10px] text-ink-muted mt-1">
              {Number(d.date.slice(8, 10))}
            </span>
          </div>
        )
      })}
    </>
  )
}
