import { expect, test } from '@playwright/test'
import { bigDataset, paginate } from './fixtures/contracts'
import { interceptContractList } from './helpers/api'
import { rowLinks } from './helpers/ui'

/**
 * F002 Criteria 1.2–1.3 / testing-pitfalls TEST-4: pagination that short-changes,
 * duplicates, or skips items is invisible to any single-page test. Every scenario
 * here uses a 120-row fixture at the default size 50 (3 pages) served through the
 * same slice-by-page logic the backend uses (`paginate`), so a boundary bug fails
 * loudly. TEST-5: each scenario asserts the request page param on the wire AND the
 * rendered outcome, never just one.
 */

/** The `·` label format is verbatim from Pagination.tsx (`Page {page} of {n} · {total} contracts`). */
const pagination = (page: import('@playwright/test').Page) =>
  page.getByRole('navigation', { name: 'Pagination' })

test.describe('pagination', () => {
  test('walks every page across boundaries with no gaps or duplicates', async ({ page }) => {
    const all = bigDataset(120)
    // Hull labels are the row-link text (primaryLabel prefers the ship item);
    // derive the expected set from the fixture so it stays coupled to the builder.
    const expectedLabels = all.map((c) => c.items[0].type_name as string)
    const calls = await interceptContractList(page, (params) =>
      paginate(all, Number(params.get('page')), Number(params.get('size'))),
    )

    await page.goto('/contracts')
    await expect(page.getByRole('heading', { level: 1, name: 'Ship Contracts' })).toBeVisible()

    const nav = pagination(page)
    const expectedSizes = [50, 50, 20] // two full pages then the 20-row remainder
    const firstOfPage = [expectedLabels[0], expectedLabels[50], expectedLabels[100]]
    const collected: string[][] = []

    for (let n = 1; n <= 3; n++) {
      if (n > 1) await page.getByRole('button', { name: /Next/ }).click()

      await expect(page).toHaveURL(new RegExp(`[?&]page=${n}(?:&|$)`))
      // keepPreviousData holds the prior rows while the next page loads; wait for
      // this page's first hull before reading, so the count reflects the new slice.
      await expect(rowLinks(page).first()).toHaveText(firstOfPage[n - 1])
      await expect(rowLinks(page)).toHaveCount(expectedSizes[n - 1])
      await expect(nav).toContainText(`Page ${n} of 3 · 120 contracts`)

      collected.push(await rowLinks(page).allTextContents())
    }

    // TEST-4: union of all pages == the full 120, intersection across pages empty.
    const seen = new Set<string>()
    for (const labels of collected) {
      for (const label of labels) {
        expect(seen.has(label), `"${label}" appeared on two pages`).toBe(false)
        seen.add(label)
      }
    }
    expect(seen.size).toBe(120)
    expect([...seen].sort()).toEqual([...expectedLabels].sort())

    // TEST-5: each page was fetched from the wire with its own page param at size 50.
    for (let n = 1; n <= 3; n++) {
      expect(
        calls.some((c) => c.params.get('page') === String(n) && c.params.get('size') === '50'),
      ).toBe(true)
    }
    expect(calls[0].url.pathname).toBe('/api/v1/contracts/')
  })

  test('Previous is disabled on the first page and Next on the last', async ({ page }) => {
    const all = bigDataset(120)
    await interceptContractList(page, (params) =>
      paginate(all, Number(params.get('page')), Number(params.get('size'))),
    )

    await page.goto('/contracts')
    await expect(rowLinks(page).first()).toHaveText(all[0].items[0].type_name as string)
    await expect(page.getByRole('button', { name: /Previous/ })).toBeDisabled()
    await expect(page.getByRole('button', { name: /Next/ })).toBeEnabled()

    await page.goto('/contracts?page=3')
    await expect(rowLinks(page).first()).toHaveText(all[100].items[0].type_name as string)
    await expect(page.getByRole('button', { name: /Next/ })).toBeDisabled()
    await expect(page.getByRole('button', { name: /Previous/ })).toBeEnabled()
  })

  test('scrolls back to the top after paging forward', async ({ page }) => {
    // Mechanism (confirmed in @tanstack/router-core scroll-restoration.js): on every
    // navigation's `onRendered`, resetScroll (default true) calls window.scrollTo(0,0).
    const all = bigDataset(120)
    await interceptContractList(page, (params) =>
      paginate(all, Number(params.get('page')), Number(params.get('size'))),
    )

    await page.goto('/contracts')
    await expect(rowLinks(page).first()).toHaveText(all[0].items[0].type_name as string)

    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
    const before = await page.evaluate(() => window.scrollY)
    // Guard against a vacuous assertion: the page must actually be scrolled first.
    expect(before).toBeGreaterThan(0)

    await page.getByRole('button', { name: /Next/ }).click()
    await expect(page).toHaveURL(/[?&]page=2(?:&|$)/)
    await expect(rowLinks(page).first()).toHaveText(all[50].items[0].type_name as string)

    // The reset fires on onRendered, a tick after the row swap — poll, never sleep.
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0)
  })

  test('rewrites an out-of-range page to the last valid page', async ({ page }) => {
    // ContractsPage's redirect effect: data.total>0 && page>pageCount -> navigate
    // replace to pageCount. The backend echoes {total>0, items:[]} for pages past
    // the end (paginate reproduces this), which triggers the self-heal.
    const all = bigDataset(120)
    const calls = await interceptContractList(page, (params) =>
      paginate(all, Number(params.get('page')), Number(params.get('size'))),
    )

    await page.goto('/contracts?page=9')

    await expect(page).toHaveURL(/[?&]page=3(?:&|$)/)
    await expect(rowLinks(page).first()).toHaveText(all[100].items[0].type_name as string)
    await expect(rowLinks(page)).toHaveCount(20)
    await expect(pagination(page)).toContainText('Page 3 of 3 · 120 contracts')

    // It requested the out-of-range page, discovered total/pageCount, then the clamp.
    expect(calls.some((c) => c.params.get('page') === '9')).toBe(true)
    expect(calls.some((c) => c.params.get('page') === '3')).toBe(true)
  })

  test('deep-links straight to a middle page without walking from page 1', async ({ page }) => {
    const all = bigDataset(120)
    const calls = await interceptContractList(page, (params) =>
      paginate(all, Number(params.get('page')), Number(params.get('size'))),
    )

    await page.goto('/contracts?page=2')

    await expect(page).toHaveURL(/[?&]page=2(?:&|$)/)
    await expect(rowLinks(page).first()).toHaveText(all[50].items[0].type_name as string)
    await expect(rowLinks(page)).toHaveCount(50)
    await expect(pagination(page)).toContainText('Page 2 of 3 · 120 contracts')

    // Fetched page 2 directly; page 1 was never requested.
    expect(calls.some((c) => c.params.get('page') === '2')).toBe(true)
    expect(calls.every((c) => c.params.get('page') !== '1')).toBe(true)
  })
})
