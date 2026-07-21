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
    baseURL: 'https://localhost:5173',
    ignoreHTTPSErrors: true,
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'desktop',
      testIgnore: /e2e\/live-smoke/,
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
    },
    {
      name: 'mobile',
      testIgnore: /e2e\/live-smoke/,
      use: { ...devices['Pixel 7'] },
    },
    {
      name: 'live-smoke',
      testMatch: /e2e\/live-smoke/,
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
    },
    // Prod-targeting smoke lane (CD's post-deploy gate): env-driven origin, real
    // certs enforced, and — critically — no local dev server (see webServer below).
    ...(process.env.E2E_PROD_BASE_URL
      ? [{
          name: 'live-smoke-prod',
          testMatch: /e2e\/live-smoke/,
          use: {
            ...devices['Desktop Chrome'],
            viewport: { width: 1280, height: 800 },
            baseURL: process.env.E2E_PROD_BASE_URL,
            ignoreHTTPSErrors: false,   // production must present a valid cert
          },
        }]
      : []),
  ],
  // The prod lane must NEVER boot a local dev server — it targets a deployed origin.
  webServer: process.env.E2E_PROD_BASE_URL
    ? undefined
    : {
        command: 'npm run dev',
        url: 'https://localhost:5173',
        ignoreHTTPSErrors: true,
        reuseExistingServer: true,
        timeout: 30_000,
      },
})
