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
}

export function fetchDraftQueue(): Promise<DraftQueue> {
  return apiFetch('/api/review/drafts')
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
] as const

export type Decision =
  | { draftId: string; action: 'accepted' }
  | { draftId: string; action: 'rejected'; reason: string }
  | { draftId: string; action: 'skipped' }
