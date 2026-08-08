import { expect, test } from '@playwright/test'
import { SEVEN_SHIPS, COURIER_CONTRACTS, pageOf, taxonomy } from './fixtures/contracts'
import { interceptContractList, interceptCurrentUser, interceptTaxonomy } from './helpers/api'
import { openFiltersIfCollapsed, rowLinks } from './helpers/ui'

/**
 * F008 cascading dogma filter (Criteria 3.2–3.5, 12).
 *
 * The option lists are served, never assembled by the client (Criterion 3.5),
 * and the surface opens only once the corpus reports `complete` (decision log
 * D1) — so every test here says which of those two states it is in. Wire
 * assertions accompany the rendered ones throughout (testing-pitfalls TEST-5):
 * a checked box that never reaches the query string is the dead control this
 * whole feature exists to remove.
 */

/** The taxonomy of a corpus whose resweep has finished. */
const READY = taxonomy({ coverage: 'complete' })

const category = (page: import('@playwright/test').Page, name: string) =>
  page.getByRole('checkbox', { name, exact: true })


// Every contracts view queries the taxonomy endpoint for the item-level
// readiness signal. Routing it here keeps the fixture lane hermetic; a test
// that needs the surface open registers its own interceptTaxonomy, which wins
// because page.route handlers run last-registered-first.
test.beforeEach(async ({ page }) => {
  await interceptTaxonomy(page)
})

test.describe('taxonomy filters', () => {
  test('a category selection scopes the group list and reaches the wire', async ({ page }) => {
    await interceptCurrentUser(page, { status: 401 })
    await interceptTaxonomy(page, READY)
    const calls = await interceptContractList(page, pageOf(SEVEN_SHIPS))

    await page.goto('/contracts')
    await expect(rowLinks(page)).toHaveCount(7)
    await openFiltersIfCollapsed(page)

    // Every group is on offer while nothing narrows the list.
    await expect(category(page, 'Shield Booster')).toBeVisible()

    await category(page, 'Ship').check()

    await expect(page).toHaveURL(/category_id=/)
    // Scoped: the Module group goes, the two Ship groups stay.
    await expect(category(page, 'Shield Booster')).toHaveCount(0)
    await expect(category(page, 'Frigate')).toBeVisible()
    await expect(category(page, 'Battleship')).toBeVisible()

    await expect
      .poll(() => calls.some((call) => call.params.getAll('category_id').includes('6')))
      .toBe(true)
  })

  test('type-ahead narrows the group list, and a group selection rides beside its category', async ({
    page,
  }) => {
    await interceptCurrentUser(page, { status: 401 })
    await interceptTaxonomy(page, READY)
    const calls = await interceptContractList(page, pageOf(SEVEN_SHIPS))

    await page.goto('/contracts?category_id=6')
    await expect(rowLinks(page)).toHaveCount(7)
    await openFiltersIfCollapsed(page)

    await page.getByLabel('Filter group list').fill('frig')
    await expect(category(page, 'Battleship')).toHaveCount(0)
    await category(page, 'Frigate').check()

    await expect(page).toHaveURL(/group_id=/)
    await expect
      .poll(() =>
        calls.some(
          (call) =>
            call.params.getAll('category_id').includes('6') &&
            call.params.getAll('group_id').includes('25'),
        ),
      )
      .toBe(true)
  })

  test('a shared taxonomy URL restores both selections and sends both params on first load', async ({
    page,
  }) => {
    await interceptCurrentUser(page, { status: 401 })
    await interceptTaxonomy(page, READY)
    const calls = await interceptContractList(page, pageOf(SEVEN_SHIPS))

    await page.goto('/contracts?category_id=6&group_id=25')
    await expect(rowLinks(page)).toHaveCount(7)
    await openFiltersIfCollapsed(page)

    await expect(category(page, 'Ship')).toBeChecked()
    await expect(category(page, 'Frigate')).toBeChecked()
    expect(calls[0].params.getAll('category_id')).toEqual(['6'])
    expect(calls[0].params.getAll('group_id')).toEqual(['25'])
  })

  test('unchecking a category takes its group selections with it, in one navigation', async ({
    page,
  }) => {
    await interceptCurrentUser(page, { status: 401 })
    await interceptTaxonomy(page, READY)
    const calls = await interceptContractList(page, pageOf(SEVEN_SHIPS))

    await page.goto('/contracts?category_id=6&category_id=7&group_id=25&group_id=77')
    await expect(rowLinks(page)).toHaveCount(7)
    await openFiltersIfCollapsed(page)
    await expect(category(page, 'Shield Booster')).toBeChecked()

    await category(page, 'Module').uncheck()

    // Shield Booster's category is gone, so Shield Booster is gone — a group
    // left in the URL would keep filtering with nothing on screen to clear it.
    await expect(category(page, 'Shield Booster')).toHaveCount(0)
    await expect(category(page, 'Frigate')).toBeChecked()
    await expect
      .poll(() => {
        const last = calls.at(-1)!.params
        return [last.getAll('category_id'), last.getAll('group_id')]
      })
      .toEqual([['6'], ['25']])
  })

  test('the filters are absent, and say so, while the corpus is still being enriched', async ({
    page,
  }) => {
    // The default taxonomy route (registered in the file-level beforeEach)
    // reports `partial`, which is the cold-cache state.
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractList(page, pageOf(SEVEN_SHIPS))

    await page.goto('/contracts')
    await expect(rowLinks(page)).toHaveCount(7)
    await openFiltersIfCollapsed(page)

    await expect(page.getByText('Item filters are still indexing.')).toBeVisible()
    await expect(category(page, 'Ship')).toHaveCount(0)
  })

  test('the filters stand down on a segment whose contracts carry no items', async ({ page }) => {
    await interceptCurrentUser(page, { status: 401 })
    await interceptTaxonomy(page, READY)
    await interceptContractList(page, pageOf(COURIER_CONTRACTS))

    await page.goto('/contracts?contract_type=courier')
    await expect(rowLinks(page)).toHaveCount(3)
    await openFiltersIfCollapsed(page)

    await expect(
      page.getByText('Item filters do not apply to contracts that carry no items.'),
    ).toBeVisible()
    await expect(category(page, 'Ship')).toHaveCount(0)
    // Ships only is still shown — the reader has to see what the segment did to
    // it — but it cannot be re-checked from here, only by leaving the segment.
    await expect(page.getByLabel('Ships only')).toBeDisabled()
  })
})
