import { useCallback, useEffect, useState } from 'react'
import { CornerBrackets } from '../components/CornerBrackets'
import { Shortcuts } from '../components/triage'
import { useKeyboardTriage } from '../lib/useKeyboardTriage'
import { LANGUAGES } from '../lib/languages'
import {
  REJECTION_REASONS,
  decideDraft,
  fetchDraftContext,
  fetchDraftQueue,
  unknownReasonCodes,
  type Decision,
  type DraftContext,
  type PatternDraft,
} from '../lib/review'

/** A1 pattern draft review queue (#32 A).
 *
 * Keyboard-first because a reviewer processes hundreds in a sitting, and this
 * queue is part of the security design rather than admin UI: the pattern
 * database is what detection reasons against, so a wrong pattern degrades
 * every verdict silently. If triage is slow the queue backs up and the
 * pressure to auto-approve becomes real. Throughput is the security property.
 *
 * Copy is English-only — internal tooling, per #32. Pattern text is not: a
 * draft can be in any of the twelve scripts, so anything rendering it carries
 * `dir="auto"` or the Urdu drafts arrive right-to-left inside a left-to-right
 * card and read as corruption.
 */
/** Local rather than shared on purpose. #58 adds the same helper to
 * `lib/languages.ts`, and importing it from there would couple this branch to
 * that one — the stacked-PR problem #55 calls out. Collapse the two into the
 * shared helper once both have landed. */
function languageLabel(code: string): string {
  return LANGUAGES.find((l) => l.code === code)?.label ?? code
}

export function ReviewQueuePage() {
  const [drafts, setDrafts] = useState<PatternDraft[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [available, setAvailable] = useState(true)
  const [unknownReasons, setUnknownReasons] = useState<string[]>([])

  useEffect(() => {
    fetchDraftQueue()
      .then((q) => {
        setDrafts(q.drafts)
        setAvailable(q.decisions_available)
        // If the server would refuse a code this UI offers, the reviewer sees a
        // key that does nothing. Checked rather than assumed, because the two
        // lists live in different languages in different files (#64).
        setUnknownReasons(unknownReasonCodes(q.rejection_reasons ?? []))
      })
      .catch((e: Error) => setError(e.message))
  }, [])

  if (error) {
    return (
      <p className="mx-auto max-w-3xl border border-red-600 bg-red-50 p-4 text-sm text-ink">
        Could not load the queue: {error}
      </p>
    )
  }
  if (!drafts) return <p className="mx-auto max-w-3xl text-sm text-ink/60">Loading queue…</p>

  return (
    <ReviewQueue
      drafts={drafts}
      decisionsAvailable={available}
      unknownReasons={unknownReasons}
    />
  )
}

/** Split from the fetch so it can be driven against captured payloads without
 * standing up auth. */
export function ReviewQueue({
  drafts,
  decisionsAvailable = true,
  unknownReasons = [],
  // Injectable for the same reason BenchmarkReportView is split from its
  // fetch: the card's neighbour panel is the part most worth eyeballing, and
  // it cannot be reached in a harness that has no session.
  loadContext = fetchDraftContext,
  persist = decideDraft,
}: {
  drafts: PatternDraft[]
  decisionsAvailable?: boolean
  unknownReasons?: string[]
  loadContext?: (id: string) => Promise<DraftContext>
  persist?: typeof decideDraft
}) {
  const [index, setIndex] = useState(0)
  const [decisions, setDecisions] = useState<Decision[]>([])
  const [choosingReason, setChoosingReason] = useState(false)
  const [announcement, setAnnouncement] = useState('')
  const [context, setContext] = useState<DraftContext | null>(null)
  const [contextFor, setContextFor] = useState<string | null>(null)
  /** Decisions the reviewer made that did NOT reach the store.
   *
   * The card advances optimistically, because a reviewer working hundreds
   * cannot wait for a round trip per keystroke and #32 makes throughput a
   * security property. Optimism is only honest if the failures are loud, so
   * these are rendered as a standing banner rather than a toast that scrolls
   * away — an accept the reviewer believes landed and did not is the exact
   * failure this screen was built read-only to avoid. */
  const [failures, setFailures] = useState<{ id: string; action: string; detail: string }[]>([])

  const current = drafts[index] ?? null
  const done = index >= drafts.length

  // Per card, never for the queue — each is one embedding call, and a reviewer
  // may never reach the last card.
  useEffect(() => {
    if (!current) return
    let cancelled = false
    setContext(null)
    setContextFor(current.id)
    loadContext(current.id)
      .then((c) => {
        if (!cancelled) setContext(c)
      })
      .catch(() => {
        // The near-duplicate hint is an aid, not a gate. A reviewer who cannot
        // reach retrieval should still be able to work the queue.
        if (!cancelled) setContext(null)
      })
    return () => {
      cancelled = true
    }
  }, [current, loadContext])

  const record = useCallback(
    (decision: Decision, label: string) => {
      setDecisions((d) => [...d, decision])
      setIndex((i) => i + 1)
      setChoosingReason(false)
      setAnnouncement(`${label}. ${drafts.length - index - 1} remaining.`)

      // A skip is not a decision. Nothing is written, because "I did not look
      // at this yet" is the absence of a judgement rather than one, and
      // recording it would put a row in an append-only table that says nothing.
      if (decision.action === 'skipped') return

      persist(decision.draftId, decision.action, {
        reason: decision.action === 'rejected' ? decision.reason : undefined,
      }).catch((e: Error) => {
        setFailures((f) => [...f, { id: decision.draftId, action: decision.action, detail: e.message }])
        setAnnouncement(`${label} was NOT saved. ${e.message}`)
      })
    },
    [drafts.length, index, persist],
  )

  // Every updater below is pure. An earlier version nested `setIndex` inside
  // the `setDecisions` updater, and React invokes updaters twice under
  // StrictMode — so one undo rewound two cards, silently discarding a decision
  // the reviewer had already made. State updaters must not have side effects.
  const undo = useCallback(() => {
    const last = decisions[decisions.length - 1]
    if (!last) {
      setAnnouncement('Nothing to undo.')
      return
    }
    setDecisions((d) => d.slice(0, -1))
    setIndex((i) => Math.max(0, i - 1))
    setChoosingReason(false)

    // Undoing an accept is not a local rewind. The pattern is already in
    // scam_patterns and already influencing retrieval, so taking it back means
    // retiring it — a `revoked` decision, appended. Anything less would leave a
    // live pattern behind a reviewer who believes they undid it.
    if (last.action === 'accepted') {
      setAnnouncement('Undoing — retiring the accepted pattern…')
      persist(last.draftId, 'revoked', { note: 'Undone by the reviewer during triage' })
        .then(() => setAnnouncement('Undone. The pattern was retired.'))
        .catch((e: Error) => {
          setFailures((f) => [...f, { id: last.draftId, action: 'revoked', detail: e.message }])
          setAnnouncement(`Could not retire the pattern. It is STILL live. ${e.message}`)
        })
      return
    }

    // A rejection stands as a record — the store is append-only and there is no
    // un-writing it. Nothing harmful is live, and deciding the card again
    // supersedes it, so the honest thing is to say that rather than imply the
    // row was removed.
    setAnnouncement(
      last.action === 'rejected'
        ? 'Back to the card. The rejection stays recorded until you decide it again.'
        : 'Undid the skip.',
    )
  }, [decisions, persist])

  useKeyboardTriage({
    enabled: !done,
    reasons: REJECTION_REASONS,
    choosingReason,
    onAccept: () => current && record({ draftId: current.id, action: 'accepted' }, 'Accepted'),
    onRejectStart: () => setChoosingReason(true),
    onRejectCancel: () => setChoosingReason(false),
    onReason: (code, label) =>
      current && record({ draftId: current.id, action: 'rejected', reason: code }, `Rejected — ${label}`),
    onSkip: () => current && record({ draftId: current.id, action: 'skipped' }, 'Skipped'),
    onUndo: undo,
  })

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-center gap-2 mb-4">
        <span className="h-2 w-2 bg-accent" aria-hidden="true" />
        <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">
          Review · pattern drafts
        </span>
      </div>

      {!decisionsAvailable && (
        <p className="border-l-4 border-amber-600 bg-amber-50 px-4 py-3 mb-4 text-[11px] text-ink leading-relaxed">
          <strong>Cannot read what has already been decided.</strong> The decision store did not
          answer, so every draft below is shown as the file has it. Some may already be accepted or
          rejected. New decisions will still be written — this is about reading, not writing — but
          you may be looking at work that is already done.
        </p>
      )}

      {unknownReasons.length > 0 && (
        <p className="border-l-4 border-amber-600 bg-amber-50 px-4 py-3 mb-4 text-[11px] text-ink leading-relaxed">
          <strong>This screen offers a reason the server does not accept:</strong>{' '}
          {unknownReasons.join(', ')}. Rejecting with it will fail. The two lists have drifted and
          one of them needs updating.
        </p>
      )}

      {failures.length > 0 && (
        <div
          role="alert"
          className="border-l-4 border-red-600 bg-red-50 px-4 py-3 mb-4 text-[11px] text-ink leading-relaxed"
        >
          <strong>
            {failures.length} decision{failures.length === 1 ? '' : 's'} did not save.
          </strong>{' '}
          The card advanced but the store did not accept it, so this work is not recorded. Decide
          these again once the store is reachable.
          <ul className="mt-2 space-y-1">
            {failures.map((f, i) => (
              <li key={`${f.id}-${i}`} className="font-mono">
                {f.id} — {f.action}: {f.detail}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Screen readers get the outcome of a keystroke; sighted users get the
          card advancing. Without this, keyboard triage is silent. */}
      <p aria-live="polite" className="sr-only">
        {announcement}
      </p>

      <Shortcuts choosingReason={choosingReason} />

      {done ? (
        <Summary decisions={decisions} total={drafts.length} onUndo={undo} />
      ) : (
        current && (
          <DraftCard
            draft={current}
            context={contextFor === current.id ? context : null}
            position={index + 1}
            total={drafts.length}
            choosingReason={choosingReason}
          />
        )
      )}
    </div>
  )
}




function DraftCard({
  draft,
  context,
  position,
  total,
  choosingReason,
}: {
  draft: PatternDraft
  context: DraftContext | null
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
          {/* Provenance (#32 C): once some patterns are machine-drafted and
              some hand-written, a reviewer must be able to tell which. */}
          <span
            className={`px-1.5 py-0.5 font-bold ${
              draft.drafted_by === 'machine'
                ? 'bg-ink text-white'
                : 'border border-ink text-ink'
            }`}
          >
            {draft.drafted_by === 'machine' ? 'machine-drafted' : 'hand-written'}
          </span>
          <span className="text-ink/50 font-mono normal-case tracking-normal">{draft.source}</span>
        </div>
      </div>

      <p
        dir="auto"
        className="text-base text-ink leading-relaxed break-words border border-line bg-white p-3 mb-4"
      >
        {draft.pattern_text}
      </p>

      <dl className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-[11px] mb-4">
        <Field label="Language" value={`${languageLabel(draft.language)} (${draft.language})`} />
        <Field label="Category" value={draft.category} />
        <Field label="Draft id" value={draft.id} mono />
      </dl>

      {draft.note && (
        <p className="text-[11px] text-ink/50 leading-relaxed mb-4">{draft.note}</p>
      )}

      <RuleResponse context={context} />
      <Neighbours context={context} />
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

/** What the offline engine already does with this text.
 *
 * Not "benchmark impact" — that would need the LLM benchmark re-run per draft,
 * which is a cost amplifier per keystroke. This is free and deterministic, and
 * labelled as what it is rather than dressed up as something stronger. */
function RuleResponse({ context }: { context: DraftContext | null }) {
  if (!context) return null
  const fired = context.rule_response

  return (
    <div className="mb-4">
      <h3 className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70 mb-1">
        Offline rules already fire
      </h3>
      {fired.length > 0 ? (
        <p className="text-xs text-ink">
          {fired.join(', ')} — the rule layer already catches this shape.
        </p>
      ) : (
        <p className="text-xs text-ink">
          Nothing. If this is a real scam, the rule layer misses it today.
        </p>
      )}
    </div>
  )
}

function Neighbours({ context }: { context: DraftContext | null }) {
  if (!context) {
    return (
      <p className="text-[11px] text-ink/40">Checking for near-duplicates…</p>
    )
  }

  if (context.neighbours === null) {
    return (
      <p className="text-[11px] text-amber-800 bg-amber-50 border-l-2 border-amber-600 px-2 py-1">
        Could not check for near-duplicates — retrieval is unavailable. This is not the same as
        finding none.
      </p>
    )
  }

  if (context.neighbours.length === 0) {
    return <p className="text-[11px] text-ink/60">No similar pattern exists yet.</p>
  }

  return (
    <div>
      <h3 className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70 mb-1">
        Nearest existing patterns
      </h3>
      <ul className="space-y-1.5">
        {context.neighbours.map((n, i) => (
          <li
            key={i}
            className={`border p-2 bg-white ${
              n.near_duplicate ? 'border-red-600' : 'border-line'
            }`}
          >
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-accent">
                {n.category}
              </span>
              <span className="text-[11px] text-ink/60">
                {Math.round(n.similarity * 100)}% similar
                {n.near_duplicate && (
                  <strong className="ml-1.5 text-red-700">near-duplicate</strong>
                )}
              </span>
            </div>
            <p dir="auto" className="mt-1 text-xs text-ink leading-relaxed break-words">
              {n.pattern_text}
            </p>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Summary({
  decisions,
  total,
  onUndo,
}: {
  decisions: Decision[]
  total: number
  onUndo: () => void
}) {
  const accepted = decisions.filter((d) => d.action === 'accepted').length
  const rejected = decisions.filter((d) => d.action === 'rejected')
  const skipped = decisions.filter((d) => d.action === 'skipped').length

  const byReason = new Map<string, number>()
  for (const d of rejected) {
    if (d.action === 'rejected') byReason.set(d.reason, (byReason.get(d.reason) ?? 0) + 1)
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
                {REJECTION_REASONS.find((r) => r.code === code)?.label ?? code} — {count}
              </li>
            ))}
          </ul>
        </div>
      )}

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
