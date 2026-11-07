import { verdictWordClass } from '../lib/scanResult'

/** The verdict as one giant flush-left word — the first thing on the result
 * page and its only `h1`. Colour carries the severity (accent red / accent-dark
 * / ink) but never alone: the word itself says it. */
export function VerdictWord({ verdict, label }: { verdict: string; label: string }) {
  return (
    <h1
      data-testid="verdict-word"
      data-verdict={verdict}
      className={`swiss-display text-left text-[clamp(3.5rem,17vw,10rem)] ${verdictWordClass(verdict)}`}
    >
      {label}
    </h1>
  )
}
