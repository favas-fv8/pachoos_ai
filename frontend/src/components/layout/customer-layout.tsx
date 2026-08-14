import { Navigate, Outlet, ScrollRestoration } from 'react-router-dom'
import { Suspense } from 'react'
import { Header } from './header'
import { Footer } from './footer'
import { MobileNav } from './mobile-nav'
import { Toaster } from '@/components/ui/toaster'
import { Spinner } from '@/components/ui/spinner'
import { ChatWidget } from '@/components/chat/ChatWidget'
import { useAppSelector } from '@/store/hooks'

const Loading = () => (
  <div className="flex min-h-[60vh] items-center justify-center">
    <Spinner size={32} />
  </div>
)

export function CustomerLayout() {
  const { isAuthenticated, user } = useAppSelector((s) => s.auth)
  // An account without a password is not active for the store — it must finish
  // the mandatory password step before reaching the Home page.
  if (isAuthenticated && !user?.has_password) {
    return <Navigate to="/create-password" replace />
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1">
        <Suspense fallback={<Loading />}>
          <Outlet />
        </Suspense>
      </main>
      <Footer />
      <MobileNav />
      <ChatWidget />
      <Toaster />
      <ScrollRestoration />
    </div>
  )
}
