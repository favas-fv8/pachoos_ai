import { motion } from 'framer-motion'
import { MapPin, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { BackButton } from '@/components/ui/back-button'

export default function Track() {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="container-px mx-auto py-8">
      <BackButton to="/account/orders" />
      <h1 className="font-display text-3xl font-bold">Track Order</h1>
      <div className="mt-6 rounded-2xl border border-border bg-surface p-6 shadow-card">
        <div className="flex items-center gap-3">
          <MapPin className="h-5 w-5 text-primary" />
          <p className="text-ink-muted">No order selected. Enter an order number to track.</p>
        </div>
        <div className="mt-4 flex gap-3">
          <Input placeholder="e.g. PCH-20260803-0012" className="flex-1" />
          <Button>Track</Button>
        </div>
      </div>

      {/* Status stepper placeholder */}
      <div className="mt-8 space-y-4">
        {['Pending', 'Accepted', 'Preparing', 'Packed', 'Out for delivery', 'Delivered'].map(
          (step, i) => (
            <div key={step} className="flex items-center gap-3">
              <div className="grid h-8 w-8 place-items-center rounded-full bg-surface-muted">
                <Clock className="h-4 w-4 text-ink-muted" />
              </div>
              <span className={i < 2 ? 'text-ink' : 'text-ink-muted'}>{step}</span>
            </div>
          ),
        )}
      </div>
    </motion.div>
  )
}