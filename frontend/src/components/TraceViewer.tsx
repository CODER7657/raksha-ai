import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Minus, Plus } from 'lucide-react'
import type { ScanResult } from '../lib/scanResult'

/** The reasoning trace behind a verdict (ARCHITECTURE.md §03).
 *
 * Collapsed by default. The people this app is built for — first-time digital
 * banking users, often elderly — need the verdict and the one next step, not
 * cosine similarities and prompt versions. But an institutional buyer cannot
 * deploy a system whose decisions it cannot audit, and a judge asked to see the
 * reasoning and there was no view to show. So the evidence is always one
 * keypress away, and never in the way.
 *
 * Each section renders only when its evidence is actually present, so this
 * works against today's backend and fills in as the persistence work lands. */
export function TraceViewer({ result }: { result: ScanResult }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const panelId = useId()

  const trace = result.trace ?? undefined
  const rules = trace?.offline_rules_fired ?? []
  const patterns = trace?.retrieved_patterns ?? []
  const retrieval = trace?.retrieval
  // Counted rather than a boolean: "one of five patterns came from an agent"
  // and "all five did" are different claims about how much of the verdict
  // rests on machine-drafted evidence.
  const agentDrafted = patterns.filter((p) => p.provenance === 'agent').length
  const review = trace?.rule_review

  // The backend returns a bare count today and the itemised list later; prefer
  // the list when it is there, fall back to the count so the section is never
  // empty just because the richer field has not shipped.
  const ruleCount = rules.length || result.offline_flags_matched

  // True once every piece of evidence §03 promises is actually being returned.
  const complete = rules.length > 0 && patterns.length > 0 && !!trace?.model && !!trace?.audit

  return (
    <div className="border-t border-rule pt-3">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex min-h-11 w-full items-center justify-between gap-3 text-left swiss-label text-ink transition-colors hover:text-accent"
      >
        <span>{open ? t('trace.hide') : t('trace.show')}</span>
        {open ? <Minus aria-hidden="true" size={18} /> : <Plus aria-hidden="true" size={18} />}
      </button>

      {open && (
        <div id={panelId} className="mt-4 space-y-5">
          <p className="text-xs text-ink/70 leading-relaxed">{t('trace.intro')}</p>

          {review && !review.native_reviewed && (
            /* Deliberately inside the collapsed panel, next to the rules it
               qualifies — not a banner on the verdict.
               A caveat on every scan in eight languages would train people to
               dismiss the warning that is correct, which costs more than the
               uncertainty it discloses. It sits where someone asking "how much
               should I trust this?" will find it. */
            <p className="border-l-2 border-accent-dark bg-paper px-2 py-1.5 text-xs text-ink leading-relaxed">
              {review.inherited_from
                ? t('trace.rulesInherited')
                : t('trace.rulesUnreviewed')}
            </p>
          )}

          <TraceSection label={t('trace.offlineRules')}>
            {ruleCount === 0 ? (
              <p className="text-xs text-ink/60 leading-relaxed">{t('trace.offlineRulesNone')}</p>
            ) : (
              <>
                <p className="text-xs text-ink/60 leading-relaxed">
                  {t('trace.offlineRulesCount', { count: ruleCount })}
                </p>
                {rules.length > 0 && (
                  <ul className="mt-2 space-y-2">
                    {rules.map((rule, i) => (
                      <li key={i} className="border border-line bg-white p-2.5">
                        <p className="text-xs font-bold text-ink break-words">
                          {/* An unknown rule id falls back to the raw pattern rather
                              than rendering the missing translation key. */}
                          {t([`trace.rules.${rule.rule_id}`, 'trace.ruleUnknown'], {
                            pattern: rule.pattern,
                          })}
                        </p>
                        {rule.matched_text && (
                          <p className="mt-1 text-xs text-ink/60 break-words">
                            {t('trace.matchedText')}:{' '}
                            <mark className="bg-accent/10 text-ink px-0.5">{rule.matched_text}</mark>
                          </p>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </TraceSection>

          {/* #88. An empty pattern list used to render as nothing at all, which
              read as "this section does not apply" rather than "this verdict was
              not grounded in anything". For nine of the twelve supported
              languages the corpus is empty, and a verdict there is the model
              answering unaided — which a reader is entitled to know, because it
              is the difference between the RAG claim holding and not.

              Only when the backend actually said so. `language_covered: null`
              means retrieval was skipped (a cache hit) and coverage was never
              established, so nothing is claimed either way. */}
          {retrieval?.language_covered === false && (
            <TraceSection label={t('trace.retrievedPatterns')}>
              <p className="border-l-2 border-accent-dark bg-paper px-2 py-1.5 text-xs text-ink leading-relaxed">
                {t('trace.noPatternsForLanguage')}
              </p>
            </TraceSection>
          )}

          {patterns.length > 0 && (
            <TraceSection label={t('trace.retrievedPatterns')}>
              {/* #32 E. Stated once above the list rather than inferred from
                  badges: "some of the evidence behind this verdict was drafted
                  by an agent" is a claim about the verdict, and a reader
                  scanning five rows should not have to assemble it themselves.
                  Only rendered when it is true — a line saying "no agents were
                  involved" on every ordinary verdict is noise that trains
                  people to skip the section. */}
              {agentDrafted > 0 && (
                <p className="mb-2 border-l-2 border-accent bg-accent/10 px-2 py-1 text-xs text-ink leading-relaxed">
                  {t('trace.agentInfluenced', { count: agentDrafted, total: patterns.length })}
                </p>
              )}
              <ul className="space-y-2">
                {patterns.map((pattern, i) => (
                  <li key={i} className="border border-line bg-white p-2.5">
                    <div className="flex items-start justify-between gap-3 flex-wrap">
                      <span className="text-xs font-bold uppercase tracking-[0.1em] text-accent">
                        {pattern.category}
                      </span>
                      <span className="text-xs text-ink/60 shrink-0">
                        {pattern.provenance === 'agent' && (
                          <span
                            className="mr-1.5 bg-ink px-1 py-0.5 text-xs font-bold uppercase tracking-[0.1em] text-white"
                            title={
                              pattern.drafted_by
                                ? `Drafted by ${pattern.drafted_by}, approved by a person`
                                : undefined
                            }
                          >
                            {t('trace.agentDrafted')}
                          </span>
                        )}
                        {t('trace.similarity', { percent: Math.round(pattern.similarity * 100) })}
                      </span>
                    </div>
                    <p className="mt-1.5 text-xs text-ink leading-relaxed break-words">
                      {pattern.pattern_text}
                    </p>
                    <div className="mt-2 h-1 w-full bg-line" aria-hidden="true">
                      <div
                        className="h-full bg-accent"
                        style={{ width: `${Math.round(pattern.similarity * 100)}%` }}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            </TraceSection>
          )}

          {trace?.model && (
            <TraceSection label={t('trace.model')}>
              <dl className="space-y-1 text-xs">
                <TraceRow label={t('trace.provider')} value={trace.model.provider} />
                <TraceRow label={t('trace.modelName')} value={trace.model.model} />
                <TraceRow label={t('trace.promptVersion')} value={trace.model.prompt_version} />
              </dl>
            </TraceSection>
          )}

          {trace?.audit && (
            <TraceSection label={t('trace.auditRecord')}>
              <dl className="space-y-1 text-xs">
                <TraceRow label={t('trace.recordId')} value={trace.audit.record_id} />
                <TraceRow label={t('trace.recordHash')} value={trace.audit.hash} />
              </dl>
            </TraceSection>
          )}

          {!complete && (
            <p className="text-xs text-ink/70 leading-relaxed">{t('trace.pending')}</p>
          )}
        </div>
      )}
    </div>
  )
}

function TraceSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="swiss-label text-ink mb-1.5">
        {label}
      </h3>
      {children}
    </section>
  )
}

function TraceRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 flex-wrap">
      <dt className="text-ink/60">{label}</dt>
      <dd className="font-mono text-ink break-all text-right">{value}</dd>
    </div>
  )
}
