import { useState } from 'react'
import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { ArrowLeft, Loader2, Mail, Send, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, toApiError } from '@/lib/api/client'

/** Public "Forgot Password?" page — request an emailed password-reset link. */
export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)

  const handleSubmit = async () => {
    if (!email.trim()) {
      setError('Enter your email address.')
      return
    }
    setLoading(true)
    setError('')
    try {
      await api.post('/api/v1/auth/password/forgot/', { email: email.trim() })
      setSent(true)
    } catch (err) {
      setError(toApiError(err).message || 'Could not send the reset link. Try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="w-full max-w-md rounded-2xl border border-border bg-surface p-8 shadow-card"
      >
        <div className="mb-6 text-center">
          <h1 className="font-display text-2xl font-bold">PACHOOS</h1>
          <p className="mt-1 text-sm text-ink-muted">Reset your password</p>
          <p className="mt-2 text-xs text-ink-muted">
            Enter your account email and we&apos;ll send you a link to choose a new password.
          </p>
        </div>

        {sent ? (
          <div className="flex items-start gap-3 rounded-xl bg-success-muted p-4 text-sm text-success">
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-medium">Check your inbox</p>
              <p className="mt-1 text-success/80">
                If an account exists for that email, a password reset link is on its way.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {error && <div className="rounded-xl bg-danger-muted p-3 text-sm text-danger">{error}</div>}
            <div className="relative">
              <Mail className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" />
              <Input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="pl-11"
                autoComplete="email"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSubmit()
                }}
              />
            </div>
            <Button onClick={handleSubmit} disabled={loading} className="w-full">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              {loading ? 'Sending…' : 'Send reset link'}
            </Button>
          </div>
        )}

        <div className="mt-6 text-center">
          <Link
            to="/login"
            className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
          >
            <ArrowLeft className="h-4 w-4" /> Back to sign in
          </Link>
        </div>
      </motion.div>
    </div>
  )
}
