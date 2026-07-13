import { expect, test } from '@playwright/test'
import { BPC_CONTRACTS, SEVEN_SHIPS, makeContract, makeShipItem, pageOf } from './fixtures/contracts'
import { interceptContractDetail, interceptContractList, interceptCurrentUser } from './helpers/api'
import { rowLinks } from './helpers/ui'

/**
 * The responsive filter-rail disclosure. Below the `lg` breakpoint the rail
 * collapses behind a single "Filters" button (ContractsPage.tsx: aria-expanded,
 * aria-controls='filter-rail', one FilterRail instance toggled by a `hidden`
 * class — NOT conditional render). At/above lg the button is display:none and
 * the <aside aria-label="Contract filters"> is a permanent column.
 *
 * This spec is about the breakpoint seam itself, so tests are gated by project:
 * the disclosure mobile-only tests skip on desktop, and the desktop-column test
 * skips on mobile. Scenario 5 (table usability) runs on both.
 */
test.describe('responsive filter-rail disclosure', () => {
  const isMobile = () => test.info().project.name === 'mobile'

  const filtersButton = (page: import('@playwright/test').Page) =>
    page.getByRole('button', { name: 'Filters', exact: true })

  test('mobile: disclosure is closed by default and its controls are not interactable', async ({
    page,
  }) => {
    test.skip(!isMobile(), 'the Filters disclosure only exists below the lg breakpoint')
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractList(page, pageOf(SEVEN_SHIPS))

    await page.goto('/contracts')
    await expect(page.getByRole('heading', { level: 1, name: 'Ship Contracts' })).toBeVisible()

    // The disclosure control itself is present and reports collapsed.
    await expect(filtersButton(page)).toBeVisible()
    await expect(filtersButton(page)).toHaveAttribute('aria-expanded', 'false')

    // Single DOM instance (display toggle, not conditional render): the rail is
    // in the tree exactly once, but hidden, so its controls can't be operated.
    await expect(page.locator('#filter-rail')).toHaveCount(1)
    await expect(page.locator('#filter-rail')).toBeHidden()
    await expect(page.getByLabel('Ships only')).toBeHidden()
    await expect(page.getByLabel('Blueprint copies only')).toBeHidden()
  })

  test('mobile: open reveals controls, a filter goes end-to-end, close hides them again', async ({
    page,
  }) => {
    test.skip(!isMobile(), 'the Filters disclosure only exists below the lg breakpoint')
    await interceptCurrentUser(page, { status: 401 })
    // Keyed responder: is_bpc=true serves the blueprint set, otherwise the ships.
    const calls = await interceptContractList(page, (params) =>
      pageOf(params.get('is_bpc') === 'true' ? BPC_CONTRACTS : SEVEN_SHIPS),
    )

    await page.goto('/contracts')
    await expect(page.getByRole('heading', { level: 1, name: 'Ship Contracts' })).toBeVisible()
    await expect(rowLinks(page)).toHaveText([
      'Revelation',
      'Raven',
      'Maelstrom',
      'Purifier',
      'Hound',
      'Breacher',
      'Minmatar Shuttle',
    ])

    // Open the disclosure → expanded, and the controls become visible.
    await filtersButton(page).click()
    await expect(filtersButton(page)).toHaveAttribute('aria-expanded', 'true')
    await expect(page.getByLabel('Blueprint copies only')).toBeVisible()

    // Interact end-to-end: the checkbox writes is_bpc=true to the URL, the app
    // re-queries, and the keyed responder swaps the rendered rows (TEST-5:
    // assert the wire AND the rendered outcome, TEST-2: no weakening).
    await page.getByLabel('Blueprint copies only').check()
    await expect(page).toHaveURL(/is_bpc=true/)
    await expect(rowLinks(page)).toHaveText([
      'Draugur Blueprint',
      'Phoenix Blueprint',
      'Breacher Blueprint',
    ])
    const last = calls.at(-1)!
    expect(last.url.pathname).toBe('/api/v1/contracts/')
    expect(last.params.get('is_bpc')).toBe('true')
    // Ships-only is still on (unchanged by the bpc toggle), so both ship the wire.
    expect(last.params.get('is_ship_contract')).toBe('true')

    // Close again → collapsed, and the controls are hidden once more.
    await filtersButton(page).click()
    await expect(filtersButton(page)).toHaveAttribute('aria-expanded', 'false')
    await expect(page.getByLabel('Blueprint copies only')).toBeHidden()
  })

  test('mobile: filter state applied while open survives closing the disclosure', async ({
    page,
  }) => {
    test.skip(!isMobile(), 'the Filters disclosure only exists below the lg breakpoint')
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractList(page, (params) =>
      pageOf(params.get('is_bpc') === 'true' ? BPC_CONTRACTS : SEVEN_SHIPS),
    )

    await page.goto('/contracts')
    await expect(page.getByRole('heading', { level: 1, name: 'Ship Contracts' })).toBeVisible()

    await filtersButton(page).click()
    await page.getByLabel('Blueprint copies only').check()
    await expect(page).toHaveURL(/is_bpc=true/)
    await expect(rowLinks(page)).toHaveText([
      'Draugur Blueprint',
      'Phoenix Blueprint',
      'Breacher Blueprint',
    ])

    // Collapse the rail. The filter lives in the URL, and the results section is
    // outside the disclosure, so both the URL and the filtered rows persist.
    await filtersButton(page).click()
    await expect(filtersButton(page)).toHaveAttribute('aria-expanded', 'false')
    await expect(page).toHaveURL(/is_bpc=true/)
    await expect(rowLinks(page)).toHaveText([
      'Draugur Blueprint',
      'Phoenix Blueprint',
      'Breacher Blueprint',
    ])
  })

  test('desktop: no disclosure button exists and the filter rail is a permanent column', async ({
    page,
  }) => {
    test.skip(isMobile(), 'above lg the rail is always visible — there is no disclosure to test')
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractList(page, pageOf(SEVEN_SHIPS))

    await page.goto('/contracts')
    await expect(page.getByRole('heading', { level: 1, name: 'Ship Contracts' })).toBeVisible()

    // The Filters button is display:none at/above lg, so it is absent from the
    // accessibility tree entirely.
    await expect(filtersButton(page)).toHaveCount(0)

    // The rail and its controls are usable without any interaction.
    await expect(page.getByRole('complementary', { name: 'Contract filters' })).toBeVisible()
    await expect(page.getByLabel('Ships only')).toBeVisible()
    await expect(page.getByLabel('Ships only')).toBeChecked()
  })

  test('both: a results row link opens the detail view and browser-back returns to the list', async ({
    page,
  }) => {
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractList(page, pageOf(SEVEN_SHIPS))
    await interceptContractDetail(page, (contractId) =>
      makeContract({ contract_id: contractId, items: [makeShipItem('Revelation')] }),
    )

    await page.goto('/contracts')
    await expect(page.getByRole('heading', { level: 1, name: 'Ship Contracts' })).toBeVisible()

    // The first row link (Revelation, contract 232100001) is visible and clickable
    // at both viewports — the table lives outside the collapsible rail.
    const firstRow = rowLinks(page).first()
    await expect(firstRow).toBeVisible()
    await expect(firstRow).toHaveText('Revelation')
    await firstRow.click()

    await expect(page).toHaveURL(/\/contracts\/232100001/)
    await expect(page.getByRole('heading', { level: 1, name: 'Revelation' })).toBeVisible()

    // Browser back restores the list (URL + rows), per PRODUCT principle #2.
    await page.goBack()
    await expect(page).toHaveURL(/\/contracts(\?|$)/)
    await expect(page.getByRole('heading', { level: 1, name: 'Ship Contracts' })).toBeVisible()
    await expect(rowLinks(page)).toHaveText([
      'Revelation',
      'Raven',
      'Maelstrom',
      'Purifier',
      'Hound',
      'Breacher',
      'Minmatar Shuttle',
    ])
  })
})
