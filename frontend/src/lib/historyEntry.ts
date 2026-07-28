import type { Verdict } from './scanResult'

export interface HistoryEntry {
  id: string
  user_id: string
  input_type: 'text' | 'audio'
  input_text: string
  language: string
  risk_score: number
  verdict: Verdict
  flagged_phrases: string[]
  explanation: string
  recommended_action: string
  created_at: string
}
