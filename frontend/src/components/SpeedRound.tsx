import { useEffect, useRef, useState } from 'react'
import { CornerBrackets } from './CornerBrackets'
import { SIMULATOR_QUESTIONS } from '../lib/simulatorData'

const ROUND_SECONDS = 30

interface Round {
  id: string
  message: string
  isScam: boolean
}

function shuffledRounds(): Round[] {
  const rounds: Round[] = SIMULATOR_QUESTIONS.map((q) => ({
    id: q.id,
    message: q.message,
    isScam: q.verdict !== 'safe',
  }))
  // Fisher-Yates — plays differently each round instead of the same fixed order.
  for (let i = rounds.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[rounds[i], rounds[j]] = [rounds[j], rounds[i]]
  }
  return rounds
}

/** Fast-paced binary safe/scam swipe game — same underlying message pool as
 * the Scam Spotter mode, but tests gut-instinct speed instead of careful
 * phrase-picking. Loops the (small) pool with a fresh shuffle each lap so a
 * 30s round doesn't run dry. */
export function SpeedRound() {
  const [started, setStarted] = useState(false)
  const [timeLeft, setTimeLeft] = useState(ROUND_SECONDS)
  const [rounds, setRounds] = useState<Round[]>([])
  const [cursor, setCursor] = useState(0)
  const [correct, setCorrect] = useState(0)
  const [attempted, setAttempted] = useState(0)
  const [flash, setFlash] = useState<'correct' | 'wrong' | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

  const start = () => {
    setRounds(shuffledRounds())
    setCursor(0)
    setCorrect(0)
    setAttempted(0)
    setTimeLeft(ROUND_SECONDS)
    setStarted(true)

    timerRef.current = setInterval(() => {
      setTimeLeft((t) => {
        if (t <= 1) {
          if (timerRef.current) clearInterval(timerRef.current)
          setStarted(false)
          return 0
        }
        return t - 1
      })
    }, 1000)
  }

  const answer = (choseScam: boolean) => {
    if (!started || rounds.length === 0) return
    const current = rounds[cursor % rounds.length]
    const isCorrect = choseScam === current.isScam
    setAttempted((a) => a + 1)
    if (isCorrect) setCorrect((c) => c + 1)
    setFlash(isCorrect ? 'correct' : 'wrong')
    setTimeout(() => setFlash(null), 200)

    setCursor((c) => {
      const next = c + 1
      if (next % rounds.length === 0) {
        // Lapped the pool — reshuffle so it doesn't repeat in the same order.
        setRounds(shuffledRounds())
      }
      return next
    })
  }

  if (!started && attempted === 0) {
    return (
      <div className="relative border border-ink bg-paper/60 backdrop-blur-sm p-6 sm:p-8 text-center">
        <CornerBrackets />
        <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70">Speed round</span>
        <p className="mt-2 text-sm text-ink/70 leading-relaxed max-w-sm mx-auto">
          {ROUND_SECONDS} seconds. Messages flash by one at a time — tap SAFE or SCAM as fast as you
          can. Tests gut instinct, not careful reading.
        </p>
        <button
          type="button"
          onClick={start}
          className="mt-6 bg-accent px-6 py-3 text-xs font-bold uppercase tracking-[0.15em] text-accent-ink hover:bg-ink transition-colors"
        >
          Start {ROUND_SECONDS}s round
        </button>
      </div>
    )
  }

  if (!started && attempted > 0) {
    const accuracy = Math.round((correct / attempted) * 100)
    return (
      <div className="relative border border-ink bg-paper/60 backdrop-blur-sm p-6 sm:p-8 text-center">
        <CornerBrackets />
        <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70">Time's up</span>
        <p className="mt-2 text-3xl font-extrabold text-ink">
          {correct}/{attempted}
        </p>
        <p className="mt-1 text-xs text-ink/60">
          correct out of {attempted} in {ROUND_SECONDS}s — {accuracy}% accuracy.
        </p>
        <button
          type="button"
          onClick={start}
          className="mt-6 bg-accent px-6 py-3 text-xs font-bold uppercase tracking-[0.15em] text-accent-ink hover:bg-ink transition-colors"
        >
          Go again
        </button>
      </div>
    )
  }

  const current = rounds[cursor % rounds.length]

  return (
    <div
      className={`relative border p-6 sm:p-8 transition-colors ${
        flash === 'correct'
          ? 'border-emerald-600 bg-emerald-50'
          : flash === 'wrong'
            ? 'border-red-600 bg-red-50'
            : 'border-ink bg-paper/60'
      }`}
    >
      <CornerBrackets />
      <div className="flex items-center justify-between mb-5">
        <span className="text-[11px] font-bold uppercase tracking-[0.1em] text-ink/60">
          Score: {correct}/{attempted}
        </span>
        <span className="text-lg font-extrabold text-accent tabular-nums">{timeLeft}s</span>
      </div>

      <p className="text-base text-ink leading-relaxed whitespace-pre-wrap break-words mb-6 min-h-[4rem]">
        {current?.message}
      </p>

      <div className="grid grid-cols-2 gap-3">
        <button
          type="button"
          onClick={() => answer(false)}
          className="border-2 border-emerald-600 py-4 text-sm font-bold uppercase tracking-[0.15em] text-emerald-700 hover:bg-emerald-600 hover:text-white transition-colors"
        >
          Safe
        </button>
        <button
          type="button"
          onClick={() => answer(true)}
          className="border-2 border-red-600 py-4 text-sm font-bold uppercase tracking-[0.15em] text-red-700 hover:bg-red-600 hover:text-white transition-colors"
        >
          Scam
        </button>
      </div>
    </div>
  )
}
