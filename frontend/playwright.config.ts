import { defineConfig, devices } from '@playwright/test'

// End-to-end journey + accessibility checks against a production build.
//
// Runs `vite preview` over the already-built `dist/` (CI builds first; locally
// run `npm run build` before `npm run test:e2e`). Every network request leaves
// through e2e/fixtures.ts, which mocks Supabase and the scan API and aborts
// anything else, so no test ever reaches a real service.
//
// The VITE_* values only need to be well formed: vite.config.ts refuses to load
// without them, even for `preview`. They match the CI build step.
const PORT = 4173
const buildEnv = {
  VITE_API_BASE_URL: 'https://raksha-ai-api.vercel.app',
  VITE_SUPABASE_URL: 'https://ci-placeholder.supabase.co',
  VITE_SUPABASE_ANON_KEY: 'ci-placeholder-anon-key',
}

// CI installs Playwright's bundled chromium. Locally, use the installed Chrome
// instead of downloading another browser.
const localChrome = process.env.CI ? {} : { channel: 'chrome' as const }

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : 1,
  reporter: process.env.CI ? [['list'], ['github']] : 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'retain-on-failure',
    ...localChrome,
  },
  projects: [
    {
      name: 'mobile-375',
      use: { ...devices['Desktop Chrome'], ...localChrome, viewport: { width: 375, height: 812 }, hasTouch: true, isMobile: true, deviceScaleFactor: 2 },
    },
    {
      name: 'desktop-1280',
      use: { ...devices['Desktop Chrome'], ...localChrome, viewport: { width: 1280, height: 800 } },
    },
  ],
  webServer: {
    command: `npx vite preview --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: buildEnv,
  },
})
