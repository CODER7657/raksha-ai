import { useState } from 'react'
import { CornerBrackets } from '../components/CornerBrackets'
import { VERDICT_META } from '../lib/scanResult'
import { SIMULATOR_QUESTIONS } from '../lib/simulatorData'

type ChipState = 'idle' | 'correct' | 'missed' | 'wrong'

export function PracticePage() {
  const [index, setIndex] = useState(0)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [revealed, setRevealed] = useState(false)
  const [correctCount, setCorrectCount] = useState(0)
  const [finished, setFinished] = useState(false)

  const question = SIMULATOR_QUESTIONS[index]

  const toggle = (phrase: string) => {
    if (revealed) return
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(phrase)) next.delete(phrase)
      else next.add(phrase)
      return next
    })
  }

  const chipState = (phrase: string): ChipState => {
    if (!revealed) return 'idle'
    const isFlagged = question.flaggedPhrases.includes(phrase)
    const isSelected = selected.has(phrase)
    if (isFlagged && isSelected) return 'correct'
    if (isFlagged && !isSelected) return 'missed'
    if (!isFlagged && isSelected) return 'wrong'
    return 'idle'
  }

  const reveal = () => {
    const flaggedSet = new Set(question.flaggedPhrases)
    const isExactMatch =
      selected.size === flaggedSet.size && [...selected].every((p) => flaggedSet.has(p))
    if (isExactMatch) setCorrectCount((c) => c + 1)
    setRevealed(true)
  }

  const next = () => {
    if (index + 1 >= SIMULATOR_QUESTIONS.length) {
      setFinished(true)
      return
    }
    setIndex((i) => i + 1)
    setSelected(new Set())
    setRevealed(false)
  }

  const restart = () => {
    setIndex(0)
    setSelected(new Set())
    setRevealed(false)
    setCorrectCount(0)
    setFinished(false)
  }

  if (finished) {
    return (
      <div className="mx-auto max-w-2xl text-center">
        <div className="relative border border-ink bg-paper/60 backdrop-blur-sm p-6 sm:p-8">
          <CornerBrackets />
          <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70">Quiz complete</span>
          <p className="mt-2 text-3xl font-extrabold text-ink">
            {correctCount}/{SIMULATOR_QUESTIONS.length}
          </p>
          <p className="mt-1 text-xs text-ink/60">messages you spotted correctly.</p>
          <button
            type="button"
            onClick={restart}
            className="mt-6 bg-accent px-4 py-2.5 text-xs font-bold uppercase tracking-[0.15em] text-accent-ink hover:bg-ink transition-colors"
          >
            Play again
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="flex items-center justify-between gap-2 mb-6">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 bg-accent" aria-hidden="true" />
          <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">Scam spotter</span>
        </div>
        <span className="text-[11px] text-ink/50">
          {index + 1}/{SIMULATOR_QUESTIONS.length}
        </span>
      </div>

      <div className="relative border border-ink bg-paper/60 backdrop-blur-sm p-6 sm:p-8">
        <CornerBrackets />

        <p className="text-sm text-ink leading-relaxed whitespace-pre-wrap break-words mb-5">{question.message}</p>

        <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70">
          Tap the phrases that seem like red flags
        </span>
        <div className="mt-2 flex flex-wrap gap-2">
          {question.candidatePhrases.map((phrase) => {
            const state = chipState(phrase)
            const isSelected = selected.has(phrase)
            return (
              <button
                key={phrase}
                type="button"
                onClick={() => toggle(phrase)}
                disabled={revealed}
                className={`px-3 py-1.5 text-xs border transition-colors ${
                  state === 'correct'
                    ? 'bg-emerald-600 border-emerald-600 text-white'
                    : state === 'wrong'
                      ? 'bg-red-600 border-red-600 text-white'
                      : state === 'missed'
                        ? 'border-accent text-ink bg-orange-50'
                        : isSelected
                          ? 'bg-ink border-ink text-white'
                          : 'border-ink text-ink hover:bg-ink/5'
                }`}
              >
                {phrase}
              </button>
            )
          })}
        </div>

        {revealed && (
          <div className="mt-5 flex flex-col gap-3">
            <span className={`self-start px-3 py-1 text-xs font-bold uppercase tracking-[0.15em] ${VERDICT_META[question.verdict].badgeClass}`}>
              {VERDICT_META[question.verdict].label}
            </span>
            <p className="text-sm text-ink leading-relaxed">{question.explanation}</p>
          </div>
        )}

        <div className="mt-6">
          {revealed ? (
            <button
              type="button"
              onClick={next}
              className="w-full bg-accent px-4 py-2.5 text-xs font-bold uppercase tracking-[0.15em] text-accent-ink hover:bg-ink transition-colors"
            >
              {index + 1 >= SIMULATOR_QUESTIONS.length ? 'See results' : 'Next message'}
            </button>
          ) : (
            <button
              type="button"
              onClick={reveal}
              className="w-full border border-ink px-4 py-2.5 text-xs font-bold uppercase tracking-[0.15em] text-ink hover:bg-ink hover:text-white transition-colors"
            >
              Reveal
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
