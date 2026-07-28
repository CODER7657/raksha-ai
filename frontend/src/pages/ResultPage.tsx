import { useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { CornerBrackets } from '../components/CornerBrackets'
import { LANGUAGES, type LanguageOption } from '../lib/languages'
import type { ScanResult, Verdict } from '../lib/scanResult'

interface ResultLocationState {
  result?: ScanResult
  sourceText?: string | null
  language?: LanguageOption['code']
}

const VERDICT_META: Record<Verdict, { label: string; badgeClass: string; barClass: string }> = {
  safe: { label: 'Safe', badgeClass: 'bg-emerald-600 text-white', barClass: 'bg-emerald-600' },
  suspicious: { label: 'Suspicious', badgeClass: 'bg-amber-500 text-white', barClass: 'bg-amber-500' },
  high_risk: { label: 'High Risk', badgeClass: 'bg-red-600 text-white', barClass: 'bg-red-600' },
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function HighlightedSource({ text, phrases }: { text: string; phrases: string[] }) {
  const parts = useMemo(() => {
    const cleanPhrases = phrases.filter((p) => p.trim().length > 0)
    if (cleanPhrases.length === 0) return [{ text, flagged: false }]

    const pattern = new RegExp(`(${cleanPhrases.map(escapeRegExp).join('|')})`, 'gi')
    return text.split(pattern).map((chunk) => ({
      text: chunk,
      flagged: cleanPhrases.some((p) => p.toLowerCase() === chunk.toLowerCase()),
    }))
  }, [text, phrases])

  return (
    <p className="text-sm text-ink leading-relaxed whitespace-pre-wrap break-words">
      {parts.map((part, i) =>
        part.flagged ? (
          <mark key={i} className="bg-accent/25 text-ink px-0.5 underline decoration-accent decoration-2">
            {part.text}
          </mark>
        ) : (
          <span key={i}>{part.text}</span>
        ),
      )}
    </p>
  )
}

function SpeakerIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" aria-hidden="true">
      <path d="M4 9v6h4l5 4V5L8 9H4Z" fill="currentColor" />
      <path d="M16.5 8.5a5 5 0 0 1 0 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M19 6a8.5 8.5 0 0 1 0 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

export function ResultPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const { result, sourceText, language } = (location.state as ResultLocationState | null) ?? {}
  const [speaking, setSpeaking] = useState(false)

  if (!result) {
    return (
      <div className="mx-auto max-w-2xl text-center">
        <p className="text-sm text-ink/60 mb-4">No scan result to show.</p>
        <button
          onClick={() => navigate('/app')}
          className="border border-ink px-4 py-2 text-xs font-bold uppercase tracking-[0.15em] text-ink hover:bg-ink hover:text-white transition-colors"
        >
          Back to scan
        </button>
      </div>
    )
  }

  const meta = VERDICT_META[result.verdict]
  const speechLang = LANGUAGES.find((l) => l.code === language)?.speechLang ?? 'en-IN'

  const speak = () => {
    if (speaking) {
      window.speechSynthesis.cancel()
      setSpeaking(false)
      return
    }
    const utterance = new SpeechSynthesisUtterance(`${result.explanation}. ${result.recommended_action}`)
    utterance.lang = speechLang
    utterance.onend = () => setSpeaking(false)
    utterance.onerror = () => setSpeaking(false)
    window.speechSynthesis.speak(utterance)
    setSpeaking(true)
  }

  const shareText = [
    `Raksha AI scam check — ${meta.label} (${result.risk_score}/100)`,
    result.explanation,
    `What to do: ${result.recommended_action}`,
  ].join('\n\n')

  const forwardToFamily = async () => {
    if (navigator.share) {
      try {
        await navigator.share({ title: 'Raksha AI scam alert', text: shareText })
      } catch {
        // user cancelled the share sheet — not an error
      }
      return
    }
    window.open(`https://wa.me/?text=${encodeURIComponent(shareText)}`, '_blank', 'noopener')
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="flex items-center gap-2 mb-6">
        <span className="h-2 w-2 bg-accent" aria-hidden="true" />
        <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">Scan result</span>
      </div>

      <div className="relative border border-ink bg-paper/60 backdrop-blur-sm p-6 sm:p-8">
        <CornerBrackets />

        <div className="flex items-center justify-between gap-3 flex-wrap mb-5">
          <span className={`px-3 py-1 text-xs font-bold uppercase tracking-[0.15em] ${meta.badgeClass}`}>
            {meta.label}
          </span>
          <button
            type="button"
            onClick={speak}
            className="flex items-center gap-1.5 border border-ink px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.1em] text-ink hover:bg-ink hover:text-white transition-colors"
          >
            <SpeakerIcon />
            {speaking ? 'Stop' : 'Read aloud'}
          </button>
        </div>

        <div className="mb-6">
          <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-[0.15em] text-ink/60 mb-1">
            <span>Risk score</span>
            <span>{result.risk_score}/100</span>
          </div>
          <div className="h-2 w-full border border-ink bg-white">
            <div className={`h-full ${meta.barClass}`} style={{ width: `${result.risk_score}%` }} />
          </div>
        </div>

        {sourceText && (
          <div className="mb-6">
            <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70">
              Flagged phrases in context
            </span>
            <div className="mt-1.5 border border-line p-3 bg-white">
              <HighlightedSource text={sourceText} phrases={result.flagged_phrases} />
            </div>
          </div>
        )}

        {!sourceText && result.flagged_phrases.length > 0 && (
          <div className="mb-6">
            <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70">Flagged phrases</span>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {result.flagged_phrases.map((phrase, i) => (
                <span key={i} className="bg-accent/25 border border-accent px-2 py-0.5 text-xs text-ink">
                  {phrase}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="mb-6">
          <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70">Why</span>
          <p className="mt-1.5 text-sm text-ink leading-relaxed">{result.explanation}</p>
        </div>

        <div className="border-l-4 border-accent bg-orange-50 px-4 py-3 mb-6">
          <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70">What to do</span>
          <p className="mt-1 text-sm text-ink leading-relaxed">{result.recommended_action}</p>
        </div>

        <p className="text-[11px] text-ink/50 mb-6">
          This exact message has been reported {result.community_report_count} time
          {result.community_report_count === 1 ? '' : 's'} by the Raksha AI community.
        </p>

        <div className="flex flex-col sm:flex-row gap-2">
          <button
            type="button"
            onClick={forwardToFamily}
            className="flex-1 bg-accent px-4 py-2.5 text-xs font-bold uppercase tracking-[0.15em] text-accent-ink hover:bg-ink transition-colors"
          >
            Forward to family
          </button>
          <button
            type="button"
            onClick={() => navigate('/app')}
            className="flex-1 border border-ink px-4 py-2.5 text-xs font-bold uppercase tracking-[0.15em] text-ink hover:bg-ink hover:text-white transition-colors"
          >
            Scan another
          </button>
        </div>
      </div>
    </div>
  )
}
