import { apiFetch } from './api'

/** A scam case the offline engine failed to flag. */
export interface MissedCase {
  id: string
  text: string
  expected_rule_ids: string[]
  status: 'enforced' | 'known_gap'
  note: string | null
}

/** One language's slice of the benchmark.
 *
 * `precision` and `recall` are `null`, never 0, when undefined — a language
 * with no cases has not been measured, which is a different claim from having
 * been measured and scored zero. Render the two differently. */
export interface LanguageBenchmark {
  language: string
  has_rules: boolean
  total_cases: number
  scam_cases: number
  benign_cases: number
  enforced_cases: number
  known_gap_cases: number
  true_positives: number
  false_negatives: number
  false_positives: number
  true_negatives: number
  exact_rule_matches: number
  precision: number | null
  recall: number | null
  missed_cases: MissedCase[]
}

export interface BenchmarkReport {
  languages: LanguageBenchmark[]
  corpus: {
    total_cases: number
    languages_covered: number
    languages_supported: number
    languages_with_rules: string[]
    languages_without_rules: string[]
  }
  provenance: {
    prompt_version: string
    primary_model: string
    fallback_model: string
    measures: string
  }
}

export function fetchOfflineRuleBenchmark(): Promise<BenchmarkReport> {
  return apiFetch('/api/benchmark/offline-rules')
}

/** Below this, a percentage is arithmetic rather than evidence.
 *
 * There is no principled threshold for "enough cases" — this one is a display
 * convention, not a statistical claim. It exists so that 100% off two cases
 * cannot be read the same way as 86% off twelve, which is the specific failure
 * an aggregated dashboard invites. */
export const LOW_CONFIDENCE_CASE_COUNT = 5

export function formatMetric(value: number | null): string {
  return value === null ? '—' : `${Math.round(value * 100)}%`
}
