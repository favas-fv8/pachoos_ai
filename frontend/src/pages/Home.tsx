import { motion } from 'framer-motion'
import { Leaf, Truck, Shield, Sparkles } from 'lucide-react'
import { ButtonLink } from '@/components/ui/button'
import { Link } from 'react-router-dom'
import { Recommendations } from '@/components/recommendations/Recommendations'

export default function Home() {
  return (
    <div className="flex flex-col">
      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-br from-primary/10 via-background to-secondary/10 py-16 sm:py-24">
        <div className="container-px mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            <span className="mx-auto mb-4 inline-flex items-center gap-2 rounded-full bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary">
              <Sparkles className="h-4 w-4" />
              Fresh every day
            </span>
            <h1 className="font-display text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
              Bakery &amp; Fruits,<br />Delivered to You
            </h1>
            <p className="mx-auto mt-4 max-w-lg text-ink-muted sm:text-lg">
              From our oven to your doorstep — fresh cakes, bread, cookies, and seasonal fruits,
              delivered in under an hour.
            </p>
            <div className="mt-8 flex justify-center gap-3">
              <ButtonLink href="/shop">Order now</ButtonLink>
              <ButtonLink href="/shop" variant="outline">
                Browse menu
              </ButtonLink>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Categories */}
      <section className="container-px mx-auto py-16">
        <h2 className="font-display text-2xl font-semibold">Shop by category</h2>
        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            { name: 'Bakery', emoji: '🍰', to: '/shop?category=bakery' },
            { name: 'Fruits', emoji: '🍎', to: '/shop?category=fruits' },
            { name: 'Pastries', emoji: '🥐', to: '/shop?category=pastries' },
            { name: 'Seasonal', emoji: '🍊', to: '/shop?category=seasonal' },
          ].map((cat) => (
            <motion.div
              key={cat.name}
              whileHover={{ y: -4 }}
              transition={{ duration: 0.2 }}
            >
              <Link
                to={cat.to}
                className="block rounded-2xl border border-border bg-surface p-6 text-center shadow-card hover:shadow-pop"
              >
                <span className="text-4xl">{cat.emoji}</span>
                <p className="mt-3 font-medium text-ink">{cat.name}</p>
              </Link>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Recommendations */}
      <section className="container-px mx-auto py-8">
        <Recommendations />
      </section>

      {/* Features */}
      <section className="border-t border-border bg-surface-muted/30 py-16">
        <div className="container-px mx-auto grid gap-8 sm:grid-cols-3">
          {[
            { icon: Truck, title: 'Fast delivery', desc: 'Free delivery on orders above ₹99 within 2 km.' },
            { icon: Shield, title: 'Secure payments', desc: 'Razorpay — UPI, cards, net banking, wallets.' },
            { icon: Leaf, title: 'Fresh guarantee', desc: 'Every product carries a freshness indicator.' },
          ].map((feat) => (
            <div key={feat.title} className="flex flex-col items-center text-center">
              <div className="grid h-14 w-14 place-items-center rounded-2xl bg-primary/10 text-primary">
                <feat.icon className="h-6 w-6" />
              </div>
              <h3 className="mt-4 font-display font-semibold">{feat.title}</h3>
              <p className="mt-2 text-sm text-ink-muted">{feat.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}