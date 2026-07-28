import { useRef, useState, type FormEvent } from 'react'
import { CornerBrackets } from '../components/CornerBrackets'
import { apiFetch } from '../lib/api'
import { LANGUAGES, type LanguageOption } from '../lib/languages'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

const SUGGESTIONS = [
  'How do I know if an OTP request is a scam?',
  'Is it safe to click a "refund" link in an SMS?',
  'What languages does Raksha AI support?',
]

export function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content:
        "I'm the Raksha AI Safety Assistant — ask me about scam patterns, digital banking safety, or how this app works.",
    },
  ])
  const [input, setInput] = useState('')
  const [language, setLanguage] = useState<LanguageOption['code']>('en')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  const send = async (text: string) => {
    if (!text.trim() || sending) return
    setError('')
    const nextMessages: ChatMessage[] = [...messages, { role: 'user', content: text }]
    setMessages(nextMessages)
    setInput('')
    setSending(true)

    try {
      const result = await apiFetch('/api/chat', {
        method: 'POST',
        body: JSON.stringify({
          message: text,
          language,
          history: nextMessages.slice(0, -1).filter((m) => m.role === 'user' || m.role === 'assistant'),
        }),
      })
      setMessages((prev) => [...prev, { role: 'assistant', content: result.reply }])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not reach the assistant — try again.')
    } finally {
      setSending(false)
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    }
  }

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    send(input)
  }

  return (
    <div className="mx-auto max-w-2xl flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 bg-accent" aria-hidden="true" />
          <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">Safety assistant</span>
        </div>
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value as LanguageOption['code'])}
          className="border border-ink bg-white px-2 py-1 text-[11px] text-ink focus:outline-none focus:ring-2 focus:ring-accent"
        >
          {LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.label}
            </option>
          ))}
        </select>
      </div>

      <div className="relative border border-ink bg-paper/60 backdrop-blur-sm p-4 sm:p-6 flex flex-col gap-3 min-h-[420px] max-h-[60vh] overflow-y-auto">
        <CornerBrackets />
        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-[85%] px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap break-words ${
              m.role === 'user'
                ? 'self-end bg-ink text-white'
                : 'self-start border border-ink bg-white text-ink'
            }`}
          >
            {m.content}
          </div>
        ))}
        {sending && (
          <div className="self-start border border-ink bg-white px-3 py-2 text-sm text-ink/50">
            Thinking…
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {messages.length === 1 && (
        <div className="flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => send(s)}
              className="border border-ink px-3 py-1.5 text-[11px] text-ink hover:bg-ink hover:text-white transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {error && <p className="border border-red-600 bg-red-50 px-3 py-2 text-[11px] text-red-700">{error}</p>}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about a scam pattern or how Raksha AI works…"
          maxLength={1000}
          className="flex-1 border border-ink bg-white px-3 py-2.5 text-sm text-ink placeholder:text-ink/30 focus:outline-none focus:ring-2 focus:ring-accent"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="bg-accent px-5 py-2.5 text-xs font-bold uppercase tracking-[0.15em] text-accent-ink hover:bg-ink transition-colors disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  )
}
