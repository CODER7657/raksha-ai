import { useEffect, useState } from 'react'
import { CornerBrackets } from '../components/CornerBrackets'
import { apiFetch } from '../lib/api'

interface TrendEntry {
  category: string
  label: string
  occurrences: number
}

export function RadarPage() {
  const [trends, setTrends] = useState<TrendEntry[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    apiFetch('/api/trends')
      .then((data: TrendEntry[]) => setTrends(data))
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load trends'))
  }, [])

  const maxCount = trends && trends.length > 0 ? Math.max(...trends.map((t) => t.occurrences)) : 1

  return (
    <div className="mx-auto max-w-2xl flex flex-col gap-6">
      <div>
        <div className="flex items-center gap-2 mb-2">
          <span className="h-2 w-2 bg-accent" aria-hidden="true" />
          <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">Community scam radar</span>
        </div>
        <p className="text-sm text-ink/70 leading-relaxed">
          Real, anonymized data — what scam categories every Raksha AI user has reported in the last 7
          days. No message content or identity is ever part of this, just category counts.
        </p>
      </div>

      {error && <p className="border border-red-600 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      {!trends && !error && <p className="text-sm text-ink/60">Loading trends…</p>}

      {trends && trends.length === 0 && (
        <div className="relative border border-ink bg-paper/60 backdrop-blur-sm p-6 sm:p-8 text-center">
          <CornerBrackets />
          <p className="text-sm text-ink/60">
            No trends yet — this fills in as more people scan messages. Be the first.
          </p>
        </div>
      )}

      {trends && trends.length > 0 && (
        <div className="relative border border-ink bg-paper/60 backdrop-blur-sm p-6 sm:p-8">
          <CornerBrackets />
          <div className="flex flex-col gap-4">
            {trends.map((t, i) => (
              <div key={t.category}>
                <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.1em] text-ink mb-1">
                  <span>
                    #{i + 1} {t.label}
                  </span>
                  <span className="text-ink/50">
                    {t.occurrences} report{t.occurrences === 1 ? '' : 's'}
                  </span>
                </div>
                <div className="h-2.5 w-full border border-ink bg-white">
                  <div
                    className="h-full bg-accent transition-all"
                    style={{ width: `${(t.occurrences / maxCount) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
