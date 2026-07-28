import { useEffect, useState } from 'react'
import { apiFetch } from '../lib/api'
import { CornerBrackets } from '../components/CornerBrackets'
import { HighlightedText } from '../components/HighlightedText'
import { VERDICT_META, type Verdict } from '../lib/scanResult'
import type { HistoryEntry } from '../lib/historyEntry'
import { LANGUAGES } from '../lib/languages'

const VERDICT_ORDER: Verdict[] = ['high_risk', 'suspicious', 'safe']

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function languageLabel(code: string) {
  return LANGUAGES.find((l) => l.code === code)?.label ?? code
}

export function HistoryPage() {
  const [entries, setEntries] = useState<HistoryEntry[] | null>(null)
  const [error, setError] = useState('')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    apiFetch('/api/history')
      .then((data: HistoryEntry[]) => setEntries(data))
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load history'))
  }, [])

  if (error) {
    return (
      <div className="mx-auto max-w-2xl">
        <p className="border border-red-600 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      </div>
    )
  }

  if (!entries) {
    return (
      <div className="mx-auto max-w-2xl">
        <p className="text-sm text-ink/60">Loading history…</p>
      </div>
    )
  }

  const counts: Record<Verdict, number> = { safe: 0, suspicious: 0, high_risk: 0 }
  for (const entry of entries) counts[entry.verdict]++
  const flaggedCount = counts.suspicious + counts.high_risk
  const maxCount = Math.max(...VERDICT_ORDER.map((v) => counts[v]), 1)

  return (
    <div className="mx-auto max-w-2xl flex flex-col gap-8">
      <div>
        <div className="flex items-center gap-2 mb-6">
          <span className="h-2 w-2 bg-accent" aria-hidden="true" />
          <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">History dashboard</span>
        </div>

        <div className="relative border border-ink bg-paper/60 backdrop-blur-sm p-6 sm:p-8">
          <CornerBrackets />
          <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70">
            Your community scam radar
          </span>
          <p className="mt-2 text-2xl font-extrabold text-ink">{flaggedCount}</p>
          <p className="mt-1 text-xs text-ink/60">
            risky message{flaggedCount === 1 ? '' : 's'} you've helped flag with Raksha AI.
            Community-wide totals across all users are coming soon.
          </p>
        </div>
      </div>

      {entries.length > 0 && (
        <div className="relative border border-ink bg-paper/60 backdrop-blur-sm p-6 sm:p-8">
          <CornerBrackets />
          <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70">Scam type trend</span>
          <div className="mt-3 flex flex-col gap-2">
            {VERDICT_ORDER.map((v) => (
              <div key={v} className="flex items-center gap-3">
                <span className="w-20 shrink-0 text-[10px] font-bold uppercase tracking-[0.1em] text-ink/70">
                  {VERDICT_META[v].label}
                </span>
                <div className="h-2 flex-1 border border-ink bg-white">
                  <div
                    className={`h-full ${VERDICT_META[v].barClass}`}
                    style={{ width: `${(counts[v] / maxCount) * 100}%` }}
                  />
                </div>
                <span className="w-6 shrink-0 text-right text-[10px] text-ink/60">{counts[v]}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
        <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70">Past scans</span>

        {entries.length === 0 ? (
          <div className="relative border border-ink bg-paper/60 backdrop-blur-sm p-6 sm:p-8 mt-2 text-center">
            <CornerBrackets />
            <p className="text-sm text-ink/60">No scans yet — go check a message.</p>
          </div>
        ) : (
          <ul className="mt-2 flex flex-col gap-2">
            {entries.map((entry) => {
              const meta = VERDICT_META[entry.verdict]
              const isExpanded = expandedId === entry.id
              return (
                <li key={entry.id} className="border border-ink bg-white">
                  <button
                    type="button"
                    onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left"
                  >
                    <span className={`shrink-0 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.1em] ${meta.badgeClass}`}>
                      {meta.label}
                    </span>
                    <span className="flex-1 truncate text-sm text-ink">{entry.input_text}</span>
                    <span className="shrink-0 text-[10px] text-ink/50">{formatDate(entry.created_at)}</span>
                  </button>

                  {isExpanded && (
                    <div className="border-t border-line px-4 py-4 flex flex-col gap-3">
                      <div className="flex items-center justify-between text-[10px] text-ink/50 uppercase tracking-[0.1em]">
                        <span>{languageLabel(entry.language)}</span>
                        <span>{entry.risk_score}/100</span>
                      </div>
                      <HighlightedText text={entry.input_text} phrases={entry.flagged_phrases} />
                      <p className="text-sm text-ink leading-relaxed">{entry.explanation}</p>
                      <div className="border-l-4 border-accent bg-orange-50 px-3 py-2">
                        <p className="text-sm text-ink leading-relaxed">{entry.recommended_action}</p>
                      </div>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
