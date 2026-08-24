// ChatWidget — floating AI assistant chat bubble.
//
// `audience` selects which backend assistant is used; the two are strictly
// separated server-side (customer vs admin data, permissions and prompts).
import { useState, useRef, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { MessageCircle, X, Send, Loader2, Bot, User } from "lucide-react"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api/client"
import { useAppSelector } from "@/store/hooks"
import { ChatMarkdown } from "./ChatMarkdown"

interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: Date
}

type Audience = "customer" | "admin"

const AUDIENCE_CONFIG = {
  customer: {
    endpoint: "/api/v1/ai/chat/",
    title: "PACHOOS Assistant",
    subtitle: "Always here to help",
    placeholder: "Ask me anything...",
    welcome: "Hey! Welcome to PACHOOS! How can I help you today?",
  },
  admin: {
    endpoint: "/api/v1/ai/admin-chat/",
    title: "PACHOOS Admin Assistant",
    subtitle: "Your live store data",
    placeholder: "Ask about revenue, orders, stock...",
    welcome:
      "Hi! Ask me about revenue, orders, customers or stock — straight from the live dashboard.",
  },
} as const

export function ChatWidget({ audience = "customer" }: { audience?: Audience }) {
  const cfg = AUDIENCE_CONFIG[audience]
  // The customer's "Deliver To" location (header picker) — sent with each
  // customer-audience message so the assistant can answer location questions.
  const deliveryAddress = useAppSelector((s) => s.ui.deliveryAddress)
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: cfg.welcome,
      timestamp: new Date(),
    },
  ])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || loading) return

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: "user",
      content: input,
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMsg])
    setInput("")
    setLoading(true)

    try {
      const history = messages
        .filter((m) => m.id !== "welcome")
        .map((m) => ({ role: m.role, content: m.content }))
      const res = await api.post(cfg.endpoint, {
        message: input,
        history,
        ...(audience === "customer" && {
          location: deliveryAddress
            ? { label: deliveryAddress.label, lat: deliveryAddress.lat, lon: deliveryAddress.lon }
            : null,
        }),
      })

      const assistantMsg: Message = {
        id: `a-${Date.now()}`,
        role: "assistant",
        content: res.data.response,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: `e-${Date.now()}`,
          role: "assistant",
          content: "Sorry, something went wrong. Please try again.",
          timestamp: new Date(),
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <>
      {/* Toggle Button */}
      <motion.button
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        whileHover={{ scale: 1.1 }}
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 z-50 grid h-14 w-14 place-items-center rounded-full bg-primary text-white shadow-lg hover:bg-primary/90"
        aria-label={cfg.title}
      >
        {isOpen ? <X className="h-6 w-6" /> : <MessageCircle className="h-6 w-6" />}
      </motion.button>

      {/* Chat Panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className="fixed bottom-24 right-6 z-50 flex w-[360px] flex-col rounded-2xl border border-border bg-surface shadow-2xl"
            style={{ maxHeight: "500px" }}
          >
            {/* Header */}
            <div className="flex items-center gap-2 border-b border-border px-4 py-3">
              <div className="grid h-8 w-8 place-items-center rounded-full bg-primary/10 text-primary">
                <Bot className="h-4 w-4" />
              </div>
              <div>
                <p className="text-sm font-semibold">{cfg.title}</p>
                <p className="text-xs text-ink-muted">{cfg.subtitle}</p>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3" style={{ maxHeight: "340px" }}>
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${
                      msg.role === "user"
                        ? "bg-primary text-white rounded-br-md"
                        : "bg-ink-subtle text-ink rounded-bl-md"
                    }`}
                  >
                    {msg.role === "assistant" && (
                      <Bot className="mb-1 inline h-3 w-3 text-primary" />
                    )}
                    {msg.role === "user" && (
                      <User className="mb-1 inline h-3 w-3 text-white/70" />
                    )}
                    <div className="ml-1 inline-block max-w-full align-top">
                      <ChatMarkdown content={msg.content} />
                    </div>
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <div className="rounded-2xl rounded-bl-md bg-ink-subtle px-4 py-2">
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="border-t border-border px-4 py-3">
              <div className="flex gap-2">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={cfg.placeholder}
                  className="flex-1 rounded-xl border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring/40"
                />
                <Button
                  size="sm"
                  onClick={sendMessage}
                  disabled={!input.trim() || loading}
                  className="rounded-xl"
                >
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
