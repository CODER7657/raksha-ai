import { mkdirSync } from 'node:fs'
import { join } from 'node:path'
import type { Page } from '@playwright/test'
import { test, expect, mockNetwork, SCAM_TEXT, SAFE_TEXT, HIGH_RISK_RESULT, SAFE_RESULT } from './fixtures.ts'

// Review screenshots, not assertions. Skipped unless SHOTS_DIR is set, e.g.
//   SHOTS_DIR=/abs/path/after npm run test:e2e -- screenshots
// Selectors are text/role based so the same spec can photograph an older build.
const dir = process.env.SHOTS_DIR

test.skip(!dir, 'set SHOTS_DIR to capture screenshots')

function shot(name: string, project: string) {
  mkdirSync(dir!, { recursive: true })
  return join(dir!, `${name}-${project.replace(/\D/g, '')}.png`)
}

async function settle(page: Page) {
  await page.evaluate(() => document.fonts.ready.then(() => undefined))
}

async function scan(page: Page, text: string) {
  await page.goto('/app')
  await page.getByRole('textbox', { name: /Paste the SMS/ }).fill(text)
  await page.getByRole('button', { name: 'Scan for scams' }).click()
  await expect(page).toHaveURL(/\/app\/result$/)
  await expect(page.getByText('What to do').first()).toBeVisible()
}

test('landing', async ({ page }, info) => {
  await mockNetwork(page)
  await page.goto('/')
  await settle(page)
  await page.screenshot({ path: shot('landing', info.project.name), fullPage: true })
})

test('scan-input', async ({ page }, info) => {
  await mockNetwork(page, { signedIn: true })
  await page.goto('/app')
  await page.getByRole('textbox', { name: /Paste the SMS/ }).fill(SCAM_TEXT)
  await settle(page)
  await page.screenshot({ path: shot('scan-input', info.project.name), fullPage: true })
})

test('result-high-risk', async ({ page }, info) => {
  await mockNetwork(page, { signedIn: true, scanResult: HIGH_RISK_RESULT })
  await scan(page, SCAM_TEXT)
  await settle(page)
  await page.screenshot({ path: shot('result-high-risk', info.project.name), fullPage: true })
})

test('result-safe', async ({ page }, info) => {
  await mockNetwork(page, { signedIn: true, scanResult: SAFE_RESULT })
  await scan(page, SAFE_TEXT)
  await settle(page)
  await page.screenshot({ path: shot('result-safe', info.project.name), fullPage: true })
})

test('not-found', async ({ page }, info) => {
  await mockNetwork(page)
  await page.goto('/definitely-not-a-page')
  await settle(page)
  await page.screenshot({ path: shot('404', info.project.name), fullPage: true })
})
