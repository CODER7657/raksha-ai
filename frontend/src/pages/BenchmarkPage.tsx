import { useEffect, useId, useState } from 'react'
import { CornerBrackets } from '../components/CornerBrackets'
import { ComparisonTable, FalsePositives, Metric } from '../components/BenchmarkComparison'
import { languageLabel } from '../lib/languages'
import {
  LOW_CONFIDENCE_CASE_COUNT,
  fetchLlmBenchmark,
  fetchOfflineRuleBenchmark,
  type BenchmarkReport,
  type LanguageBenchmark,
  type LlmBenchmarkReport,
  type LlmLanguageBenchmark,
} from '../lib/benchmark'

/** Reviewer-facing benchmark dashboard (#32 B).
 *
 * Copy is English-only by design: this is internal tooling, and #32 says so
 * explicitly. Corpus text is not — a case can be in any of the twelve scripts,
 * so anything rendering message text carries `dir="auto"` and wraps, or Urdu
 * arrives right-to-left inside a left-to-right table and reads as corruption.
 *
 * There is deliberately no headline number anywhere on this page. */
export function BenchmarkPage() {
  const [report, setReport] = useState<BenchmarkReport | null>(null)
  const [llm, setLlm] = useState<LlmBenchmarkReport | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchOfflineRuleBenchmark()
      .then(setReport)
      .catch((e: Error) => setError(e.message))
    // Failure here is not fatal: the offline half is computed live and always
    // available, while this one depends on somebody having committed a run.
    // A missing LLM benchmark degrades to "not run", not to a broken page.
    fetchLlmBenchmark()
      .then(setLlm)
      .catch(() => setLlm({ available: false }))
  }, [])

  if (error) {
    return (
      <div className="mx-auto max-w-4xl">
        <p className="border border-red-600 bg-red-50 p-4 text-sm text-ink">
          Could not load the benchmark: {error}
        </p>
      </div>
    )
  }

  if (!report) {
    return <p className="mx-auto max-w-4xl text-sm text-ink/60">Loading benchmark…</p>
  }

  return <BenchmarkReportView report={report} llm={llm} />
}

/** The render, split from the fetch so it can be exercised against a captured
 * backend payload without standing up auth. */
export function BenchmarkReportView({
  report,
  llm,
}: {
  report: BenchmarkReport
  llm: LlmBenchmarkReport | null
}) {
  const { corpus, provenance } = report
  const uncovered = corpus.languages_without_rules

  const llmByLanguage = new Map<string, LlmLanguageBenchmark>(
    llm?.available ? llm.languages.map((l) => [l.language, l]) : [],
  )
  const pairs = report.languages.map((rules) => ({
    language: rules.language,
    rules,
    model: llmByLanguage.get(rules.language) ?? null,
  }))

  // Both halves' false positives, kept in one section rather than split by
  // engine — a reviewer asking "what are we shouting at?" does not care which
  // half shouted.
  const falsePositiveGroups = [
    ...report.languages.map((l) => ({
      language: l.language,
      half: 'offline rules',
      cases: l.false_positive_cases ?? [],
    })),
    ...(llm?.available ? llm.languages : []).map((l) => ({
      language: l.language,
      half: 'RAG + LLM',
      cases: l.false_positive_cases ?? [],
    })),
  ]

  return (
    <div className="mx-auto max-w-4xl">
      <div className="flex items-center gap-2 mb-6">
        <span className="h-2 w-2 bg-accent" aria-hidden="true" />
        <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">
          Benchmark · both detection halves
        </span>
      </div>

      <div className="relative border border-ink bg-paper/60 backdrop-blur-sm p-6 sm:p-8 mb-6">
        <CornerBrackets />

        <p className="text-sm text-ink leading-relaxed mb-4">
          Precision and recall for both halves of detection, against the same corpus. The{' '}
          <strong>offline rule engine</strong> is the zero-network fallback that decides whether a
          user gets a warning or a 503 when both providers are down; the{' '}
          <strong>RAG&nbsp;+&nbsp;LLM path</strong> is what normally judges a message. They
          disagree, and where they disagree is the part worth reading.
        </p>

        <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
          <Stat label="Corpus cases" value={String(corpus.total_cases)} />
          <Stat
            label="Languages with cases"
            value={`${corpus.languages_covered}/${corpus.languages_supported}`}
          />
          <Stat
            label="Languages with rules"
            value={`${corpus.languages_with_rules.length}/${corpus.languages_supported}`}
          />
          <Stat label="Prompt version" value={provenance.prompt_version} />
        </dl>
      </div>

      {uncovered.length > 0 && (
        <div className="border-l-4 border-red-600 bg-red-50 px-4 py-3 mb-6">
          <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70">
            {uncovered.length} of {corpus.languages_supported} languages have no offline rules
          </p>
          <p className="mt-1 text-sm text-ink leading-relaxed">
            {uncovered.map((c) => languageLabel(c)).join(', ')} fall through to the English
            patterns, which cannot match native script. A scam in these languages fires nothing,
            so with both providers down the user gets an error page rather than a warning.
          </p>
        </div>
      )}

      <h2 className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70 mb-2">
        Both halves, per language
      </h2>
      <p className="text-[11px] text-ink/50 leading-relaxed mb-3">
        Never aggregated — a single figure across twelve languages is dominated by whichever one
        has the most cases. A language with {LOW_CONFIDENCE_CASE_COUNT} cases or fewer reads{' '}
        <em>too few</em> rather than a percentage: 100% over two cases is arithmetic, not evidence,
        and a dimmed 100% is still a 100% somebody can screenshot.
      </p>

      {llm && !llm.available && (
        <p className="border-l-4 border-ink/30 bg-paper px-4 py-3 mb-3 text-[11px] text-ink/60 leading-relaxed">
          No RAG&nbsp;+&nbsp;LLM run has been committed, so only the offline half has numbers.
          Scoring spends API quota per case, so it is a CLI rather than something this page can
          trigger: <code className="font-mono">python scripts/run_llm_benchmark.py --run --out
          testdata/benchmark/llm-latest.json</code>
        </p>
      )}

      <ComparisonTable pairs={pairs} />

      {llm?.available && <RunProvenance llm={llm} />}

      <FalsePositives groups={falsePositiveGroups} />

      <h2 className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70 mb-2">
        Offline rules in detail
      </h2>
      <p className="text-[11px] text-ink/50 leading-relaxed mb-3">
        The zero-network fallback on its own — the half that decides whether a user gets a warning
        or a 503 when both providers are down.
      </p>

      {/* Wide content scrolls inside its own container so the page body never
          scrolls sideways on a 375px phone. */}
      <div className="overflow-x-auto border border-ink bg-white mb-8">
        <table className="w-full min-w-[560px] text-xs">
          <caption className="sr-only">
            Offline rule engine precision and recall, broken down by language
          </caption>
          <thead>
            <tr className="border-b border-ink bg-paper">
              <th scope="col" className="text-left font-bold uppercase tracking-[0.1em] p-2">
                Language
              </th>
              <th scope="col" className="text-left font-bold uppercase tracking-[0.1em] p-2">
                Rules
              </th>
              <th scope="col" className="text-right font-bold uppercase tracking-[0.1em] p-2">
                Cases
              </th>
              <th scope="col" className="text-right font-bold uppercase tracking-[0.1em] p-2">
                Precision
              </th>
              <th scope="col" className="text-right font-bold uppercase tracking-[0.1em] p-2">
                Recall
              </th>
              <th scope="col" className="text-right font-bold uppercase tracking-[0.1em] p-2">
                Missed
              </th>
            </tr>
          </thead>
          <tbody>
            {report.languages.map((lang) => (
              <LanguageRow key={lang.language} lang={lang} />
            ))}
          </tbody>
        </table>
      </div>

      <MissedCases languages={report.languages} />
    </div>
  )
}

/** Which models and prompt produced the run being displayed.
 *
 * Not decoration. The provider ladder means a single run can be scored partly
 * by Groq and partly by Gemini — the first real run was, because Groq hit its
 * daily token cap partway through — so two runs are only comparable if you can
 * see what answered. Leakage is stated for the same reason: a reader seeing
 * 95.7% deserves to know whether anything was excluded to get there. */
function RunProvenance({ llm }: { llm: Extract<LlmBenchmarkReport, { available: true }> }) {
  const { run, leakage } = llm

  return (
    <div className="border border-line bg-white p-3 mb-8 text-[11px] text-ink/60 leading-relaxed">
      <p>
        RAG&nbsp;+&nbsp;LLM figures come from the last committed run — prompt{' '}
        <span className="font-mono text-ink">{run.prompt_version}</span>, scored by{' '}
        <span className="font-mono text-ink">{run.models.join(' + ') || 'unknown'}</span>.
        {run.models.length > 1 && (
          <> Two models answered, so per-case scores are not from a single judge.</>
        )}
      </p>
      <p className="mt-1">
        {leakage.held_out ? (
          <>
            Held out: no case sits within {leakage.threshold} similarity of a stored pattern, so
            nothing was graded against its own notes.
          </>
        ) : (
          <span className="text-red-700">
            {leakage.leaked_cases} case(s) are effectively present in the pattern database and were
            excluded. These figures cover only the remainder.
          </span>
        )}
      </p>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/60">{label}</dt>
      <dd className="mt-0.5 text-lg text-ink">{value}</dd>
    </div>
  )
}

function LanguageRow({ lang }: { lang: LanguageBenchmark }) {
  const unmeasured = lang.total_cases === 0

  return (
    <tr className={`border-b border-line last:border-0 ${unmeasured ? 'text-ink/40' : ''}`}>
      <th scope="row" className="text-left font-normal p-2">
        {languageLabel(lang.language)}{' '}
        <span className="text-ink/40 uppercase">{lang.language}</span>
      </th>
      <td className="p-2">
        {lang.has_rules ? (
          <span className="text-ink/60">yes</span>
        ) : (
          <span className="bg-red-100 text-red-800 px-1.5 py-0.5 font-bold">none</span>
        )}
      </td>
      <td className="p-2 text-right tabular-nums">{lang.total_cases}</td>
      {/* Same treatment as the comparison table above, deliberately. This table
          used to dim a small-sample percentage rather than withhold it, which
          left a bare 100% for a two-case language sitting directly under a
          table that had just refused to print one. */}
      <td className="p-2 text-right">
        <Metric value={lang.precision} cases={lang.total_cases} />
      </td>
      <td
        className={`p-2 text-right ${lang.recall === 0 ? 'text-red-700 font-bold' : ''}`}
      >
        <Metric value={lang.recall} cases={lang.total_cases} />
      </td>
      <td className="p-2 text-right tabular-nums">
        {lang.false_negatives > 0 ? lang.false_negatives : '—'}
      </td>
    </tr>
  )
}

function MissedCases({ languages }: { languages: LanguageBenchmark[] }) {
  const withMisses = languages.filter((l) => l.missed_cases.length > 0)
  if (withMisses.length === 0) return null

  return (
    <section>
      <h2 className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70 mb-2">
        What is being missed
      </h2>
      <p className="text-[11px] text-ink/50 leading-relaxed mb-3">
        Scam cases where no rule fired at all. A recall figure says how bad it is; these say what
        to fix.
      </p>
      <div className="space-y-4">
        {withMisses.map((lang) => (
          <MissedForLanguage key={lang.language} lang={lang} />
        ))}
      </div>
    </section>
  )
}

function MissedForLanguage({ lang }: { lang: LanguageBenchmark }) {
  const [open, setOpen] = useState(false)
  const panelId = useId()

  return (
    <div className="border border-line">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex w-full items-center justify-between gap-3 p-3 text-left text-xs font-bold uppercase tracking-[0.1em] text-ink/70 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent transition-colors"
      >
        <span>
          {languageLabel(lang.language)} — {lang.missed_cases.length} missed
        </span>
        <span aria-hidden="true" className="text-ink/40">
          {open ? '—' : '+'}
        </span>
      </button>

      {open && (
        <ul id={panelId} className="border-t border-line divide-y divide-line">
          {lang.missed_cases.map((c) => (
            <li key={c.id} className="p-3 bg-white">
              <div className="flex items-center justify-between gap-2 flex-wrap mb-1.5">
                <span className="font-mono text-[10px] text-ink/50 break-all">{c.id}</span>
                <span
                  className={`text-[10px] font-bold uppercase tracking-[0.1em] px-1.5 py-0.5 ${
                    c.status === 'known_gap'
                      ? 'bg-amber-100 text-amber-900'
                      : 'bg-red-100 text-red-800'
                  }`}
                >
                  {c.status === 'known_gap' ? 'known gap' : 'regression'}
                </span>
              </div>
              {/* dir="auto" is load-bearing: without it an Urdu case renders
                  left-to-right inside this table and reads as corrupted text. */}
              <p dir="auto" className="text-sm text-ink leading-relaxed break-words">
                {c.text}
              </p>
              {c.expected_rule_ids.length > 0 && (
                <p className="mt-1.5 text-[11px] text-ink/60 break-words">
                  Expected: {c.expected_rule_ids.join(', ')}
                </p>
              )}
              {c.note && <p className="mt-1 text-[11px] text-ink/50 leading-relaxed">{c.note}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
