export type Verdict = 'safe' | 'suspicious' | 'high_risk'

export const VERDICT_META: Record<Verdict, { label: string; badgeClass: string; barClass: string }> = {
  safe: { label: 'Safe', badgeClass: 'bg-emerald-600 text-white', barClass: 'bg-emerald-600' },
  suspicious: { label: 'Suspicious', badgeClass: 'bg-amber-500 text-white', barClass: 'bg-amber-500' },
  high_risk: { label: 'High Risk', badgeClass: 'bg-red-600 text-white', barClass: 'bg-red-600' },
}

export interface ScanResult {
  risk_score: number
  verdict: Verdict
  category?: string
  flagged_phrases: string[]
  explanation: string
  recommended_action: string
  community_report_count: number
  offline_flags_matched: number
  transcript: string | null
}
