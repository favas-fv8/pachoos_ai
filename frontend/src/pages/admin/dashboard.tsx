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
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { BackButton } from "@/components/ui/back-button"
import { api } from "@/lib/api/client"
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
  low_stock_threshold: number
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

  useEffect(() => {
    fetchDashboardData()
  }, [])

  const fetchDashboardData = async () => {
    setLoading(true)
    setError("")
    try {
      const [statsRes, topRes, lowRes, ordersRes, chartRes] = await Promise.all([
        api.get("/api/v1/admin-dashboard/stats/"),
        api.get("/api/v1/admin-dashboard/top-products/?limit=5"),
        api.get("/api/v1/admin-dashboard/low-stock/"),
        api.get("/api/v1/admin-dashboard/recent-orders/?limit=10"),
        api.get("/api/v1/admin-dashboard/revenue-chart/?days=30"),
      ])
      setStats(statsRes.data)
      setTopProducts(topRes.data)
      setLowStock(lowRes.data)
      setRecentOrders(ordersRes.data)
      setRevenueChart(chartRes.data)
    } catch {
      setError("Failed to load dashboard data.")
    } finally {
      setLoading(false)
    }
  }

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
          { icon: DollarSign, label: "Monthly Revenue", value: `₹${stats?.revenue.monthly || "0"}`, color: "success" },
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
        {/* Revenue Chart (simple bar representation) */}
        <section className="rounded-2xl border border-border bg-surface p-6 shadow-card">
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-primary" /> Revenue (Last 30 Days)
          </h2>
          <div className="flex items-end gap-1 h-40">
            {revenueChart.slice(-14).map((d) => {
              const maxRev = Math.max(...revenueChart.map((x) => parseFloat(x.revenue) || 0), 1)
              const height = (parseFloat(d.revenue) / maxRev) * 100
              return (
                <div key={d.date} className="flex-1 flex flex-col items-center">
                  <div
                    className="w-full bg-primary rounded-t"
                    style={{ height: `${Math.max(height, 4)}%` }}
                    title={`₹${d.revenue}`}
                  />
                  <span className="text-[10px] text-ink-muted mt-1">
                    {d.date.slice(5)}
                  </span>
                </div>
              )
            })}
          </div>
        </section>

        {/* Low Stock Alerts */}
        <section className="rounded-2xl border border-border bg-surface p-6 shadow-card">
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-warning" /> Low Stock Alerts
          </h2>
          {lowStock.length === 0 ? (
            <p className="text-sm text-ink-muted">All products well stocked!</p>
          ) : (
            <div className="space-y-2">
              {lowStock.map((p) => (
                <div key={p.id} className="flex items-center justify-between rounded-xl bg-warning-muted px-4 py-3">
                  <div>
                    <p className="text-sm font-medium">{p.name}</p>
                    <p className="text-xs text-ink-muted">Threshold: {p.low_stock_threshold}</p>
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
                <span className="text-sm font-semibold">₹{p.total_revenue}</span>
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
    </div>
  )
}
