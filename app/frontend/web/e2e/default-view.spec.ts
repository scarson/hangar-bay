import { expect, test } from '@playwright/test'
import { SEVEN_SHIPS, pageOf } from './fixtures/contracts'
import { interceptContractList, interceptCurrentUser } from './helpers/api'
import { openFiltersIfCollapsed, rowLinks } from './helpers/ui'

/**
 * F002 Criterion 1.1 / PRODUCT.md: the default view is ship contracts ONLY —
 * non-ship contracts are reachable by an explicit toggle, never the default.
 */
test.describe('default view', () => {
  test('root redirects to /contracts and shows ships-only by default', async ({ page }) => {
    await interceptCurrentUser(page, { status: 401 })
    const calls = await interceptContractList(page, pageOf(SEVEN_SHIPS))

    await page.goto('/')

    await expect(page).toHaveURL(/\/contracts/)
    await expect(page.getByRole('heading', { level: 1, name: 'Ship Contracts' })).toBeVisible()
    await expect(page).toHaveTitle('Ship Contracts — Hangar Bay')

    // Every hull renders as a row link, in fixture (issued-desc) order.
    await expect(rowLinks(page)).toHaveText([
      'Revelation',
      'Raven',
      'Maelstrom',
      'Purifier',
      'Hound',
      'Breacher',
      'Minmatar Shuttle',
    ])

    // Polite live region announces the count (wording is currently always
    // plural — recorded closing-gate nit, so match loosely on purpose).
    await expect(page.getByRole('status')).toHaveText(/7 contracts? match/)

    // The ships-only toggle reflects the default.
    await openFiltersIfCollapsed(page)
    await expect(page.getByLabel('Ships only')).toBeChecked()

    // Request contract (TEST-5: assert the wire, not just the render):
    // schema path verbatim WITH trailing slash (PROXY-1) and the ships-only
    // default translated to is_ship_contract=true.
    expect(calls.length).toBeGreaterThan(0)
    const first = calls[0]
    expect(first.url.pathname).toBe('/api/v1/contracts/')
    expect(first.params.get('is_ship_contract')).toBe('true')
    expect(first.params.get('page')).toBe('1')
    expect(first.params.get('size')).toBe('50')
    expect(first.params.get('sort_by')).toBe('date_issued')
    expect(first.params.get('sort_direction')).toBe('desc')
    expect(first.params.has('search')).toBe(false)
  })

  test('unchecking Ships only widens to All Contracts and drops the API filter', async ({ page }) => {
    await interceptCurrentUser(page, { status: 401 })
    const calls = await interceptContractList(page, (params) =>
      pageOf(params.get('is_ship_contract') === 'true' ? SEVEN_SHIPS : SEVEN_SHIPS.slice(0, 2)),
    )

    await page.goto('/contracts')
    await expect(page.getByRole('heading', { level: 1, name: 'Ship Contracts' })).toBeVisible()

    await openFiltersIfCollapsed(page)
    await page.getByLabel('Ships only').uncheck()

    await expect(page.getByRole('heading', { level: 1, name: 'All Contracts' })).toBeVisible()
    await expect(page).toHaveURL(/ships_only=false/)
    await expect(rowLinks(page)).toHaveText(['Revelation', 'Raven'])

    // ships_only=false means the param is ABSENT from the API call, not false.
    const last = calls[calls.length - 1]
    expect(last.params.has('is_ship_contract')).toBe(false)
  })
})
