export type Verdict = 'safe' | 'suspicious' | 'high_risk'

/** `labelKey` points into the `verdict` i18n namespace — call t(meta.labelKey)
 * at the render site rather than storing the translated string here, since
 * this module has no access to the active language. */
export const VERDICT_META: Record<Verdict, { labelKey: string; badgeClass: string; barClass: string }> = {
  safe: { labelKey: 'verdict.safe', badgeClass: 'bg-emerald-600 text-white', barClass: 'bg-emerald-600' },
  suspicious: { labelKey: 'verdict.suspicious', badgeClass: 'bg-amber-500 text-white', barClass: 'bg-amber-500' },
  high_risk: { labelKey: 'verdict.highRisk', badgeClass: 'bg-red-600 text-white', barClass: 'bg-red-600' },
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
}
