export type Verdict = 'safe' | 'suspicious' | 'high_risk'

/** `labelKey` points into the `verdict` i18n namespace — call t(meta.labelKey)
 * at the render site rather than storing the translated string here, since
 * this module has no access to the active language. */
/** Colours come from the `--color-verdict-*` tokens in index.css, which are
 * checked against design/tokens.json — the same file the Android Compose theme
 * is generated from. They were `bg-emerald-600` / `bg-amber-500` / `bg-red-600`;
 * the hex is unchanged, but a verdict is now painted from one shared definition
 * rather than two independent ones (#116 §2). */
/** `wordClass` is the Swiss verdict word on the result page: high risk in the
 * accent red, suspicious in accent-dark, safe in plain ink. Deliberately not a
 * green/amber/red traffic light there — one red, used only for danger. The
 * badges keep the shared verdict colours, with the label in ink where white
 * text would fall under 4.5:1 on emerald or amber. */
export const VERDICT_META: Record<Verdict, { labelKey: string; badgeClass: string; barClass: string; wordClass: string }> = {
  safe: { labelKey: 'verdict.safe', badgeClass: 'bg-verdict-safe text-ink', barClass: 'bg-verdict-safe', wordClass: 'text-ink' },
  suspicious: { labelKey: 'verdict.suspicious', badgeClass: 'bg-verdict-suspicious text-ink', barClass: 'bg-verdict-suspicious', wordClass: 'text-accent-dark' },
  high_risk: { labelKey: 'verdict.highRisk', badgeClass: 'bg-verdict-high-risk text-white', barClass: 'bg-verdict-high-risk', wordClass: 'text-accent' },
}

/** The class that colours a verdict's word, or plain ink for a verdict string
 * this build does not know (a newer backend), rather than throwing. */
export function verdictWordClass(verdict: string): string {
  return Object.hasOwn(VERDICT_META, verdict) ? VERDICT_META[verdict as Verdict].wordClass : 'text-ink'
}

/** One known scam pattern pulled back by the RAG retrieval step, with how
 * closely it matched. `similarity` is cosine, 0–1. */
export interface RetrievedPattern {
  pattern_text: string
  category: string
  similarity: number
  /** Where this pattern came from (#32 C/E). `agent` means an agent drafted it
   * and a person approved it into the database — never that an agent put it
   * there unreviewed, which the schema forbids.
   *
   * Optional because a verdict recorded before provenance existed genuinely
   * does not know, and absence must not be rendered as `human`: "we did not
   * record it" and "a person wrote it" are different claims. */
  provenance?: 'human' | 'agent'
  drafted_by?: string | null
}

/** One offline rule that fired before any network call. `rule_id` is looked up
 * in the `trace.rules.*` i18n namespace for a human-readable name; when the id
 * is unknown the raw `pattern` is shown instead, so a newly added backend rule
 * degrades to something legible rather than blank. */
export interface OfflineRuleHit {
  rule_id: string
  pattern: string
  matched_text: string
}

/** Which model and prompt produced the verdict. Without this a decision made
 * six months ago cannot be reproduced — see ARCHITECTURE.md §03. */
export interface ModelStamp {
  provider: string
  model: string
  prompt_version: string
  /** True when this verdict was served from the cache rather than judged now
   * (#68). The backend has sent it since the cache landed and this type did not
   * declare it, so the client could not render it — meaning two identical
   * verdicts were indistinguishable from two independent judgements, which is
   * exactly what stamping it was meant to prevent. */
  cached?: boolean
  /** When the cached verdict was originally judged. Present only on a cache
   * hit; `null` where the stored row predates the field. */
  first_judged_at?: string | null
}

/** Position of this verdict in the append-only, hash-chained audit log. */
export interface AuditRecord {
  record_id: string
  hash: string
  prev_hash: string | null
}

/** The reasoning trace behind a verdict.
 *
 * Every field is optional on purpose. The backend lands these incrementally
 * (ARCHITECTURE.md §03 / roadmap P0) — today the scan pipeline computes the
 * retrieved patterns and then discards them, and never captures a model
 * version at all. The viewer renders whatever is present so the UI can ship
 * ahead of the persistence work instead of waiting on it.
 *
 * Field names here are the frontend's half of a contract that does not exist
 * yet; they need Pavan's sign-off before the backend implements them. */
/** Whether retrieval had a corpus to search at all (#88).
 *
 * An empty `retrieved_patterns` meant two different things and said neither:
 * the corpus was searched and nothing was close, or this language has no
 * corpus. Nine of the twelve supported languages are currently the second, and
 * a verdict there is the model answering unaided rather than a grounded one.
 *
 * `language_covered: null` is a third state and not a falsy second: a cached
 * verdict skipped retrieval, so coverage was never established. Rendering that
 * as "no patterns exist" would assert a gap on a scan that never looked. */
export interface RetrievalCoverage {
  language_covered: boolean | null
  patterns_retrieved: number
  /** How many cleared the weak-match floor and actually reached the prompt.
   * Not derivable from the count above — five retrieved and none used is a
   * different verdict from five retrieved and five used. */
  patterns_used: number
  skipped?: string
}

/** Whether a speaker of this language has read its detection rules (#89).
 *
 * Two booleans rather than one, because one would mislead in whichever
 * direction it was set. Every language falls back to the **English** rules,
 * which are reviewed — so a code-mixed message ("your KYC is expiring, share
 * OTP") is caught by reviewed rules in all twelve languages. What is unreviewed
 * in eight of them is detection of text written wholly in the language's own
 * script. */
export interface RuleReview {
  status: 'in-service' | 'inherited' | 'reviewed-by-proxy' | 'unreviewed'
  native_reviewed: boolean
  code_mixed_reviewed: boolean
  /** `mr` borrows Hindi's rules because the vocabulary genuinely overlaps.
   * Weaker than review, stronger than nothing, and its own claim. */
  inherited_from: string | null
  /** The language a `reviewed-by-proxy` review went through — someone read
   * these rules via a language they do speak.
   *
   * Deliberately not folded into `inherited_from`: that says *whose rules
   * these are*, this says *who read them, and through what*. Marathi
   * inheriting Hindi's rules involves no human at all, so collapsing the two
   * would leave a reader unable to tell a borrowed rule set from a reviewed
   * one. A language code, never a person's name. */
  reviewed_via: string | null
}

/** One named finding from A2 stage 1's static link checks. */
export interface LinkSignal {
  name: string
  /**
   * Which observation this derives from. Two signals sharing a basis are ONE
   * witness — do not count signals to decide how much agrees.
   */
  basis: string
  /** False only for a signal that attacker-controlled page content could move. */
  deterministic: boolean
  detail: string
}

export interface LinkSignals {
  signals: LinkSignal[]
  /**
   * Distinct bases, already computed. Never render `signals.length` as the
   * amount of agreement: a single lookalike domain fires three checks that are
   * all one observation about one string.
   */
  independent_witnesses: number
  /** Whether at least one signal is immune to page content. */
  deterministic_witness: boolean
  /**
   * True when this evidence stopped the verdict being `safe`. The verdict shown
   * is already the floored one — do not raise it again here. Worth surfacing in
   * the explanation, because the message text looked ordinary and the link did
   * not, and that is a different story from "this message is a scam".
   */
  verdict_floor_applied: boolean
}

/**
 * Email only, and absent entirely for SMS or pasted text — those have no sender
 * to check, which is a different statement from a sender that could not be
 * checked.
 */
export interface SenderCheck {
  /**
   * `unverifiable` is the normal case, not an error: a shared or forwarded
   * message does not carry what SPF and DKIM need. A `pass` says the mail
   * really came from the domain it claims and nothing about whether that
   * domain is trustworthy — never render it as "safe sender".
   */
  verification: 'pass' | 'fail' | 'unverifiable'
  /** Show these. They are never evidence and must not be counted as signals. */
  caveats: string[]
}

export interface ScanTrace {
  rule_review?: RuleReview
  offline_rules_fired?: OfflineRuleHit[]
  retrieved_patterns?: RetrievedPattern[]
  retrieval?: RetrievalCoverage
  model?: ModelStamp
  link_signals?: LinkSignals
  sender?: SenderCheck
  audit?: AuditRecord
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
  trace?: ScanTrace | null
}
