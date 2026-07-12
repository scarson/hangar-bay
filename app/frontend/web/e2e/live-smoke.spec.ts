import { expect, test } from '@playwright/test'
import { rowLinks } from './helpers/ui'

/**
 * Live-backend smoke lane — the one lane that exercises the REAL stack:
 * Vite proxy -> FastAPI -> Postgres. Everything here asserts structure and
 * invariants, never values: the dev backend wipes and re-ingests on every
 * restart (implementation-pitfalls ENV-2/ENV-3), so contract names, counts,
 * and prices are different on every run — and a dataset with zero ships is
 * legitimate (the first 100-contract sample of The Forge had none).
 *
 * Opt-in because it needs the backend up and settled on :8000:
 *   E2E_LIVE=1 npx playwright test --project=live-smoke
 */
test.skip(!process.env.E2E_LIVE, 'live smoke is opt-in: E2E_LIVE=1 with the backend on :8000')

/** Parse the announced total from the polite live region. */
async function announcedTotal(page: import('@playwright/test').Page): Promise<number> {
  const region = page.getByRole('status').filter({ hasText: /contracts? match/ })
  await expect(region).toHaveText(/[\d,]+ contracts? match/)
  const text = await region.textContent()
  return Number((text ?? '').replace(/[^\d]/g, ''))
}

test('ships-only default loads through the real proxy without error', async ({ page }) => {
  const responsePromise = page.waitForResponse((r) => r.url().includes('/api/v1/contracts/'))
  await page.goto('/')

  // PROXY-1 end-to-end: the proxied request itself must succeed — a bare-path
  // regression 307-escapes the proxy and this becomes a 404/error.
  const response = await responsePromise
  expect(response.status()).toBe(200)
  expect(new URL(response.url()).pathname).toBe('/api/v1/contracts/')

  await expect(page.getByRole('heading', { level: 1, name: 'Ship Contracts' })).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)

  // Structural XOR: N rows for N>0, the empty card for N=0. Both are valid
  // live datasets; an error or a mismatch between announcement and render is not.
  const total = await announcedTotal(page)
  if (total > 0) {
    await expect(rowLinks(page).first()).toBeVisible()
    expect(await rowLinks(page).count()).toBe(Math.min(total, 50))
  } else {
    await expect(page.getByRole('heading', { name: 'No contracts match these filters' })).toBeVisible()
  }
})

test('detail round-trip works on whatever the market offers', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1, name: 'Ship Contracts' })).toBeVisible()

  const total = await announcedTotal(page)
  test.skip(total === 0, 'live dataset has no ship contracts right now')

  const firstRow = rowLinks(page).first()
  const hull = (await firstRow.textContent()) ?? ''
  await firstRow.click()

  await expect(page).toHaveURL(/\/contracts\/\d+$/)
  await expect(page.getByRole('alert')).toHaveCount(0)
  await expect(page.getByRole('heading', { level: 1 })).toContainText(hull.trim())
  await expect(page.getByRole('region', { name: 'Contents' })).toBeVisible()

  // In-app history back restores the list.
  await page.getByRole('button', { name: '← All contracts' }).click()
  await expect(page).toHaveURL(/\/contracts(\?|$)/)
  await expect(rowLinks(page).first()).toBeVisible()
})

test('pagination crosses a real page boundary when the dataset has one', async ({ page }) => {
  // The all-contracts view maximizes the odds of multiple pages.
  await page.goto('/contracts?ships_only=false')
  await expect(page.getByRole('heading', { level: 1, name: 'All Contracts' })).toBeVisible()

  const next = page.getByRole('button', { name: 'Next →' })
  test.skip(await next.isDisabled(), 'live dataset fits on one page right now')

  const pageOneHrefs = new Set(
    await rowLinks(page).evaluateAll((links) => links.map((a) => a.getAttribute('href'))),
  )
  await next.click()
  await expect(page).toHaveURL(/page=2/)
  await expect(rowLinks(page).first()).toBeVisible()
  const pageTwoHrefs = await rowLinks(page).evaluateAll((links) => links.map((a) => a.getAttribute('href')))

  // Distinct parent entities across the boundary (SQLA-1 regression guard):
  // no contract may appear on both pages.
  expect(pageTwoHrefs.length).toBeGreaterThan(0)
  for (const href of pageTwoHrefs) {
    expect(pageOneHrefs.has(href)).toBe(false)
  }
})
