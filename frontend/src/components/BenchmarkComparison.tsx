import { useId, useState } from 'react'
import { languageLabel } from '../lib/languages'
import {
  formatMetric,
  hasEnoughCases,
  type FalsePositiveCase,
  type LanguageBenchmark,
  type LlmLanguageBenchmark,
} from '../lib/benchmark'

/** The two benchmark halves, compared rather than tabled side by side (#50).
 *
 * The offline rules and the RAG+LLM path disagree, and where they disagree is
 * the whole value: the rules ignore a genuine SBI debit alert that the model
 * flags, and the model catches a cross-sentence refund scam the rules miss. A
 * reviewer should see "rules say X, model says Y" without opening two views.
 *
 * Two things this deliberately does not do:
 *
 * 1. **No aggregate figure, anywhere.** Both payloads refuse to produce one on
 *    purpose — a single number across twelve languages is dominated by whichever
 *    language someone happened to write cases for. Adding one here would undo
 *    that on the surface people actually read.
 * 2. **No percentage under a handful of cases.** Nine languages have two rows
 *    each. `recall: 1.000` over two cases is true and reads as parity, so it is
 *    rendered as words instead of a dimmed number — a dimmed 100% is still a
 *    100% somebody can screenshot.
 */

/** A metric, or an honest refusal to state one.
 *
 * Exported because every table on the page has to use it. A "too few" in one
 * table and a bare `100%` for the same language in another is worse than
 * neither — the reader takes the number, and the caveat reads as a quibble. */
export function Metric({ value, cases }: { value: number | null; cases: number }) {
  if (cases === 0) return <span className="text-ink/40">—</span>
  if (!hasEnoughCases(cases)) {
    return (
      <span className="text-ink/50 italic" title={`${cases} case(s) — too few to score`}>
        too few
      </span>
    )
  }
  return <span className="tabular-nums">{formatMetric(value)}</span>
}

type Pair = {
  language: string
  rules: LanguageBenchmark
  model: LlmLanguageBenchmark | null
}

export function ComparisonTable({ pairs }: { pairs: Pair[] }) {
  return (
    <div className="overflow-x-auto border border-ink bg-white mb-8">
      <table className="w-full min-w-[680px] text-xs">
        <caption className="sr-only">
          Offline rule engine compared with the RAG and LLM pipeline, per language. No aggregate
          row.
        </caption>
        <thead>
          <tr className="border-b border-line bg-paper text-ink/60">
            <th scope="col" />
            <th scope="col" />
            <th scope="col" colSpan={2} className="text-center font-bold uppercase tracking-[0.1em] p-2 border-l border-line">
              Offline rules
            </th>
            <th scope="col" colSpan={2} className="text-center font-bold uppercase tracking-[0.1em] p-2 border-l border-line">
              RAG + LLM
            </th>
            <th scope="col" className="border-l border-line" />
          </tr>
          <tr className="border-b border-ink bg-paper">
            <th scope="col" className="text-left font-bold uppercase tracking-[0.1em] p-2">
              Language
            </th>
            <th scope="col" className="text-right font-bold uppercase tracking-[0.1em] p-2">
              Cases
            </th>
            <th scope="col" className="text-right font-bold uppercase tracking-[0.1em] p-2 border-l border-line">
              Prec
            </th>
            <th scope="col" className="text-right font-bold uppercase tracking-[0.1em] p-2">
              Recall
            </th>
            <th scope="col" className="text-right font-bold uppercase tracking-[0.1em] p-2 border-l border-line">
              Prec
            </th>
            <th scope="col" className="text-right font-bold uppercase tracking-[0.1em] p-2">
              Recall
            </th>
            <th scope="col" className="text-left font-bold uppercase tracking-[0.1em] p-2 border-l border-line">
              Disagreement
            </th>
          </tr>
        </thead>
        <tbody>
          {pairs.map((pair) => (
            <ComparisonRow key={pair.language} pair={pair} />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ComparisonRow({ pair }: { pair: Pair }) {
  const { rules, model } = pair
  const cases = rules.total_cases
  const unmeasured = cases === 0

  // Cases one half caught and the other did not, by id. This is the column a
  // reviewer actually scans — a language where both halves agree needs no
  // attention, and one where they diverge is where a rule is missing or a
  // model is over-warning.
  const ruleMisses = new Set(rules.missed_cases.map((c) => c.id))
  const modelMisses = new Set((model?.missed_cases ?? []).map((c) => c.id))
  const modelSaved = [...ruleMisses].filter((id) => !modelMisses.has(id)).length
  const rulesSaved = [...modelMisses].filter((id) => !ruleMisses.has(id)).length

  return (
    <tr className={`border-b border-line last:border-0 ${unmeasured ? 'text-ink/40' : ''}`}>
      <th scope="row" className="text-left font-normal p-2">
        {languageLabel(rules.language)} <span className="text-ink/40 uppercase">{rules.language}</span>
        {!rules.has_rules && (
          <span className="ml-1.5 bg-red-100 text-red-800 px-1 py-0.5 text-[10px] font-bold">
            no rules
          </span>
        )}
      </th>
      <td className="p-2 text-right tabular-nums">{cases || '—'}</td>

      <td className="p-2 text-right border-l border-line">
        <Metric value={rules.precision} cases={cases} />
      </td>
      <td className="p-2 text-right">
        <Metric value={rules.recall} cases={cases} />
      </td>

      <td className="p-2 text-right border-l border-line">
        {model ? <Metric value={model.precision} cases={model.scored_cases} /> : <NotRun />}
      </td>
      <td className="p-2 text-right">
        {model ? <Metric value={model.recall} cases={model.scored_cases} /> : <NotRun />}
      </td>

      <td className="p-2 border-l border-line text-[11px] leading-tight">
        {modelSaved > 0 && (
          <div className="text-ink">
            model caught <strong>{modelSaved}</strong> the rules missed
          </div>
        )}
        {rulesSaved > 0 && (
          <div className="text-ink">
            rules caught <strong>{rulesSaved}</strong> the model missed
          </div>
        )}
        {modelSaved === 0 && rulesSaved === 0 && !unmeasured && (
          <span className="text-ink/40">none</span>
        )}
      </td>
    </tr>
  )
}

function NotRun() {
  return (
    <span className="text-ink/40" title="not in the last committed run">
      not run
    </span>
  )
}

/** Benign messages something warned about.
 *
 * Deliberately rendered above the misses and in the same visual weight. Over-
 * warning is the accepted failure direction, and that stays defensible only
 * while we can name what is being warned about — today's single English false
 * positive is a real bank debit alert, the most common legitimate SMS our users
 * receive. Warning on those at scale is alarm fatigue, which is how someone
 * learns to ignore the warning that matters. */
export function FalsePositives({
  groups,
}: {
  groups: { language: string; half: string; cases: FalsePositiveCase[] }[]
}) {
  const nonEmpty = groups.filter((g) => g.cases.length > 0)

  return (
    <section className="mb-8">
      <h2 className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70 mb-2">
        What we are shouting at
      </h2>
      <p className="text-[11px] text-ink/50 leading-relaxed mb-3">
        Benign messages that triggered a warning. Over-warning is the failure we accept, and that
        holds only while we can say what is being warned about — a precision figure alone cannot
        tell one odd edge case from every bank alert in the country.
      </p>

      {nonEmpty.length === 0 ? (
        <p className="border border-line bg-white p-3 text-sm text-ink/60">
          No benign case triggered a warning in either half.
        </p>
      ) : (
        <div className="space-y-4">
          {nonEmpty.map((group) => (
            <CaseGroup
              key={`${group.half}-${group.language}`}
              title={`${languageLabel(group.language)} — ${group.cases.length} warned about, ${group.half}`}
              tone="warn"
            >
              {group.cases.map((c) => (
                <li key={c.id} className="p-3 bg-white">
                  <div className="flex items-center justify-between gap-2 flex-wrap mb-1.5">
                    <span className="font-mono text-[10px] text-ink/50 break-all">{c.id}</span>
                    {c.verdict && (
                      <span className="bg-amber-100 text-amber-900 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.1em]">
                        {c.verdict} {c.risk_score !== undefined && `(${c.risk_score})`}
                      </span>
                    )}
                  </div>
                  {/* dir="auto" or an Urdu case renders left-to-right and reads
                      as corrupted text. */}
                  <p dir="auto" className="text-sm text-ink leading-relaxed break-words">
                    {c.text}
                  </p>
                  {c.fired_rule_ids && c.fired_rule_ids.length > 0 && (
                    <p className="mt-1.5 text-[11px] text-ink/60 break-words">
                      Fired: {c.fired_rule_ids.join(', ')}
                    </p>
                  )}
                  {c.note && (
                    <p className="mt-1 text-[11px] text-ink/50 leading-relaxed">{c.note}</p>
                  )}
                </li>
              ))}
            </CaseGroup>
          ))}
        </div>
      )}
    </section>
  )
}

export function CaseGroup({
  title,
  tone,
  children,
}: {
  title: string
  tone: 'warn' | 'miss'
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(false)
  const panelId = useId()

  return (
    <div className={`border ${tone === 'warn' ? 'border-amber-600' : 'border-line'}`}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex w-full items-center justify-between gap-3 p-3 text-left text-xs font-bold uppercase tracking-[0.1em] text-ink/70 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent transition-colors"
      >
        <span>{title}</span>
        <span aria-hidden="true" className="text-ink/40">
          {open ? '—' : '+'}
        </span>
      </button>
      {open && (
        <ul id={panelId} className="border-t border-line divide-y divide-line">
          {children}
        </ul>
      )}
    </div>
  )
}
