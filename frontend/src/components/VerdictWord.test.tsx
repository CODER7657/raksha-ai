import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { VerdictWord } from './VerdictWord'
import { VERDICT_META, verdictWordClass, type Verdict } from '../lib/scanResult'

afterEach(cleanup)

describe('VerdictWord', () => {
  it.each<[Verdict, string, string]>([
    ['high_risk', 'High Risk', 'text-accent'],
    ['suspicious', 'Suspicious', 'text-accent-dark'],
    ['safe', 'Safe', 'text-ink'],
  ])('renders %s as a giant flush-left h1 in %s', (verdict, label, colour) => {
    render(<VerdictWord verdict={verdict} label={label} />)
    const word = screen.getByRole('heading', { level: 1, name: label })
    const classes = word.className.split(/\s+/)
    expect(classes).toContain(colour)
    expect(classes).toContain('swiss-display')
    expect(classes).toContain('text-left')
    expect(classes).not.toContain('text-center')
    expect(word.dataset.verdict).toBe(verdict)
  })

  it('never paints safe or suspicious in the danger red', () => {
    for (const verdict of ['safe', 'suspicious'] as const) {
      const { unmount } = render(<VerdictWord verdict={verdict} label={verdict} />)
      expect(screen.getByTestId('verdict-word').className.split(/\s+/)).not.toContain('text-accent')
      unmount()
    }
  })

  it('falls back to ink for a verdict this build does not know', () => {
    render(<VerdictWord verdict="brand_new_verdict" label="Unknown" />)
    expect(screen.getByTestId('verdict-word').className.split(/\s+/)).toContain('text-ink')
  })

  it('renders the label as text, never as markup', () => {
    render(<VerdictWord verdict="high_risk" label={'<img src=x onerror=alert(1)>'} />)
    expect(document.querySelector('img')).toBeNull()
    expect(screen.getByTestId('verdict-word').textContent).toBe('<img src=x onerror=alert(1)>')
  })
})

describe('verdictWordClass', () => {
  it('matches VERDICT_META for every known verdict', () => {
    for (const [verdict, meta] of Object.entries(VERDICT_META)) {
      expect(verdictWordClass(verdict)).toBe(meta.wordClass)
    }
  })

  it.each(['', 'HIGH_RISK', 'toString', '__proto__', 'constructor'])('returns ink for %j', (value) => {
    expect(verdictWordClass(value)).toBe('text-ink')
  })

  it('keeps every verdict badge readable: white text only on the high-risk red', () => {
    expect(VERDICT_META.high_risk.badgeClass).toContain('text-white')
    expect(VERDICT_META.safe.badgeClass).toContain('text-ink')
    expect(VERDICT_META.suspicious.badgeClass).toContain('text-ink')
  })
})
