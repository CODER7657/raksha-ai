import { apiFetch } from './api'

/** One token of the variant, and whether the seed already contained it.
 *
 * Structured data, deliberately not markup. This text is written by an
 * adversarial loop to defeat our detector, so it is rendered as React children
 * — escaped by default — and never via `dangerouslySetInnerHTML`. */
export interface DiffToken {
  text: string
  kind: 'same' | 'added'
}

export interface EvasionSeed {
  id: string
  text: string
  language: string
  expected_rule_ids: string[]
}

export interface Evasion {
  id: string
  seed_id: string
  strategy: string
  language: string
  /** Attacker-authored. Treat as hostile data everywhere it appears. */
  text: string
  verdict: string
  risk_score: number
  rules_fired: string[]
  judge_reason: string
  detector: string
  status: string
  first_seen: string | null
  /** `null` when the seed has since left the corpus — the variant is still
   * reviewable, just harder, and the UI says the original is missing rather
   * than rendering an empty panel. */
  seed: EvasionSeed | null
  diff: DiffToken[] | null
}

export interface EvasionQueue {
  evasions: Evasion[]
  counts: { open: number; fixed: number; wontfix: number; total: number }
  by_strategy: Record<string, number>
  decisions_persisted: boolean
}

export function fetchEvasionQueue(): Promise<EvasionQueue> {
  return apiFetch('/api/review/evasions')
}

/** Why a variant was not worth adding to the corpus.
 *
 * Different vocabulary from the pattern queue's: the question there is "is this
 * a good pattern?", here it is "is this still the same fraud, and does pinning
 * it teach the detector anything?". Reusing one list would have made both
 * vaguer. */
export const EVASION_REJECTION_REASONS = [
  { key: '1', code: 'not_the_same_fraud', label: 'Mutation changed what it asks for' },
  { key: '2', code: 'not_realistic', label: 'No real scammer would send this' },
  { key: '3', code: 'duplicate_evasion', label: 'Same gap as one already pinned' },
  { key: '4', code: 'strategy_noise', label: 'This strategy is producing noise' },
  { key: '5', code: 'already_caught', label: 'Detector catches it now' },
] as const
