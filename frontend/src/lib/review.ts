import { apiFetch } from './api'

export interface PatternDraft {
  id: string
  language: string
  pattern_text: string
  category: string
  source: string
  drafted_by: 'machine' | 'human'
  created_at: string
  status: 'pending' | 'accepted' | 'rejected'
  decision: { by: string; at: string; reason: string } | null
  note: string | null
}

export interface Neighbour {
  pattern_text: string
  category: string
  similarity: number
  near_duplicate: boolean
}

/** A draft plus what the reviewer needs to decide on it.
 *
 * `neighbours: null` means retrieval could not be reached, which is a
 * different claim from `[]` — "nothing similar exists". A reviewer must not
 * read the second as the first, so the UI renders them differently. */
export interface DraftContext extends PatternDraft {
  neighbours: Neighbour[] | null
  rule_response: string[]
}

export interface DraftQueue {
  drafts: PatternDraft[]
  counts: { pending: number; accepted: number; rejected: number; total: number }
  decisions_persisted: boolean
  /** Whether the decision store could be read for *this* request. A different
   * question from `decisions_persisted`, which is about the capability: a full
   * queue with `decisions_available: false` means "cannot see what was
   * decided", not "nothing has been". Working the second as the first means
   * re-deciding drafts already done. */
  decisions_available: boolean
  /** The server's vocabulary, so the list below cannot drift from the check
   * constraint that enforces it. */
  rejection_reasons: string[]
}

export function fetchDraftQueue(): Promise<DraftQueue> {
  return apiFetch('/api/review/drafts')
}

export interface DecisionRecord {
  draft_id: string
  decision: 'accepted' | 'rejected' | 'revoked'
  reason: string | null
  note: string | null
  pattern_id: string | null
  created_at: string
}

/** Record one decision. Rejects on failure rather than resolving, deliberately:
 * a reviewer who believes they approved a pattern into the detection set and
 * did not is the failure this endpoint exists to remove, so the caller must
 * handle it rather than being able to ignore it. */
export function decideDraft(
  id: string,
  decision: 'accepted' | 'rejected' | 'revoked',
  options: { reason?: string; note?: string } = {},
): Promise<{ decision: DecisionRecord }> {
  return apiFetch(`/api/review/drafts/${encodeURIComponent(id)}/decision`, {
    method: 'POST',
    body: JSON.stringify({
      decision,
      reason: options.reason ?? null,
      note: options.note ?? null,
    }),
  })
}

/** Fetched per card, not for the whole queue — each call costs one embedding,
 * and a reviewer may never reach the fiftieth card. */
export function fetchDraftContext(id: string): Promise<DraftContext> {
  return apiFetch(`/api/review/drafts/${encodeURIComponent(id)}/context`)
}

/** Rejection reasons, each on a number key.
 *
 * A free-text box would be skipped under volume — a reviewer processing
 * hundreds types nothing — and then rejections teach whoever tunes A1
 * nothing. One keystroke is the most that survives that pressure. */
export const REJECTION_REASONS = [
  { key: '1', code: 'duplicate', label: 'Duplicate of an existing pattern' },
  { key: '2', code: 'not_a_scam', label: 'Not actually a scam' },
  { key: '3', code: 'too_broad', label: 'Too broad — would over-warn' },
  { key: '4', code: 'wrong_language', label: 'Wrong language or script' },
  { key: '5', code: 'low_quality', label: 'Garbled or low quality' },
  { key: '6', code: 'low_value', label: 'Real, but too rare to be worth a slot' },
] as const

/** Codes 1–5 shipped before the store existed and are deliberately unchanged —
 * the backend adopted them rather than the reverse, because a reviewer who has
 * learned that 3 is "too broad" would be silently retrained by a reordering.
 *
 * This checks the two lists still agree at runtime. A mismatch means the server
 * would reject a decision the UI happily offered, which the reviewer would
 * experience as a button that does nothing — the failure #64 was about, in a
 * new place. */
export function unknownReasonCodes(serverReasons: string[]): string[] {
  const known = new Set(serverReasons)
  return REJECTION_REASONS.filter((r) => !known.has(r.code)).map((r) => r.code)
}

export type Decision =
  | { draftId: string; action: 'accepted' }
  | { draftId: string; action: 'rejected'; reason: string }
  | { draftId: string; action: 'skipped' }
