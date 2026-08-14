export type Verdict = 'safe' | 'suspicious' | 'high_risk'

/** `labelKey` points into the `verdict` i18n namespace — call t(meta.labelKey)
 * at the render site rather than storing the translated string here, since
 * this module has no access to the active language. */
export const VERDICT_META: Record<Verdict, { labelKey: string; badgeClass: string; barClass: string }> = {
  safe: { labelKey: 'verdict.safe', badgeClass: 'bg-emerald-600 text-white', barClass: 'bg-emerald-600' },
  suspicious: { labelKey: 'verdict.suspicious', badgeClass: 'bg-amber-500 text-white', barClass: 'bg-amber-500' },
  high_risk: { labelKey: 'verdict.highRisk', badgeClass: 'bg-red-600 text-white', barClass: 'bg-red-600' },
}

/** One known scam pattern pulled back by the RAG retrieval step, with how
 * closely it matched. `similarity` is cosine, 0–1. */
export interface RetrievedPattern {
  pattern_text: string
  category: string
  similarity: number
}

/** One offline rule that fired before any network call. `rule_id` is looked up
 * in the `trace.rules.*` i18n namespace for a human-readable name; when the id
 * is unknown the raw `pattern` is shown instead, so a newly added backend rule
 * degrades to something legible rather than blank. */
export interface OfflineRuleHit {
  rule_id: string
  pattern: string
  matched_text: string
}

/** Which model and prompt produced the verdict. Without this a decision made
 * six months ago cannot be reproduced — see ARCHITECTURE.md §03. */
export interface ModelStamp {
  provider: string
  model: string
  prompt_version: string
}

/** Position of this verdict in the append-only, hash-chained audit log. */
export interface AuditRecord {
  record_id: string
  hash: string
  prev_hash: string | null
}

/** The reasoning trace behind a verdict.
 *
 * Every field is optional on purpose. The backend lands these incrementally
 * (ARCHITECTURE.md §03 / roadmap P0) — today the scan pipeline computes the
 * retrieved patterns and then discards them, and never captures a model
 * version at all. The viewer renders whatever is present so the UI can ship
 * ahead of the persistence work instead of waiting on it.
 *
 * Field names here are the frontend's half of a contract that does not exist
 * yet; they need Pavan's sign-off before the backend implements them. */
export interface ScanTrace {
  offline_rules_fired?: OfflineRuleHit[]
  retrieved_patterns?: RetrievedPattern[]
  model?: ModelStamp
  audit?: AuditRecord
}

export interface ScanResult {
  risk_score: number
  verdict: Verdict
  flagged_phrases: string[]
  explanation: string
  recommended_action: string
  community_report_count: number
  offline_flags_matched: number
  transcript: string | null
  trace?: ScanTrace | null
}
