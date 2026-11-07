import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowRight, Share2, Square, Volume2 } from 'lucide-react'
import { HighlightedText } from '../components/HighlightedText'
import { VerdictWord } from '../components/VerdictWord'
import { TraceViewer } from '../components/TraceViewer'
import { LANGUAGES, type LanguageOption } from '../lib/languages'
import { VERDICT_META, type ScanResult } from '../lib/scanResult'
import { cancelVoice, prefetchVoice, speak as speakText } from '../lib/voice'

interface ResultLocationState {
  result?: ScanResult
  sourceText?: string | null
  language?: LanguageOption['code']
}

export function ResultPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { result, sourceText, language } = (location.state as ResultLocationState | null) ?? {}
  const [speaking, setSpeaking] = useState(false)
  // The Indic providers take several seconds to return audio. Without a visible
  // "preparing" state the button looks broken, which is exactly what makes
  // people tap it repeatedly.
  const [preparing, setPreparing] = useState(false)
  const [voiceNote, setVoiceNote] = useState(false)

  // The result was generated in the language the scan was run in, so read it
  // back in that language rather than whatever is selected now.
  const resultLanguage = language ?? 'en'
  const speechText = result ? `${result.explanation}. ${result.recommended_action}` : ''

  // Start synthesising the moment the verdict appears, not when the button is
  // tapped. Reading the result takes a few seconds; borrowing that time turns a
  // ~8s wait into an instant play. Declared above the early return below because
  // hooks cannot run conditionally.
  useEffect(() => {
    if (!speechText) return
    void prefetchVoice(speechText, resultLanguage)
  }, [speechText, resultLanguage])

  if (!result) {
    return (
      <div className="max-w-2xl">
        <h1 className="swiss-display text-[clamp(2rem,7vw,3.5rem)]">{t('result.noResult')}</h1>
        <button
          type="button"
          onClick={() => navigate('/app')}
          className="mt-6 inline-flex min-h-11 items-center border-2 border-ink px-5 py-2 text-sm font-bold uppercase tracking-[0.08em] text-ink transition-colors hover:bg-ink hover:text-paper"
        >
          {t('result.backToScan')}
        </button>
      </div>
    )
  }

  const meta = VERDICT_META[result.verdict]
  const verdictLabel = t(meta.labelKey)
  const languageOption = LANGUAGES.find((l) => l.code === resultLanguage)
  const speechLang = languageOption?.speechLang ?? 'en-IN'

  const speak = async () => {
    if (speaking || preparing) {
      cancelVoice()
      setSpeaking(false)
      setPreparing(false)
      return
    }
    setPreparing(true)
    setVoiceNote(false)
    // Must be the identical string the prefetch used, or the cache misses.
    const { source, exactMatch, stale } = await speakText(
      speechText,
      {
        language: resultLanguage,
        speechLang,
        onEnd: () => setSpeaking(false),
        onError: () => setSpeaking(false),
      },
    )

    // A newer tap superseded this one; it owns the button state now.
    if (stale) return

    setPreparing(false)
    setSpeaking(true)
    if (source === 'browser' && !exactMatch) setVoiceNote(true)
  }

  const shareText = [
    `${t('result.shareCheckLabel')} — ${verdictLabel} (${result.risk_score}/100)`,
    result.explanation,
    `${t('result.shareWhatToDo')}: ${result.recommended_action}`,
  ].join('\n\n')

  const forwardToFamily = async () => {
    if (navigator.share) {
      try {
        await navigator.share({ title: t('result.shareAlertTitle'), text: shareText })
      } catch {
        // user cancelled the share sheet — not an error
      }
      return
    }
    window.open(`https://wa.me/?text=${encodeURIComponent(shareText)}`, '_blank', 'noopener')
  }

  return (
    <>
      <article className="relative grid grid-cols-12 gap-x-4 gap-y-8 sm:gap-x-6">
        <header className="col-span-12">
          <p className="swiss-label flex items-center gap-2 text-ink">
            <span className="h-2 w-2 bg-accent" aria-hidden="true" />
            {t('result.eyebrow')}
          </p>
          <div className="mt-4">
            <VerdictWord verdict={result.verdict} label={verdictLabel} />
          </div>
          <div className="mt-6 h-[3px] w-full bg-rule" aria-hidden="true" />
        </header>

        <div className="col-span-12 flex flex-col gap-4 md:col-span-4">
          <div>
            <p className="swiss-label text-ink">{t('result.riskScore')}</p>
            <p className={`mt-1 font-display text-6xl font-extrabold leading-none tracking-[-0.04em] ${meta.wordClass}`}>
              {result.risk_score}
              <span className="text-2xl text-ink/70">/100</span>
            </p>
            <div className="mt-3 h-2 w-full bg-line" aria-hidden="true">
              <div className={`h-full bg-current ${meta.wordClass}`} style={{ width: `${result.risk_score}%` }} />
            </div>
          </div>

          <button
            type="button"
            onClick={speak}
            className="flex min-h-11 items-center gap-2 self-start border-2 border-ink bg-paper px-4 py-2 text-sm font-bold uppercase tracking-[0.06em] text-ink transition-colors hover:bg-ink hover:text-paper"
          >
            {speaking || preparing ? <Square aria-hidden="true" size={18} /> : <Volume2 aria-hidden="true" size={18} />}
            {preparing ? t('result.preparing') : speaking ? t('result.stop') : t('result.readAloud')}
          </button>

          {voiceNote && (
            <p className="text-xs leading-relaxed text-ink/70">
              {t('result.noVoiceInstalled', { language: languageOption?.label ?? t('result.thisLanguage') })}
            </p>
          )}
        </div>

        <div className="col-span-12 flex flex-col gap-8 bg-paper md:col-span-8">
          <section className="border-l-4 border-accent pl-4">
            <h2 className="swiss-label font-sans text-ink">{t('result.whatToDo')}</h2>
            <p className="mt-2 font-display text-xl font-bold leading-snug tracking-[-0.01em] text-ink sm:text-2xl">
              {result.recommended_action}
            </p>
          </section>

          <section>
            <h2 className="swiss-label font-sans text-ink">{t('result.why')}</h2>
            <p className="mt-2 text-base leading-relaxed text-ink">{result.explanation}</p>
          </section>

          {sourceText && (
            <section>
              <h2 className="swiss-label font-sans text-ink">{t('result.flaggedPhrasesInContext')}</h2>
              <div className="mt-2 border-t border-rule pt-3">
                <HighlightedText text={sourceText} phrases={result.flagged_phrases} />
              </div>
            </section>
          )}

          {!sourceText && result.flagged_phrases.length > 0 && (
            <section>
              <h2 className="swiss-label font-sans text-ink">{t('result.flaggedPhrases')}</h2>
              <ul className="mt-2 flex flex-wrap gap-2">
                {result.flagged_phrases.map((phrase, i) => (
                  <li key={i} className="border-b-2 border-accent bg-accent/10 px-2 py-1 text-sm text-ink">
                    {phrase}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <p className="text-sm text-ink/70">{t('result.reported', { count: result.community_report_count })}</p>

          <TraceViewer result={result} />

          <div className="flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={forwardToFamily}
              className="flex min-h-12 flex-1 items-center justify-between gap-2 bg-accent px-5 py-3 text-left text-sm font-bold uppercase tracking-[0.08em] text-accent-ink transition-colors hover:bg-ink"
            >
              {t('result.forwardToFamily')}
              <Share2 aria-hidden="true" size={18} />
            </button>
            <button
              type="button"
              onClick={() => navigate('/app')}
              className="flex min-h-12 flex-1 items-center justify-between gap-2 border-2 border-ink bg-paper px-5 py-3 text-left text-sm font-bold uppercase tracking-[0.08em] text-ink transition-colors hover:bg-ink hover:text-paper"
            >
              {t('result.scanAnother')}
              <ArrowRight aria-hidden="true" size={18} />
            </button>
          </div>
        </div>
      </article>
    </>
  )
}
