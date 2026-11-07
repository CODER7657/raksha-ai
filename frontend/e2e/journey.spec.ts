import {
  test,
  expect,
  mockNetwork,
  signIn,
  hasHorizontalScroll,
  SCAM_TEXT,
  SAFE_TEXT,
  HIGH_RISK_RESULT,
  SAFE_RESULT,
} from './fixtures.ts'

// The one journey the roadmap gates on: a visitor lands, signs in (mocked
// Supabase session), pastes a scam message and gets the verdict as a giant
// flush-left word. Runs once per viewport project (375x812 and 1280x800).

test('landing -> sign in -> scan text -> high-risk verdict', async ({ page }) => {
  const seen = await mockNetwork(page, { scanResult: HIGH_RISK_RESULT })

  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Spot the scam')
  expect(await hasHorizontalScroll(page)).toBe(false)

  // Sign in: hand the app a session the way supabase-js stores one, then load
  // the login route, which forwards a signed-in user into the app.
  await signIn(page)
  await page.goto('/login')
  await expect(page).toHaveURL(/\/app$/)

  const message = page.getByRole('textbox', { name: /Paste the SMS/ })
  await expect(message).toBeVisible()
  expect(await hasHorizontalScroll(page)).toBe(false)
  await message.fill(SCAM_TEXT)

  const scanRequest = page.waitForRequest((r) => r.url().endsWith('/api/scan/text') && r.method() === 'POST')
  await page.getByRole('button', { name: 'Scan for scams' }).click()
  expect((await scanRequest).postDataJSON()).toEqual({ text: SCAM_TEXT, language: 'en' })

  await expect(page).toHaveURL(/\/app\/result$/)
  const verdict = page.getByTestId('verdict-word')
  await expect(verdict).toHaveText('High Risk')
  await expect(verdict).toHaveCSS('color', 'rgb(216, 20, 27)')
  await expect(verdict).toHaveCSS('text-align', /left|start/)
  // "Giant": at least 3x the 16px body size at every viewport.
  const size = await verdict.evaluate((el) => parseFloat(getComputedStyle(el).fontSize))
  expect(size).toBeGreaterThanOrEqual(48)
  await expect(page.getByText(HIGH_RISK_RESULT.recommended_action)).toBeVisible()
  expect(await hasHorizontalScroll(page)).toBe(false)

  // Only the two mocked origins were ever asked for anything.
  expect(seen.length).toBeGreaterThan(0)
  for (const request of seen) {
    expect(request).toMatch(/^[A-Z]+ https:\/\/(raksha-ai-api\.vercel\.app|ci-placeholder\.supabase\.co)\//)
  }
})

test('a safe message renders the verdict in ink', async ({ page }) => {
  await mockNetwork(page, { signedIn: true, scanResult: SAFE_RESULT })
  await page.goto('/app')
  await page.getByRole('textbox', { name: /Paste the SMS/ }).fill(SAFE_TEXT)
  await page.getByRole('button', { name: 'Scan for scams' }).click()

  const verdict = page.getByTestId('verdict-word')
  await expect(verdict).toHaveText('Safe')
  await expect(verdict).toHaveCSS('color', 'rgb(17, 17, 17)')
  expect(await hasHorizontalScroll(page)).toBe(false)
})

test('an empty submission shows the error and makes no API call', async ({ page }) => {
  const seen = await mockNetwork(page, { signedIn: true })
  await page.goto('/app')
  await page.getByRole('button', { name: 'Scan for scams' }).click()
  await expect(page.getByText('Paste a message first.')).toBeVisible()
  expect(seen.filter((r) => r.includes('/api/scan'))).toEqual([])
})

test('a failed scan keeps the user on the input with the server message', async ({ page }) => {
  await mockNetwork(page, { signedIn: true, scanStatus: 500 })
  await page.goto('/app')
  await page.getByRole('textbox', { name: /Paste the SMS/ }).fill(SCAM_TEXT)
  await page.getByRole('button', { name: 'Scan for scams' }).click()
  await expect(page.getByText('Detection service unavailable')).toBeVisible()
  await expect(page).toHaveURL(/\/app$/)
})

test('the app is closed to a signed-out visitor', async ({ page }) => {
  await mockNetwork(page)
  await page.goto('/app')
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Spot the scam')
})

test('opening the result page directly offers a way back', async ({ page }) => {
  await mockNetwork(page, { signedIn: true })
  await page.goto('/app/result')
  await expect(page.getByText('No scan result to show.')).toBeVisible()
  await page.getByRole('button', { name: 'Back to scan' }).click()
  await expect(page).toHaveURL(/\/app$/)
})

test('no horizontal scroll at 375, 768 or 1280 on any journey page', async ({ page }) => {
  await mockNetwork(page, { signedIn: true, scanResult: HIGH_RISK_RESULT })
  for (const width of [375, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/app')
    await page.getByRole('textbox', { name: /Paste the SMS/ }).fill(SCAM_TEXT)
    expect(await hasHorizontalScroll(page), `scan input at ${width}`).toBe(false)
    await page.getByRole('button', { name: 'Scan for scams' }).click()
    await expect(page.getByTestId('verdict-word')).toBeVisible()
    expect(await hasHorizontalScroll(page), `result at ${width}`).toBe(false)
    await page.goto('/nope')
    expect(await hasHorizontalScroll(page), `404 at ${width}`).toBe(false)
  }
})

test('every journey control is at least 44px tall', async ({ page }) => {
  await mockNetwork(page, { signedIn: true, scanResult: HIGH_RISK_RESULT })
  await page.goto('/app')
  await page.getByRole('textbox', { name: /Paste the SMS/ }).fill(SCAM_TEXT)
  const small = async () =>
    page.evaluate(() =>
      [...document.querySelectorAll('main button, main a, main select, header button, header a, header select')]
        .filter((el) => (el as HTMLElement).offsetParent !== null)
        .filter((el) => el.getBoundingClientRect().height < 44)
        .map((el) => `${el.tagName} "${el.textContent?.trim().slice(0, 30)}" ${Math.round(el.getBoundingClientRect().height)}px`),
    )
  expect(await small()).toEqual([])
  await page.getByRole('button', { name: 'Scan for scams' }).click()
  await expect(page.getByTestId('verdict-word')).toBeVisible()
  expect(await small()).toEqual([])
})
