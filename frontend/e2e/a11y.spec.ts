import type { Page } from '@playwright/test'
import {
  test,
  expect,
  mockNetwork,
  seriousViolations,
  hasHorizontalScroll,
  SCAM_TEXT,
  SAFE_TEXT,
  HIGH_RISK_RESULT,
  SAFE_RESULT,
} from './fixtures.ts'

// axe-core with the WCAG 2.1 A/AA rule set. The bar is zero serious or critical
// violations on each page the journey touches, plus the 404 and login.

async function scanTo(page: Page, text: string) {
  await page.goto('/app')
  await page.getByRole('textbox', { name: /Paste the SMS/ }).fill(text)
  await page.getByRole('button', { name: 'Scan for scams' }).click()
  await expect(page.getByTestId('verdict-word')).toBeVisible()
}

test('landing has no serious/critical axe violations', async ({ page }) => {
  await mockNetwork(page)
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  expect(await seriousViolations(page)).toEqual([])
  expect(await hasHorizontalScroll(page)).toBe(false)
})

test('scan input has no serious/critical axe violations', async ({ page }) => {
  await mockNetwork(page, { signedIn: true })
  await page.goto('/app')
  await expect(page.getByRole('textbox', { name: /Paste the SMS/ })).toBeVisible()
  expect(await seriousViolations(page)).toEqual([])
})

test('high-risk result has no serious/critical axe violations', async ({ page }) => {
  await mockNetwork(page, { signedIn: true, scanResult: HIGH_RISK_RESULT })
  await scanTo(page, SCAM_TEXT)
  expect(await seriousViolations(page)).toEqual([])
})

test('safe result has no serious/critical axe violations', async ({ page }) => {
  await mockNetwork(page, { signedIn: true, scanResult: SAFE_RESULT })
  await scanTo(page, SAFE_TEXT)
  expect(await seriousViolations(page)).toEqual([])
})

test('404 has no serious/critical axe violations', async ({ page }) => {
  await mockNetwork(page)
  await page.goto('/definitely-not-a-page')
  await expect(page.getByRole('heading', { level: 1, name: 'Page not found' })).toBeVisible()
  expect(await seriousViolations(page)).toEqual([])
  expect(await hasHorizontalScroll(page)).toBe(false)
})

test('login has no serious/critical axe violations', async ({ page }) => {
  await mockNetwork(page)
  await page.goto('/login')
  await expect(page.getByRole('button', { name: 'Log in', exact: true })).toBeVisible()
  expect(await seriousViolations(page)).toEqual([])
})
