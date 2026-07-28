import { useEffect, useRef, useState, type FormEvent } from 'react'
import { apiFetch } from '../lib/api'
import { LANGUAGES, type LanguageOption } from '../lib/languages'
import { CornerBrackets } from '../components/CornerBrackets'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const EXAMPLE_PROMPTS = [
  'Is it safe to share my UPI PIN over a call?',
  'I think I just got scammed — what do I do right now?',
  'How do fake KYC messages usually try to trick people?',
]

const MAX_HISTORY_SENT = 8

function SpeakerIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" aria-hidden="true">
      <path d="M4 9v6h4l5 4V5L8 9H4Z" fill="currentColor" />
      <path d="M16.5 8.5a5 5 0 0 1 0 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

export function ChatPage() {
  const [language, setLanguage] = useState<LanguageOption['code']>('en')
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [speakingIndex, setSpeakingIndex] = useState<number | null>(null)

  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  const speechLang = LANGUAGES.find((l) => l.code === language)?.speechLang ?? 'en-IN'

  const speak = (text: string, index: number) => {
    if (speakingIndex === index) {
      window.speechSynthesis.cancel()
      setSpeakingIndex(null)
      return
    }
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = speechLang
    utterance.onend = () => setSpeakingIndex(null)
    utterance.onerror = () => setSpeakingIndex(null)
    window.speechSynthesis.speak(utterance)
    setSpeakingIndex(index)
  }

  const send = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || sending) return

    setError('')
    setInput('')
    const nextMessages: Message[] = [...messages, { role: 'user', content: trimmed }]
    setMessages(nextMessages)
    setSending(true)

    try {
      const history = nextMessages.slice(0, -1).slice(-MAX_HISTORY_SENT)
      const result = await apiFetch('/api/chat', {
        method: 'POST',
        body: JSON.stringify({ message: trimmed, language, history }),
      })
      setMessages((prev) => [...prev, { role: 'assistant', content: result.reply }])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Assistant is unavailable — try again.')
      setMessages((prev) => prev.slice(0, -1))
      setInput(trimmed)
    } finally {
      setSending(false)
    }
  }

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    send(input)
  }

  return (
    <div className="mx-auto max-w-2xl flex flex-col h-[calc(100vh-160px)] min-h-[420px]">
      <div className="flex items-center justify-between gap-2 mb-4 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 bg-accent" aria-hidden="true" />
          <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">Ask Raksha AI</span>
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

      <div className="relative flex-1 min-h-0 border border-ink bg-paper/60 backdrop-blur-sm flex flex-col">
        <CornerBrackets />

        <div className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6 flex flex-col gap-3">
          {messages.length === 0 && (
            <div className="flex-1 flex flex-col items-center justify-center text-center gap-4 py-8">
              <p className="text-sm text-ink/60 max-w-xs">
                Ask anything about scams, UPI safety, or what to do if something already went wrong. Answers are
                grounded against Raksha AI's known scam pattern database.
              </p>
              <div className="flex flex-col gap-2 w-full max-w-sm">
                {EXAMPLE_PROMPTS.map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => send(p)}
                    className="border border-line bg-white px-3 py-2 text-left text-xs text-ink/80 hover:border-accent hover:text-ink transition-colors"
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[85%] px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words ${
                  m.role === 'user' ? 'bg-ink text-white' : 'border border-ink bg-white text-ink'
                }`}
              >
                {m.content}
                {m.role === 'assistant' && (
                  <button
                    type="button"
                    onClick={() => speak(m.content, i)}
                    className="mt-1.5 flex items-center gap-1 text-[10px] font-bold uppercase tracking-[0.1em] text-ink/40 hover:text-accent transition-colors"
                  >
                    <SpeakerIcon />
                    {speakingIndex === i ? 'Stop' : 'Read aloud'}
                  </button>
                )}
              </div>
            </div>
          ))}

          {sending && (
            <div className="flex justify-start">
              <div className="border border-ink bg-white px-3.5 py-2.5 text-sm text-ink/40">
                <span className="inline-flex gap-1">
                  <span className="animate-bounce [animation-delay:0ms]">•</span>
                  <span className="animate-bounce [animation-delay:150ms]">•</span>
                  <span className="animate-bounce [animation-delay:300ms]">•</span>
                </span>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {error && <p className="mx-4 mb-2 border border-red-600 bg-red-50 px-3 py-2 text-[11px] text-red-700">{error}</p>}

        <form onSubmit={handleSubmit} className="border-t border-line p-3 flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            maxLength={1000}
            placeholder="Ask about a scam, UPI safety, what to do next…"
            className="flex-1 border border-ink bg-white px-3 py-2 text-sm text-ink placeholder:text-ink/30 focus:outline-none focus:ring-2 focus:ring-accent"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="bg-accent px-4 py-2 text-xs font-bold uppercase tracking-[0.15em] text-accent-ink hover:bg-ink transition-colors disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  )
}
