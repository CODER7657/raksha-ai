import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
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

  // The backend returns a bare count today and the itemised list later; prefer
  // the list when it is there, fall back to the count so the section is never
  // empty just because the richer field has not shipped.
  const ruleCount = rules.length || result.offline_flags_matched

  // True once every piece of evidence §03 promises is actually being returned.
  const complete = rules.length > 0 && patterns.length > 0 && !!trace?.model && !!trace?.audit

  return (
    <div className="border-t border-line pt-5 mb-6">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex w-full items-center justify-between gap-3 text-left text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent transition-colors"
      >
        <span>{open ? t('trace.hide') : t('trace.show')}</span>
        <span aria-hidden="true" className="text-ink/40">
          {open ? '—' : '+'}
        </span>
      </button>

      {open && (
        <div id={panelId} className="mt-4 space-y-5">
          <p className="text-[11px] text-ink/50 leading-relaxed">{t('trace.intro')}</p>

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
                          <p className="mt-1 text-[11px] text-ink/60 break-words">
                            {t('trace.matchedText')}:{' '}
                            <mark className="bg-accent/25 text-ink px-0.5">{rule.matched_text}</mark>
                          </p>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </TraceSection>

          {patterns.length > 0 && (
            <TraceSection label={t('trace.retrievedPatterns')}>
              <ul className="space-y-2">
                {patterns.map((pattern, i) => (
                  <li key={i} className="border border-line bg-white p-2.5">
                    <div className="flex items-start justify-between gap-3 flex-wrap">
                      <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-accent">
                        {pattern.category}
                      </span>
                      <span className="text-[11px] text-ink/60 shrink-0">
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
            <p className="text-[11px] text-ink/40 leading-relaxed">{t('trace.pending')}</p>
          )}
        </div>
      )}
    </div>
  )
}

function TraceSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70 mb-1.5">
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
