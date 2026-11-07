import { test as base, expect, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

// Everything external is mocked here. The app talks to two origins in
// production (Supabase and the FastAPI backend); both are answered from this
// file, and any other non-local request is aborted so a forgotten call fails
// loudly instead of silently reaching the internet.

export const API_ORIGIN = 'https://raksha-ai-api.vercel.app'
export const SUPABASE_ORIGIN = 'https://ci-placeholder.supabase.co'
// supabase-js derives its storage key from the project ref (first host label).
const STORAGE_KEY = 'sb-ci-placeholder-auth-token'

export const SCAM_TEXT =
  'Dear customer your SBI KYC is expiring today. Click bit.ly/kyc-upd8 and share the OTP to avoid account block.'
export const SAFE_TEXT = 'Hi, the parents meeting at school is moved to 4 pm on Friday. See you there.'

export const HIGH_RISK_RESULT = {
  risk_score: 92,
  verdict: 'high_risk',
  flagged_phrases: ['KYC is expiring', 'share the OTP'],
  explanation: 'Banks never ask for an OTP over SMS. This message uses urgency and a shortened link.',
  recommended_action: 'Do not click the link or share any OTP. Call your bank on the number printed on your card.',
  community_report_count: 14,
  offline_flags_matched: 2,
  transcript: null,
  trace: null,
}

export const SAFE_RESULT = {
  risk_score: 4,
  verdict: 'safe',
  flagged_phrases: [],
  explanation: 'An ordinary personal message with no links, payment requests or urgency.',
  recommended_action: 'No action needed.',
  community_report_count: 0,
  offline_flags_matched: 0,
  transcript: null,
  trace: null,
}

const FAR_FUTURE = Math.floor(Date.now() / 1000) + 60 * 60 * 24 * 365

const fakeUser = {
  id: '00000000-0000-4000-8000-000000000001',
  aud: 'authenticated',
  role: 'authenticated',
  email: 'e2e@example.com',
  app_metadata: { provider: 'email' },
  user_metadata: {},
  created_at: '2026-01-01T00:00:00Z',
}

const fakeSession = {
  access_token: 'e2e-access-token',
  refresh_token: 'e2e-refresh-token',
  token_type: 'bearer',
  expires_in: 3600,
  expires_at: FAR_FUTURE,
  user: fakeUser,
}

export interface MockOptions {
  signedIn?: boolean
  scanResult?: typeof HIGH_RISK_RESULT | typeof SAFE_RESULT
  /** Non-200 makes the scan endpoint fail with a FastAPI-style `detail`. */
  scanStatus?: number
}

/** Store a session exactly where supabase-js looks for one. Takes effect on the
 * next full page load. */
export async function signIn(page: Page) {
  await page.evaluate(
    ([key, value]) => window.localStorage.setItem(key, value),
    [STORAGE_KEY, JSON.stringify(fakeSession)] as const,
  )
}

export async function mockNetwork(
  page: Page,
  { signedIn = false, scanResult = HIGH_RISK_RESULT, scanStatus = 200 }: MockOptions = {},
) {
  const seen: string[] = []

  if (signedIn) {
    await page.addInitScript(
      ([key, value]) => window.localStorage.setItem(key, value),
      [STORAGE_KEY, JSON.stringify(fakeSession)] as const,
    )
  }

  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url())
    if (url.hostname === 'localhost' || url.hostname === '127.0.0.1') return route.continue()

    seen.push(`${route.request().method()} ${url.origin}${url.pathname}`)

    if (url.origin === SUPABASE_ORIGIN) {
      if (url.pathname.startsWith('/auth/v1/user')) return route.fulfill({ json: fakeUser })
      if (url.pathname.startsWith('/auth/v1/token')) return route.fulfill({ json: fakeSession })
      if (url.pathname.startsWith('/auth/v1/logout')) return route.fulfill({ status: 204, body: '' })
      return route.fulfill({ json: {} })
    }

    if (url.origin === API_ORIGIN) {
      if (url.pathname === '/api/scan/text') {
        return scanStatus === 200
          ? route.fulfill({ json: scanResult })
          : route.fulfill({ status: scanStatus, json: { detail: 'Detection service unavailable' } })
      }
      // 503 is the documented "use the browser voice" answer (lib/voice.ts).
      if (url.pathname.startsWith('/api/tts')) return route.fulfill({ status: 503, json: { detail: 'off' } })
      if (url.pathname === '/api/history') return route.fulfill({ json: [] })
      return route.fulfill({ status: 404, json: { detail: 'not mocked' } })
    }

    return route.abort('blockedbyclient')
  })

  return seen
}

/** Serious and critical axe violations only — the bar the roadmap sets. */
export async function seriousViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
  return results.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target.join(' ')).slice(0, 5) }))
}

/** True when the document is wider than the viewport. */
export async function hasHorizontalScroll(page: Page) {
  return page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
}

export const test = base
export { expect }
