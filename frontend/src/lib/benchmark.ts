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
  /** Benign cases a rule fired on. Mirrors the LLM half's field of the same
   * name so one component can render either. */
  false_positive_cases: FalsePositiveCase[]
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

/** A benign case something warned about. Both halves report these; the offline
 * half names the rules that fired, the LLM half names the verdict it gave. */
export interface FalsePositiveCase {
  id: string
  text: string
  note: string | null
  /** Offline half only. */
  fired_rule_ids?: string[]
  /** LLM half only. */
  verdict?: string
  risk_score?: number
}

/** A scam the LLM half failed to flag. Shaped like `MissedCase` where the
 * meaning matches, so one component renders either. */
export interface LlmMissedCase {
  id: string
  text: string
  verdict: string
  risk_score: number
  status: string | null
  note: string | null
}

export interface LlmLanguageBenchmark {
  language: string
  total_cases: number
  scam_cases: number
  benign_cases: number
  scored_cases: number
  leaked_cases: number
  true_positives: number
  false_negatives: number
  false_positives: number
  true_negatives: number
  precision: number | null
  recall: number | null
  missed_cases: LlmMissedCase[]
  false_positive_cases: FalsePositiveCase[]
  leaked_case_ids: string[]
}

/** `available: false` when no run has been committed. An absent benchmark is a
 * state to render, not an error — the offline half still has numbers. */
export type LlmBenchmarkReport =
  | { available: false }
  | {
      available: true
      languages: LlmLanguageBenchmark[]
      run: { api_calls: number; cache_hits: number; models: string[]; prompt_version: string }
      leakage: { leaked_cases: number; threshold: number; held_out: boolean }
      provenance: { prompt_version: string; models: string[]; measures: string }
    }

export function fetchOfflineRuleBenchmark(): Promise<BenchmarkReport> {
  return apiFetch('/api/benchmark/offline-rules')
}

/** Reads the last committed run. Never triggers one — scoring spends API quota
 * per case, so it is a CLI, and this only reads what it wrote. */
export function fetchLlmBenchmark(): Promise<LlmBenchmarkReport> {
  return apiFetch('/api/benchmark/llm')
}

/** Under this, a percentage is arithmetic rather than evidence, and must be
 * rendered as words. `recall: 1.000` over two cases is technically true and
 * reads as parity — which is exactly the misreading a dimmed number invites
 * and a phrase prevents. */
export function hasEnoughCases(totalCases: number): boolean {
  return totalCases > LOW_CONFIDENCE_CASE_COUNT
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
