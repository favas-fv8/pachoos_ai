import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
import { lazy, Suspense, type JSX } from 'react'
import { Spinner } from '@/components/ui/spinner'
import { CustomerLayout } from '@/components/layout/customer-layout'
import { AdminLayout } from '@/components/layout/admin-layout'
import { AccountLayout } from '@/pages/account/AccountLayout'
import { PublicOnly, RequireAuth, RequireAdmin, RequirePasswordSetup, SessionGuard } from '@/router/guards'

const Home = lazy(() => import('@/pages/Home'))
const Shop = lazy(() => import('@/pages/Shop'))
const ProductDetail = lazy(() => import('@/pages/ProductDetail'))
const Cart = lazy(() => import('@/pages/Cart'))
const Checkout = lazy(() => import('@/pages/Checkout'))
const Payment = lazy(() => import('@/pages/Payment'))
const PaymentResult = lazy(() => import('@/pages/PaymentResult'))
const Wallet = lazy(() => import('@/pages/Wallet'))
const Account = lazy(() => import('@/pages/Account'))
const Track = lazy(() => import('@/pages/Track'))
const Wishlist = lazy(() => import('@/pages/Wishlist'))
const Login = lazy(() => import('@/pages/Login'))
const ForgotPassword = lazy(() => import('@/pages/ForgotPassword'))
const ResetPassword = lazy(() => import('@/pages/ResetPassword'))
const CreatePassword = lazy(() => import('@/pages/CreatePassword'))

const AccountProfile = lazy(() => import('@/pages/account/Profile'))
const AccountOrders = lazy(() => import('@/pages/account/Orders'))
const AccountPayments = lazy(() => import('@/pages/account/Payments'))
const AccountWallet = lazy(() => import('@/pages/account/Wallet'))
const AccountDebtBook = lazy(() => import('@/pages/account/DebtBook'))
const AccountSettings = lazy(() => import('@/pages/account/Settings'))

const AdminDashboard = lazy(() => import('@/pages/admin/dashboard'))
const AdminProducts = lazy(() => import('@/pages/admin/products'))
const AdminOrders = lazy(() => import('@/pages/admin/orders'))
const AdminOrderDetail = lazy(() => import('@/pages/admin/order-detail'))
const AdminCustomers = lazy(() => import('@/pages/admin/customers'))
const AdminDebtBook = lazy(() => import('@/pages/admin/debt-book'))
const AdminNotifications = lazy(() => import('@/pages/admin/notifications'))
const AdminPayments = lazy(() => import('@/pages/admin/payments'))
const AdminSettings = lazy(() => import('@/pages/admin/settings'))

const Loading = (): JSX.Element => (
  <div className="flex min-h-[60vh] items-center justify-center">
    <Spinner size={32} />
  </div>
)

/** The /account area uses the customer shell for customers and admins alike. */
function AccountArea(): JSX.Element {
  return <CustomerLayout />
}

/**
 * Two fully separate interfaces sharing the same backend:
 *  - Customer Website at "/"  (CustomerLayout — public-facing storefront)
 *  - Admin Dashboard at "/admin" (AdminLayout — admin & super admin only)
 */
const router = createBrowserRouter([
  {
    // Session guard — watches for revoked sessions and redirects to /login.
    element: <SessionGuard />,
    children: [
      // ── Customer Website ────────────────────────────────────────────────
      {
        path: '/',
        element: <CustomerLayout />,
        children: [
          { index: true, element: <Home /> },
          { path: 'shop', element: <Shop /> },
          { path: 'shop/:category', element: <Shop /> },
          { path: 'product/:slug', element: <ProductDetail /> },
          { path: 'cart', element: <Cart /> },
          { path: 'checkout', element: <RequireAuth><Checkout /></RequireAuth> },
          { path: 'payment/:orderId', element: <RequireAuth><Payment /></RequireAuth> },
          { path: 'payment/result', element: <RequireAuth><PaymentResult /></RequireAuth> },
          { path: 'track/:orderId?', element: <Track /> },
          { path: 'wallet', element: <RequireAuth><Wallet /></RequireAuth> },
          { path: 'wishlist', element: <RequireAuth><Wishlist /></RequireAuth> },
        ],
      },

      // ── Account (customers keep the customer shell; admins get the Admin shell) ──
      {
        path: '/account',
        element: (
          <RequireAuth>
            <AccountArea />
          </RequireAuth>
        ),
        children: [
          {
            element: <AccountLayout />,
            children: [
              { index: true, element: <Account /> },
              { path: 'profile', element: <AccountProfile /> },
              { path: 'orders', element: <AccountOrders /> },
              { path: 'payments', element: <AccountPayments /> },
              { path: 'wallet', element: <AccountWallet /> },
              { path: 'debt-book', element: <AccountDebtBook /> },
              { path: 'settings', element: <AccountSettings /> },
            ],
          },
        ],
      },

      // ── Admin Dashboard (protected by RBAC) ─────────────────────────────
      {
        path: '/admin',
        element: (
          <RequireAdmin>
            <AdminLayout />
          </RequireAdmin>
        ),
        children: [
          { index: true, element: <Navigate to="/admin/dashboard" replace /> },
          { path: 'dashboard', element: <AdminDashboard /> },
          { path: 'products', element: <AdminProducts /> },
          { path: 'categories', element: <Navigate to="/admin/products" replace /> },
          { path: 'orders', element: <AdminOrders /> },
          { path: 'orders/:orderId', element: <AdminOrderDetail /> },
          { path: 'customers', element: <AdminCustomers /> },
          { path: 'debt-book', element: <AdminDebtBook /> },
          { path: 'payments', element: <AdminPayments /> },
          { path: 'notifications', element: <AdminNotifications /> },
          { path: 'settings', element: <AdminSettings /> },
        ],
      },

      // ── Public auth ─────────────────────────────────────────────────────
      {
        path: '/login',
        element: (
          <PublicOnly>
            <Login />
          </PublicOnly>
        ),
      },
      {
        path: '/forgot-password',
        element: (
          <PublicOnly>
            <ForgotPassword />
          </PublicOnly>
        ),
      },
      {
        path: '/reset-password',
        element: (
          <PublicOnly>
            <ResetPassword />
          </PublicOnly>
        ),
      },
      {
        path: '/create-password',
        element: (
          <RequirePasswordSetup>
            <CreatePassword />
          </RequirePasswordSetup>
        ),
      },
    ],
  },
])

export function AppRouter() {
  return (
    <Suspense fallback={<Loading />}>
      <RouterProvider router={router} />
    </Suspense>
  )
}