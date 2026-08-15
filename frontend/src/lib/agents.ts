import { apiFetch } from './api'

export interface AgentRow {
  agent_id: string
  display_name: string
  enabled: boolean
  disabled_reason: string | null
  disabled_at: string | null
  spend_cap_calls: number | null
  calls_24h: number
  /** `null` when uncapped — not 0, and not 1. An uncapped agent has no
   * meaningful fraction, and rendering one as an empty bar reads as "plenty of
   * room left" rather than "no limit is being enforced". */
  budget_used: number | null
  over_cap: boolean
  last_outcome: 'ok' | 'failed' | 'blocked' | null
  last_run_at: string | null
  last_run_calls: number | null
}

/** `available: false` means the control plane could not be read — which is a
 * different thing from having no agents, and the console must not render them
 * the same way. */
export interface AgentOverview {
  available: boolean
  agents: AgentRow[]
}

export interface AgentRun {
  id: number
  agent_id: string
  outcome: 'ok' | 'failed' | 'blocked'
  model_calls: number
  detail: Record<string, unknown> | null
  started_at: string
  finished_at: string | null
}

export function fetchAgents(): Promise<AgentOverview> {
  return apiFetch('/api/agents')
}

export function fetchAgentRuns(agentId?: string): Promise<{ runs: AgentRun[] }> {
  const query = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : ''
  return apiFetch(`/api/agents/runs${query}`)
}

/** Stops or starts one agent. Errors propagate deliberately: an operator who
 * believes they stopped an agent and did not is the worst outcome this screen
 * can produce, so a failed switch must never look like a successful one. */
export function switchAgent(
  agentId: string,
  enabled: boolean,
  reason?: string,
): Promise<{ agent: AgentRow }> {
  return apiFetch(`/api/agents/${encodeURIComponent(agentId)}/switch`, {
    method: 'POST',
    body: JSON.stringify({ enabled, reason }),
  })
}
