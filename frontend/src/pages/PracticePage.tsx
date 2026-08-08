import { useCallback, useEffect, useRef, useState, type PointerEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../lib/api'
import { LanguageSelect } from '../components/LanguageSelect'
import { useLanguage } from '../context/LanguageContext'
import { CornerBrackets } from '../components/CornerBrackets'
import { TiltCard } from '../components/TiltCard'
import { HighlightedText } from '../components/HighlightedText'

interface PracticeQuestion {
  id: string
  text: string
  is_scam: boolean
  category: string
  category_label: string
  red_flags: string[]
  tip: string
}

type Stage = 'start' | 'loading' | 'playing' | 'finished'

const DRAG_THRESHOLD = 110
const BEST_KEY_PREFIX = 'raksha_practice_best_'

function tierKeysFor(pct: number): { titleKey: string; blurbKey: string } {
  if (pct >= 90) return { titleKey: 'practice.tierEliteTitle', blurbKey: 'practice.tierEliteBlurb' }
  if (pct >= 70) return { titleKey: 'practice.tierSharpTitle', blurbKey: 'practice.tierSharpBlurb' }
  if (pct >= 50) return { titleKey: 'practice.tierGettingThereTitle', blurbKey: 'practice.tierGettingThereBlurb' }
  return { titleKey: 'practice.tierStayAlertTitle', blurbKey: 'practice.tierStayAlertBlurb' }
}

export function PracticePage() {
  const { t } = useTranslation()
  const [stage, setStage] = useState<Stage>('start')
  const { language, option, isTranslated } = useLanguage()
  const [questions, setQuestions] = useState<PracticeQuestion[]>([])
  const [index, setIndex] = useState(0)
  const [score, setScore] = useState(0)
  const [streak, setStreak] = useState(0)
  const [bestStreak, setBestStreak] = useState(0)
  const [answered, setAnswered] = useState(false)
  const [lastCorrect, setLastCorrect] = useState(false)
  const [lastGuessScam, setLastGuessScam] = useState(false)
  const [error, setError] = useState('')

  const [dragX, setDragX] = useState(0)
  const [dragging, setDragging] = useState(false)
  const dragStartX = useRef(0)

  const bestKey = `${BEST_KEY_PREFIX}${language}`
  const [best, setBest] = useState<number | null>(null)

  useEffect(() => {
    const stored = localStorage.getItem(bestKey)
    setBest(stored ? Number(stored) : null)
  }, [bestKey])

  const current = questions[index]

  const startRound = useCallback(async () => {
    setError('')
    setStage('loading')
    try {
      const round = await apiFetch(`/api/practice/round?language=${language}&count=8`)
      setQuestions(round.questions)
      setIndex(0)
      setScore(0)
      setStreak(0)
      setBestStreak(0)
      setAnswered(false)
      setDragX(0)
      setStage('playing')
    } catch (err) {
      setError(err instanceof Error ? err.message : t('practice.loadError'))
      setStage('start')
    }
  }, [language, t])

  const commitAnswer = (guessScam: boolean) => {
    if (answered || !current) return
    const correct = guessScam === current.is_scam
    setLastCorrect(correct)
    setLastGuessScam(guessScam)
    setAnswered(true)
    setDragX(guessScam ? 400 : -400)
    if (correct) {
      setScore((s) => s + 1)
      setStreak((s) => {
        const next = s + 1
        setBestStreak((b) => Math.max(b, next))
        return next
      })
    } else {
      setStreak(0)
    }
  }

  const nextQuestion = () => {
    if (index + 1 >= questions.length) {
      const pct = Math.round((score / questions.length) * 100)
      if (best === null || pct > best) {
        localStorage.setItem(bestKey, String(pct))
        setBest(pct)
      }
      setStage('finished')
      return
    }
    setIndex((i) => i + 1)
    setAnswered(false)
    setDragX(0)
  }

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    if (answered) return
    setDragging(true)
    dragStartX.current = e.clientX - dragX
  }
  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    if (!dragging || answered) return
    setDragX(e.clientX - dragStartX.current)
  }
  const endDrag = () => {
    if (!dragging) return
    setDragging(false)
    if (answered) return
    if (dragX > DRAG_THRESHOLD) commitAnswer(true)
    else if (dragX < -DRAG_THRESHOLD) commitAnswer(false)
    else setDragX(0)
  }

  useEffect(() => {
    if (stage !== 'playing') return
    const onKey = (e: KeyboardEvent) => {
      if (answered) {
        if (e.key === 'Enter' || e.key === ' ') nextQuestion()
        return
      }
      if (e.key === 'ArrowRight') commitAnswer(true)
      if (e.key === 'ArrowLeft') commitAnswer(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage, answered, current])

  if (stage === 'start' || stage === 'loading') {
    return (
      <div className="mx-auto max-w-2xl">
        <div className="flex items-center gap-2 mb-6">
          <span className="h-2 w-2 bg-accent" aria-hidden="true" />
          <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">{t('practice.eyebrow')}</span>
        </div>

        <div className="relative border border-ink bg-paper/60 backdrop-blur-sm p-6 sm:p-8">
          <CornerBrackets />
          <h1 className="text-xl font-extrabold uppercase tracking-tight text-ink mb-2">{t('practice.title')}</h1>
          <p className="text-sm text-ink/70 leading-relaxed mb-6">{t('practice.intro')}</p>

          {!isTranslated && (
            <p className="mb-6 border border-line bg-white/60 px-3 py-2 text-[10px] leading-relaxed text-ink/50">
              {t('practice.untranslatedNote', { language: option.label })}
            </p>
          )}

          <label className="flex flex-col gap-1.5 mb-6">
            <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70">{t('common.language')}</span>
            <LanguageSelect className="px-3 py-2 text-sm" />
          </label>

          {best !== null && (
            <p className="mb-4 text-[11px] text-ink/50">
              {t('practice.bestScore', { score: best })}
            </p>
          )}

          {error && <p className="mb-4 border border-red-600 bg-red-50 px-3 py-2 text-[11px] text-red-700">{error}</p>}

          <button
            type="button"
            onClick={startRound}
            disabled={stage === 'loading'}
            className="w-full bg-accent px-4 py-2.5 text-xs font-bold uppercase tracking-[0.15em] text-accent-ink hover:bg-ink transition-colors disabled:opacity-50"
          >
            {stage === 'loading' ? t('practice.loading') : t('practice.startPractice')}
          </button>
        </div>
      </div>
    )
  }

  if (stage === 'finished') {
    const pct = Math.round((score / questions.length) * 100)
    const tier = tierKeysFor(pct)
    return (
      <div className="mx-auto max-w-2xl">
        <div className="flex items-center gap-2 mb-6">
          <span className="h-2 w-2 bg-accent" aria-hidden="true" />
          <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">{t('practice.roundComplete')}</span>
        </div>

        <div className="relative border border-ink bg-paper/60 backdrop-blur-sm p-6 sm:p-8 text-center">
          <CornerBrackets />
          <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-accent mb-2">{t(tier.titleKey)}</p>
          <p className="text-4xl font-extrabold text-ink mb-1">
            {score}/{questions.length}
          </p>
          <p className="text-sm text-ink/60 mb-1">{t('practice.percentCorrect', { pct, streak: bestStreak })}</p>
          <p className="text-sm text-ink/70 leading-relaxed mt-4 mb-6">{t(tier.blurbKey)}</p>

          {best !== null && (
            <p className="text-[11px] text-ink/50 mb-6">{t('practice.bestScore', { score: best })}</p>
          )}

          <div className="flex flex-col sm:flex-row gap-2">
            <button
              type="button"
              onClick={startRound}
              className="flex-1 bg-accent px-4 py-2.5 text-xs font-bold uppercase tracking-[0.15em] text-accent-ink hover:bg-ink transition-colors"
            >
              {t('practice.playAgain')}
            </button>
            <button
              type="button"
              onClick={() => setStage('start')}
              className="flex-1 border border-ink px-4 py-2.5 text-xs font-bold uppercase tracking-[0.15em] text-ink hover:bg-ink hover:text-white transition-colors"
            >
              {t('practice.changeLanguage')}
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (!current) return null

  const rotate = dragX / 18
  const opacity = answered ? 1 : Math.max(0.4, 1 - Math.abs(dragX) / 600)

  return (
    <div className="mx-auto max-w-2xl">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 bg-accent" aria-hidden="true" />
          <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">
            {t('practice.questionCounter', { current: index + 1, total: questions.length })}
          </span>
        </div>
        <div className="flex items-center gap-4 text-[11px] font-bold uppercase tracking-[0.1em]">
          <span className="text-ink/70">{t('practice.score', { score })}</span>
          {streak >= 2 && <span className="text-accent">🔥 {streak}</span>}
        </div>
      </div>

      <div className="h-1.5 w-full border border-ink bg-white mb-6">
        <div
          className="h-full bg-accent transition-all"
          style={{ width: `${((index + (answered ? 1 : 0)) / questions.length) * 100}%` }}
        />
      </div>

      <div className="relative select-none" style={{ touchAction: 'pan-y' }}>
        <TiltCard>
          <div
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={endDrag}
            onPointerLeave={endDrag}
            style={{
              transform: `translateX(${dragX}px) rotate(${rotate}deg)`,
              opacity,
              transition: dragging ? 'none' : 'transform 300ms ease-out, opacity 300ms ease-out',
              cursor: answered ? 'default' : 'grab',
            }}
            className="relative border border-ink bg-white p-6 sm:p-8 min-h-[220px] flex flex-col justify-center"
          >
            <CornerBrackets />
            <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/40 mb-3">{t('practice.isThisAScam')}</p>
            <p className="text-base sm:text-lg text-ink leading-relaxed">{current.text}</p>
          </div>
        </TiltCard>

        {!answered && (
          <div className="mt-5 flex gap-2">
            <button
              type="button"
              onClick={() => commitAnswer(false)}
              className="flex-1 border-2 border-emerald-600 text-emerald-700 py-3 text-xs font-bold uppercase tracking-[0.15em] hover:bg-emerald-600 hover:text-white transition-colors"
            >
              ✅ {t('practice.safe')}
            </button>
            <button
              type="button"
              onClick={() => commitAnswer(true)}
              className="flex-1 border-2 border-red-600 text-red-700 py-3 text-xs font-bold uppercase tracking-[0.15em] hover:bg-red-600 hover:text-white transition-colors"
            >
              🚩 {t('practice.scamAnswer')}
            </button>
          </div>
        )}

        {answered && (
          <div className="mt-5 relative border border-ink bg-paper/60 backdrop-blur-sm p-5">
            <CornerBrackets />
            <p
              className={`text-sm font-bold uppercase tracking-[0.1em] mb-3 ${
                lastCorrect ? 'text-emerald-700' : 'text-red-700'
              }`}
            >
              {lastCorrect ? `✅ ${t('practice.correct')}` : `❌ ${lastGuessScam ? t('practice.notQuiteScam') : t('practice.notQuiteSafe')}`}
              <span className="ml-2 font-normal normal-case text-ink/50 tracking-normal">
                · {current.is_scam ? t('practice.actuallyScam') : t('practice.actuallySafe')} ({current.category_label})
              </span>
            </p>

            {current.is_scam && current.red_flags.length > 0 && (
              <div className="mb-3">
                <HighlightedText text={current.text} phrases={current.red_flags} />
              </div>
            )}

            <p className="text-sm text-ink/80 leading-relaxed mb-4">{current.tip}</p>

            <button
              type="button"
              onClick={nextQuestion}
              className="w-full bg-accent px-4 py-2.5 text-xs font-bold uppercase tracking-[0.15em] text-accent-ink hover:bg-ink transition-colors"
            >
              {index + 1 >= questions.length ? t('practice.seeResults') : t('practice.next')}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
