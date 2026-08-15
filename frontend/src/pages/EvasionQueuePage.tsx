import { useCallback, useState } from 'react'
import { useEffect } from 'react'
import { CornerBrackets } from '../components/CornerBrackets'
import { Key, Shortcuts } from '../components/triage'
import { useKeyboardTriage } from '../lib/useKeyboardTriage'
import { LANGUAGES } from '../lib/languages'
import {
  EVASION_REJECTION_REASONS,
  fetchEvasionQueue,
  type Evasion,
  type EvasionQueue as Queue,
} from '../lib/evasions'

/** A6 evasion review queue (#41 §3).
 *
 * The red-team loop produces variants that got past the detector. The
 * reviewer's question is "is this still the same fraud?", which cannot be
 * answered from the variant alone — so seed and variant sit side by side with
 * the mutation highlighted.
 *
 * **Everything here renders attacker-authored text.** The variants are written
 * by an adversarial loop to defeat our detection, and one containing "ignore
 * previous instructions" is a realistic thing to find. So it is rendered as
 * React children — escaped by construction — never through
 * `dangerouslySetInnerHTML`, and this screen calls no model with any of it. The
 * diff arrives as tokens rather than markup precisely so there is nothing here
 * that could interpret it.
 */
function languageLabel(code: string): string {
  return LANGUAGES.find((l) => l.code === code)?.label ?? code
}

export function EvasionQueuePage() {
  const [queue, setQueue] = useState<Queue | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchEvasionQueue()
      .then(setQueue)
      .catch((e: Error) => setError(e.message))
  }, [])

  if (error) {
    return (
      <p className="mx-auto max-w-4xl border border-red-600 bg-red-50 p-4 text-sm text-ink">
        Could not load the evasion queue: {error}
      </p>
    )
  }
  if (!queue) return <p className="mx-auto max-w-4xl text-sm text-ink/60">Loading queue…</p>

  return <EvasionReview queue={queue} />
}

/** Split from the fetch so it can be driven against captured payloads without
 * standing up auth. */
export function EvasionReview({ queue }: { queue: Queue }) {
  const { evasions, counts, by_strategy: byStrategy, decisions_persisted: persisted } = queue

  const [index, setIndex] = useState(0)
  const [decisions, setDecisions] = useState<
    { id: string; action: 'accepted' | 'rejected' | 'skipped'; reason?: string }[]
  >([])
  const [choosingReason, setChoosingReason] = useState(false)
  const [announcement, setAnnouncement] = useState('')

  const current = evasions[index] ?? null
  const done = index >= evasions.length

  const record = useCallback(
    (action: 'accepted' | 'rejected' | 'skipped', label: string, reason?: string) => {
      if (!current) return
      setDecisions((d) => [...d, { id: current.id, action, reason }])
      setIndex((i) => i + 1)
      setChoosingReason(false)
      setAnnouncement(`${label}. ${evasions.length - index - 1} remaining.`)
    },
    [current, evasions.length, index],
  )

  // Pure updaters only. Nesting setIndex inside a setDecisions updater made one
  // undo rewind two cards in #60, because React invokes updaters twice under
  // StrictMode — the same shape of bug would be just as invisible here.
  const undo = useCallback(() => {
    if (decisions.length === 0) {
      setAnnouncement('Nothing to undo.')
      return
    }
    setDecisions((d) => d.slice(0, -1))
    setIndex((i) => Math.max(0, i - 1))
    setChoosingReason(false)
    setAnnouncement('Undid the last decision.')
  }, [decisions.length])

  useKeyboardTriage({
    enabled: !done && evasions.length > 0,
    reasons: EVASION_REJECTION_REASONS,
    choosingReason,
    onAccept: () => record('accepted', 'Accepted — will be pinned as a corpus gap'),
    onRejectStart: () => setChoosingReason(true),
    onRejectCancel: () => setChoosingReason(false),
    onReason: (code, label) => record('rejected', `Rejected — ${label}`, code),
    onSkip: () => record('skipped', 'Skipped'),
    onUndo: undo,
  })

  return (
    <div className="mx-auto max-w-4xl">
      <div className="flex items-center gap-2 mb-4">
        <span className="h-2 w-2 bg-accent" aria-hidden="true" />
        <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">
          Review · red-team evasions
        </span>
      </div>

      <QueueHealth counts={counts} byStrategy={byStrategy} />

      {!persisted && evasions.length > 0 && (
        <p className="border-l-4 border-amber-600 bg-amber-50 px-4 py-3 mb-4 text-[11px] text-ink leading-relaxed">
          <strong>Decisions are not saved yet.</strong> Accepting does not yet write a{' '}
          <code className="font-mono">known_gap</code> row to the corpus. Triage and the tally are
          real; nothing leaves this screen.
        </p>
      )}

      <p aria-live="polite" className="sr-only">
        {announcement}
      </p>

      {evasions.length === 0 ? (
        <EmptyQueue counts={counts} />
      ) : done ? (
        <Summary decisions={decisions} total={evasions.length} onUndo={undo} />
      ) : (
        <>
          <Shortcuts choosingReason={choosingReason} reasons={EVASION_REJECTION_REASONS} />
          {current && (
            <EvasionCard
              evasion={current}
              position={index + 1}
              total={evasions.length}
              choosingReason={choosingReason}
            />
          )}
        </>
      )}
    </div>
  )
}

/** An empty queue is the goal state, not a failure — say so, and show the
 * closed work so the screen is not mistaken for broken. */
function EmptyQueue({ counts }: { counts: Queue['counts'] }) {
  return (
    <div className="relative border border-ink bg-paper/60 p-6">
      <CornerBrackets />
      <h2 className="text-sm font-bold uppercase tracking-[0.15em] text-ink mb-2">
        No unresolved evasions
      </h2>
      <p className="text-sm text-ink leading-relaxed">
        Every variant the red-team loop has found is closed: {counts.fixed} fixed
        {counts.wontfix > 0 && `, ${counts.wontfix} judged not worth chasing`}. That is the state
        this queue is supposed to be in — it only grows when the loop finds something the detector
        misses.
      </p>
      <p className="mt-2 text-[11px] text-ink/50 leading-relaxed">
        Run the loop to look for more:{' '}
        <code className="font-mono">
          python scripts/run_redteam.py --run --detector rules
        </code>
      </p>
    </div>
  )
}

/** Which strategies are producing work.
 *
 * A strategy generating nothing but noise is itself a finding — and it is only
 * visible in aggregate, never from inside a single card. */
function QueueHealth({
  counts,
  byStrategy,
}: {
  counts: Queue['counts']
  byStrategy: Record<string, number>
}) {
  const strategies = Object.entries(byStrategy)

  return (
    <div className="border border-line bg-white p-3 mb-4 text-[11px] text-ink/60">
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        <span>
          <strong className="text-ink">{counts.open}</strong> open
        </span>
        <span>{counts.fixed} fixed</span>
        {counts.wontfix > 0 && <span>{counts.wontfix} wontfix</span>}
      </div>
      {strategies.length > 0 && (
        <p className="mt-1.5">
          By strategy:{' '}
          {strategies.map(([name, n], i) => (
            <span key={name}>
              {i > 0 && ' · '}
              <span className="font-mono text-ink">{name}</span> {n}
            </span>
          ))}
        </p>
      )}
    </div>
  )
}

function EvasionCard({
  evasion,
  position,
  total,
  choosingReason,
}: {
  evasion: Evasion
  position: number
  total: number
  choosingReason: boolean
}) {
  return (
    <div
      className={`relative border bg-paper/60 backdrop-blur-sm p-5 sm:p-6 ${
        choosingReason ? 'border-amber-600' : 'border-ink'
      }`}
    >
      <CornerBrackets />

      <div className="flex items-center justify-between gap-3 flex-wrap mb-4 text-[10px] uppercase tracking-[0.15em]">
        <span className="text-ink/60">
          {position} of {total}
        </span>
        <div className="flex items-center gap-2">
          <span className="bg-ink text-white px-1.5 py-0.5 font-bold">{evasion.strategy}</span>
          <span className="text-ink/50 font-mono normal-case tracking-normal">
            vs {evasion.detector}
          </span>
        </div>
      </div>

      {/* Side by side, because "is this still the same fraud?" is unanswerable
          from the variant alone. Stacks on mobile rather than shrinking to two
          unreadable columns. */}
      <div className="grid md:grid-cols-2 gap-3 mb-4">
        <Panel title="Original scam" subtitle={evasion.seed?.id ?? 'seed missing'}>
          {evasion.seed ? (
            <p dir="auto" className="text-sm text-ink leading-relaxed break-words">
              {evasion.seed.text}
            </p>
          ) : (
            <p className="text-[11px] text-amber-800">
              The seed case is no longer in the corpus, so there is nothing to compare against.
              Judge the variant on its own or skip it.
            </p>
          )}
        </Panel>

        <Panel title="Variant that evaded" subtitle={`${evasion.verdict} (${evasion.risk_score})`} highlight>
          <VariantText evasion={evasion} />
        </Panel>
      </div>

      <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[11px] mb-4">
        <Field label="Language" value={`${languageLabel(evasion.language)} (${evasion.language})`} />
        <Field label="Rules fired" value={evasion.rules_fired.join(', ') || 'none'} />
        <Field label="Expected" value={evasion.seed?.expected_rule_ids.join(', ') || '—'} />
        <Field label="Evasion id" value={evasion.id} mono />
      </dl>

      {evasion.judge_reason && (
        <div>
          <h3 className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70 mb-1">
            Why the judge called it the same fraud
          </h3>
          {/* Model-authored, about attacker text. Same handling: rendered, never
              interpreted. */}
          <p className="text-xs text-ink leading-relaxed break-words">{evasion.judge_reason}</p>
        </div>
      )}
    </div>
  )
}

/** The variant, with words the seed did not contain marked.
 *
 * Rendered token by token from structured data. There is deliberately no path
 * here that turns this text into markup — it is the most hostile string on the
 * screen, and the diff is the one place it would be tempting to build HTML. */
function VariantText({ evasion }: { evasion: Evasion }) {
  if (!evasion.diff) {
    return (
      <p dir="auto" className="text-sm text-ink leading-relaxed break-words">
        {evasion.text}
      </p>
    )
  }

  return (
    <p dir="auto" className="text-sm text-ink leading-relaxed break-words">
      {evasion.diff.map((token, i) => (
        <span key={i}>
          {token.kind === 'added' ? (
            <mark className="bg-accent/25 text-ink px-0.5 underline decoration-accent decoration-2">
              {token.text}
            </mark>
          ) : (
            token.text
          )}{' '}
        </span>
      ))}
    </p>
  )
}

function Panel({
  title,
  subtitle,
  highlight,
  children,
}: {
  title: string
  subtitle: string
  highlight?: boolean
  children: React.ReactNode
}) {
  return (
    <div className={`border p-3 bg-white ${highlight ? 'border-accent' : 'border-line'}`}>
      <div className="flex items-baseline justify-between gap-2 flex-wrap mb-1.5">
        <h3 className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70">{title}</h3>
        <span className="text-[10px] text-ink/40 font-mono break-all">{subtitle}</span>
      </div>
      {children}
    </div>
  )
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="font-bold uppercase tracking-[0.1em] text-ink/50">{label}</dt>
      <dd className={`mt-0.5 text-ink break-words ${mono ? 'font-mono text-[10px]' : ''}`}>
        {value}
      </dd>
    </div>
  )
}

function Summary({
  decisions,
  total,
  onUndo,
}: {
  decisions: { action: string; reason?: string }[]
  total: number
  onUndo: () => void
}) {
  const accepted = decisions.filter((d) => d.action === 'accepted').length
  const rejected = decisions.filter((d) => d.action === 'rejected')
  const skipped = decisions.filter((d) => d.action === 'skipped').length

  const byReason = new Map<string, number>()
  for (const d of rejected) {
    if (d.reason) byReason.set(d.reason, (byReason.get(d.reason) ?? 0) + 1)
  }

  return (
    <div className="relative border border-ink bg-paper/60 p-6">
      <CornerBrackets />
      <h2 className="text-sm font-bold uppercase tracking-[0.15em] text-ink mb-3">
        Queue complete — {total} triaged
      </h2>
      <dl className="grid grid-cols-3 gap-4 text-xs mb-4">
        <Field label="Accepted" value={String(accepted)} />
        <Field label="Rejected" value={String(rejected.length)} />
        <Field label="Skipped" value={String(skipped)} />
      </dl>

      {byReason.size > 0 && (
        <div className="mb-4">
          <h3 className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70 mb-1">
            Why they were rejected
          </h3>
          <ul className="text-xs text-ink space-y-0.5">
            {[...byReason.entries()].map(([code, count]) => (
              <li key={code}>
                {EVASION_REJECTION_REASONS.find((r) => r.code === code)?.label ?? code} — {count}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="text-[11px] text-ink/50 mb-3">
        Accepted variants become <code className="font-mono">known_gap</code> corpus rows once the
        write path exists. Press <Key>U</Key> to revisit the last one.
      </p>

      <button
        type="button"
        onClick={onUndo}
        className="border border-ink px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.15em] text-ink hover:bg-ink hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent transition-colors"
      >
        Undo last
      </button>
    </div>
  )
}
