import { defineConfig, devices } from '@playwright/test'

/**
 * Two lanes:
 * - Fixture lane (desktop + mobile projects): every API call is intercepted via
 *   page.route, so assertions are deterministic regardless of backend/data state
 *   (the dev backend wipes and re-ingests on every restart — implementation-pitfalls
 *   ENV-2/ENV-3 — so live data can never anchor exact-value assertions).
 * - Live smoke lane (live-smoke project): structural assertions against the real
 *   backend on :8000 through the Vite proxy. Opt-in via E2E_LIVE=1.
 *
 * Retries stay at 0: a flaky test gets fixed with deterministic synchronization,
 * never masked by retry (testing-pitfalls TEST-2).
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'desktop',
      testIgnore: /live-smoke/,
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
    },
    {
      name: 'mobile',
      testIgnore: /live-smoke/,
      use: { ...devices['Pixel 7'] },
    },
    {
      name: 'live-smoke',
      testMatch: /live-smoke/,
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 30_000,
  },
})
