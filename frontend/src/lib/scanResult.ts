export type Verdict = 'safe' | 'suspicious' | 'high_risk'

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
