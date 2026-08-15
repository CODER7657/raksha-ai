import { useCallback, useEffect, useState } from 'react'
import { CornerBrackets } from '../components/CornerBrackets'
import {
  fetchAgentRuns,
  fetchAgents,
  switchAgent,
  type AgentRow,
  type AgentRun,
} from '../lib/agents'

/** Operator console (#32 D, AGENT-LAYER.md §09).
 *
 * §09 promised per-agent budget caps, a kill switch and a run log. Nothing
 * rendered any of it, so the controls existed only in a document — and a
 * control that exists only in a document is indistinguishable, on the day you
 * need it, from one that was never built.
 *
 * Two rules this screen holds itself to:
 *
 * **It never claims to have stopped something it did not.** A failed switch
 * surfaces as an error and the row stays as it was. The alternative — an
 * optimistic toggle that flips and silently reverts — is the single worst thing
 * an operator console can do, because the operator walks away.
 *
 * **It says when it cannot see.** An empty list because no agents are
 * registered and an empty list because the database is unreachable call for
 * opposite responses, so they render differently.
 */
export function OperatorConsolePage() {
  const [agents, setAgents] = useState<AgentRow[] | null>(null)
  const [available, setAvailable] = useState(true)
  const [runs, setRuns] = useState<AgentRun[]>([])
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    fetchAgents()
      .then((data) => {
        setAgents(data.agents)
        setAvailable(data.available)
      })
      .catch((e: Error) => setError(e.message))
    fetchAgentRuns()
      .then((data) => setRuns(data.runs))
      .catch(() => setRuns([]))
  }, [])

  useEffect(load, [load])

  if (error) {
    return (
      <p className="mx-auto max-w-4xl border border-red-600 bg-red-50 p-4 text-sm text-ink">
        Could not load the operator console: {error}
      </p>
    )
  }
  if (!agents) return <p className="mx-auto max-w-4xl text-sm text-ink/60">Loading agents…</p>

  return <OperatorConsole agents={agents} runs={runs} available={available} onChanged={load} />
}

/** Split from the fetch so it can be driven against captured payloads. */
export function OperatorConsole({
  agents,
  runs,
  available,
  onChanged,
}: {
  agents: AgentRow[]
  runs: AgentRun[]
  available: boolean
  onChanged: () => void
}) {
  return (
    <div className="mx-auto max-w-4xl">
      <div className="flex items-center gap-2 mb-4">
        <span className="h-2 w-2 bg-accent" aria-hidden="true" />
        <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">
          Operator · agents
        </span>
      </div>

      {!available ? (
        <div className="border-l-4 border-red-600 bg-red-50 px-4 py-3 mb-4 text-sm text-ink">
          <strong>The control plane cannot be reached.</strong> This is not the same as having no
          agents: whether any of them are running or disabled is currently unknown, and the switches
          below would not take effect. Agents themselves fail closed — they refuse to spend when
          they cannot check their own state — so nothing is running unsupervised.
        </div>
      ) : (
        <p className="border-l-4 border-ink/30 bg-paper px-4 py-3 mb-4 text-[11px] text-ink/60 leading-relaxed">
          Stopping an agent takes effect wherever it runs, including a teammate running it by hand
          from a terminal — the CLIs check this before spending anything. It does{' '}
          <strong>not</strong> touch detection: a scan still works with every agent here disabled.
        </p>
      )}

      <div className="space-y-3 mb-8">
        {agents.length === 0 ? (
          <p className="border border-line bg-white p-4 text-sm text-ink/60">
            No agents are registered. Run migration 0006.
          </p>
        ) : (
          agents.map((agent) => (
            <AgentCard key={agent.agent_id} agent={agent} onChanged={onChanged} />
          ))
        )}
      </div>

      <RunLog runs={runs} />
    </div>
  )
}

function AgentCard({ agent, onChanged }: { agent: AgentRow; onChanged: () => void }) {
  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState<string | null>(null)
  const [askingReason, setAskingReason] = useState(false)
  const [reason, setReason] = useState('')

  const apply = async (enabled: boolean, why?: string) => {
    setBusy(true)
    setFailure(null)
    try {
      await switchAgent(agent.agent_id, enabled, why)
      setAskingReason(false)
      setReason('')
      // Re-read rather than patching local state. The server is the authority
      // on whether the switch actually moved, and an optimistic flip is exactly
      // how a console ends up lying about it.
      onChanged()
    } catch (e) {
      setFailure((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className={`relative border bg-paper/60 p-4 ${
        agent.enabled ? 'border-ink' : 'border-amber-600'
      }`}
    >
      <CornerBrackets />

      <div className="flex items-start justify-between gap-3 flex-wrap mb-3">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-[0.1em] text-ink">
            {agent.display_name}
          </h2>
          <p className="font-mono text-[10px] text-ink/40">{agent.agent_id}</p>
        </div>
        <span
          className={`px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.15em] ${
            agent.enabled ? 'bg-emerald-600 text-white' : 'bg-amber-500 text-white'
          }`}
        >
          {agent.enabled ? 'running' : 'stopped'}
        </span>
      </div>

      {!agent.enabled && agent.disabled_reason && (
        <p className="text-[11px] text-ink/70 mb-3 border-l-2 border-amber-600 pl-2">
          Stopped: {agent.disabled_reason}
          {agent.disabled_at && ` · ${new Date(agent.disabled_at).toLocaleString()}`}
        </p>
      )}

      <Spend agent={agent} />

      <dl className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-[11px] mt-3 mb-3">
        <Field
          label="Last run"
          value={agent.last_run_at ? new Date(agent.last_run_at).toLocaleString() : 'never'}
        />
        <Field label="Outcome" value={agent.last_outcome ?? '—'} tone={agent.last_outcome} />
        <Field
          label="That run cost"
          value={agent.last_run_calls != null ? `${agent.last_run_calls} calls` : '—'}
        />
      </dl>

      {failure && (
        <p className="border-l-4 border-red-600 bg-red-50 px-3 py-2 mb-3 text-[11px] text-ink">
          <strong>Nothing changed.</strong> {failure}
        </p>
      )}

      {askingReason ? (
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            if (reason.trim()) void apply(false, reason)
          }}
        >
          <label htmlFor={`reason-${agent.agent_id}`} className="sr-only">
            Why are you stopping {agent.display_name}?
          </label>
          <input
            id={`reason-${agent.agent_id}`}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Why? e.g. looping on transliteration"
            autoFocus
            className="flex-1 min-w-[220px] border border-ink bg-white px-2 py-1.5 text-xs text-ink focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent"
          />
          <button
            type="submit"
            disabled={busy || !reason.trim()}
            className="bg-amber-500 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.15em] text-white disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            {busy ? 'Stopping…' : 'Stop agent'}
          </button>
          <button
            type="button"
            onClick={() => setAskingReason(false)}
            className="border border-ink px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.15em] text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            Cancel
          </button>
        </form>
      ) : (
        <button
          type="button"
          disabled={busy}
          onClick={() => (agent.enabled ? setAskingReason(true) : void apply(true))}
          className={`px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.15em] disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent transition-colors ${
            agent.enabled
              ? 'border border-ink text-ink hover:bg-ink hover:text-white'
              : 'bg-ink text-white hover:bg-accent'
          }`}
        >
          {busy ? 'Working…' : agent.enabled ? 'Stop this agent' : 'Start it again'}
        </button>
      )}
    </div>
  )
}

/** Spend against cap.
 *
 * An uncapped agent gets a sentence, not an empty bar. A bar at 0% reads as
 * "plenty of budget left" when the truth is "no limit is being enforced", and
 * those are opposite things for an operator to know. */
function Spend({ agent }: { agent: AgentRow }) {
  if (agent.spend_cap_calls == null) {
    return (
      <p className="text-[11px] text-ink/60">
        {agent.calls_24h} model calls in the last 24h. <strong>No cap set</strong> — this agent can
        spend without limit.
      </p>
    )
  }

  const pct = Math.min(100, Math.round((agent.budget_used ?? 0) * 100))

  return (
    <div>
      <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-[0.15em] text-ink/60 mb-1">
        <span>24h spend</span>
        <span className={agent.over_cap ? 'text-red-700' : ''}>
          {agent.calls_24h} / {agent.spend_cap_calls} calls
        </span>
      </div>
      <div
        className="h-2 w-full border border-ink bg-white"
        role="img"
        aria-label={`${agent.calls_24h} of ${agent.spend_cap_calls} model calls used in the last 24 hours`}
      >
        <div
          className={`h-full ${agent.over_cap ? 'bg-red-600' : 'bg-accent'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {agent.over_cap && (
        <p className="mt-1 text-[11px] text-red-700">
          At cap. The agent refuses to start rather than running a shorter job — a partial run would
          be the silent degradation §09 rules out.
        </p>
      )}
    </div>
  )
}

function Field({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone?: string | null
}) {
  const colour =
    tone === 'failed' ? 'text-red-700' : tone === 'blocked' ? 'text-amber-700' : 'text-ink'
  return (
    <div>
      <dt className="font-bold uppercase tracking-[0.1em] text-ink/50">{label}</dt>
      <dd className={`mt-0.5 break-words ${colour}`}>{value}</dd>
    </div>
  )
}

/** What ran, what it cost, and how it ended.
 *
 * `blocked` rows are the point, not noise: they are the evidence a kill switch
 * or a cap actually fired. An operator asking "did it work?" is asking for
 * exactly these. */
function RunLog({ runs }: { runs: AgentRun[] }) {
  return (
    <section>
      <h2 className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70 mb-2">
        Run log
      </h2>
      <p className="text-[11px] text-ink/50 leading-relaxed mb-3">
        Every run, including the ones a kill switch or a cap refused. A <em>blocked</em> entry is
        the control working.
      </p>

      {runs.length === 0 ? (
        <p className="border border-line bg-white p-3 text-sm text-ink/60">
          Nothing has run yet.
        </p>
      ) : (
        <div className="overflow-x-auto border border-ink bg-white">
          <table className="w-full min-w-[520px] text-xs">
            <caption className="sr-only">Recent agent runs, most recent first</caption>
            <thead>
              <tr className="border-b border-ink bg-paper">
                <th scope="col" className="text-left font-bold uppercase tracking-[0.1em] p-2">
                  When
                </th>
                <th scope="col" className="text-left font-bold uppercase tracking-[0.1em] p-2">
                  Agent
                </th>
                <th scope="col" className="text-left font-bold uppercase tracking-[0.1em] p-2">
                  Outcome
                </th>
                <th scope="col" className="text-right font-bold uppercase tracking-[0.1em] p-2">
                  Calls
                </th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} className="border-b border-line last:border-0">
                  <td className="p-2 whitespace-nowrap">
                    {new Date(run.started_at).toLocaleString()}
                  </td>
                  <td className="p-2 font-mono text-[10px] break-all">{run.agent_id}</td>
                  <td className="p-2">
                    <span
                      className={`px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.1em] ${
                        run.outcome === 'ok'
                          ? 'text-ink/60'
                          : run.outcome === 'blocked'
                            ? 'bg-amber-100 text-amber-900'
                            : 'bg-red-100 text-red-800'
                      }`}
                    >
                      {run.outcome}
                    </span>
                    {run.detail?.reason != null && (
                      <span className="ml-1.5 text-[11px] text-ink/60">
                        {String(run.detail.reason)}
                      </span>
                    )}
                  </td>
                  <td className="p-2 text-right tabular-nums">{run.model_calls}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
