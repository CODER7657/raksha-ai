import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { CornerBrackets } from '../components/CornerBrackets'
import { HighlightedText } from '../components/HighlightedText'
import { LANGUAGES, type LanguageOption } from '../lib/languages'
import { VERDICT_META, type ScanResult } from '../lib/scanResult'
import { cancelVoice, speak as speakText } from '../lib/voice'

interface ResultLocationState {
  result?: ScanResult
  sourceText?: string | null
  language?: LanguageOption['code']
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
  const [voiceNote, setVoiceNote] = useState(false)

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
  // The result was generated in the language the scan was run in, so read it
  // back in that language rather than whatever is selected now.
  const resultLanguage = language ?? 'en'
  const languageOption = LANGUAGES.find((l) => l.code === resultLanguage)
  const speechLang = languageOption?.speechLang ?? 'en-IN'

  const speak = async () => {
    if (speaking) {
      cancelVoice()
      setSpeaking(false)
      return
    }
    setSpeaking(true)
    setVoiceNote(false)
    const { source, exactMatch } = await speakText(
      `${result.explanation}. ${result.recommended_action}`,
      {
        language: resultLanguage,
        speechLang,
        onEnd: () => setSpeaking(false),
        onError: () => setSpeaking(false),
      },
    )
    if (source === 'browser' && !exactMatch) setVoiceNote(true)
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

        {voiceNote && (
          <p className="-mt-3 mb-5 text-[10px] text-ink/40 leading-relaxed">
            This device has no installed {languageOption?.label ?? 'this language'} voice — reading with the
            closest available voice, pronunciation may be off.
          </p>
        )}

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
              <HighlightedText text={sourceText} phrases={result.flagged_phrases} />
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
