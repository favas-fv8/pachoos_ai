import { motion } from 'framer-motion'
import { ShoppingBag, ArrowRight } from 'lucide-react'
import { ButtonLink } from '@/components/ui/button'

export default function Cart() {
  return (
    <div className="container-px mx-auto py-8">
      <h1 className="font-display text-3xl font-bold">Cart</h1>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="mt-6 flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-surface py-20 text-center"
      >
        <ShoppingBag className="mb-4 h-12 w-12 text-ink-muted" />
        <p className="text-ink-muted">Your cart is empty.</p>
        <ButtonLink href="/shop" className="mt-4">
          Start shopping <ArrowRight className="ml-2 h-4 w-4" />
        </ButtonLink>
      </motion.div>
    </div>
  )
}