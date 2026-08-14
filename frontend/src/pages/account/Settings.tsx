import { useState } from 'react'
import { motion } from 'framer-motion'
import { BackButton } from '@/components/ui/back-button'
import { useNavigate } from 'react-router-dom'
import { Moon, Sun, LogOut, KeyRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import ChangePasswordForm from '@/components/auth/ChangePasswordForm'
import { useAppDispatch, useAppSelector } from '@/store/hooks'
import { toggleTheme } from '@/store/slices/uiSlice'
import { logout } from '@/store/slices/authSlice'
import { signOutFirebase } from '@/lib/firebase'

export default function Settings() {
  const theme = useAppSelector((s) => s.ui.theme)
  const dispatch = useAppDispatch()
  const navigate = useNavigate()

  const [passwordOpen, setPasswordOpen] = useState(false)

  const handleLogout = async () => {
    // Clear the lingering Firebase session so the next Google sign-in starts fresh.
    await signOutFirebase()
    dispatch(logout())
    navigate('/login', { replace: true })
  }

  return (
    <div>
      <BackButton to="/account" />
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
        <div className="flex items-center justify-between rounded-2xl border border-border bg-surface p-6 shadow-card">
          <div>
            <p className="font-semibold">Theme</p>
            <p className="text-sm text-ink-muted">Switch between light and dark mode.</p>
          </div>
          <Button variant="outline" onClick={() => dispatch(toggleTheme())}>
            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            {theme === 'dark' ? 'Light mode' : 'Dark mode'}
          </Button>
        </div>

        <div className="rounded-2xl border border-border bg-surface p-6 shadow-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-semibold">Change password</p>
              <p className="text-sm text-ink-muted">
                Enter your current password, then set a new one. All other devices will be signed out.
              </p>
            </div>
            <Button variant="outline" onClick={() => setPasswordOpen((o) => !o)}>
              <KeyRound className="h-4 w-4" />
              {passwordOpen ? 'Close' : 'Change'}
            </Button>
          </div>
          {passwordOpen && (
            <div className="mt-4 border-t border-border pt-4">
              <ChangePasswordForm />
            </div>
          )}
        </div>

        <div className="flex items-center justify-between rounded-2xl border border-border bg-surface p-6 shadow-card">
          <div>
            <p className="font-semibold">Sign out</p>
            <p className="text-sm text-ink-muted">Log out of this device.</p>
          </div>
          <Button variant="danger" onClick={handleLogout}>
            <LogOut className="h-4 w-4" />
            Sign out
          </Button>
        </div>
      </motion.div>
    </div>
  )
}