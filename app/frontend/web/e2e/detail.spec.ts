import { expect, test } from '@playwright/test'
import { makeBpcItem, makeContract, makeShipItem, pageOf } from './fixtures/contracts'
import {
  failUnexpectedApiCalls,
  interceptContractDetail,
  interceptContractList,
  interceptCurrentUser,
} from './helpers/api'
import { rowLinks } from './helpers/ui'

/**
 * F003 contract detail view + the back-navigation seam (PRODUCT principle #2:
 * the URL is the interface). Fixture lane only — every list/detail call is
 * intercepted, so assertions never depend on the wiped-and-reingested dev DB.
 */

const CONTRACT_ID = 232_500_001
const HULL = 'Maelstrom'

/**
 * One contract carrying BOTH a ship item and a blueprint-copy item, so the
 * Contents list exercises the SHIP badge and the BPC badge in a single fixture.
 * Fresh items each call (record_id auto-increments) keep list keys unique.
 */
function detailContract() {
  return makeContract({
    contract_id: CONTRACT_ID,
    price: 1_750_000_000,
    type: 'item_exchange',
    items: [makeShipItem(HULL), makeBpcItem('Raven Blueprint')],
  })
}

test.describe('contract detail (F003)', () => {
  test('row click opens the detail view with hull, badges, sections, items, and priced ISK', async ({
    page,
  }) => {
    const contract = detailContract()
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractList(page, pageOf([contract]))
    const detailCalls = await interceptContractDetail(page, contract)

    await page.goto('/contracts')
    await expect(rowLinks(page)).toHaveText([HULL])

    await rowLinks(page).first().click()

    // Route param → detail URL (no trailing slash on the detail endpoint).
    await expect(page).toHaveURL(new RegExp(`/contracts/${CONTRACT_ID}$`))
    await expect(page.getByRole('heading', { level: 1, name: HULL })).toBeVisible()

    // Type badge (item_exchange → "Exchange"; Badge only uppercases via CSS,
    // the DOM text is title-case).
    await expect(page.getByText('Exchange', { exact: true })).toBeVisible()

    // The three definition sections are aria-labelledby regions.
    await expect(page.getByRole('region', { name: 'Economics' })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Identification' })).toBeVisible()
    const contents = page.getByRole('region', { name: /Contents/ })
    await expect(contents).toBeVisible()

    // Ship item shows the SHIP badge, the BPC item shows the BPC badge — scoped
    // to Contents so the header's own BPC badge doesn't stand in for the row's.
    await expect(contents.getByText('Ship', { exact: true })).toBeVisible()
    await expect(contents.getByText('BPC', { exact: true })).toBeVisible()

    // Price renders with grouping separators and a trailing " ISK".
    await expect(page.getByRole('region', { name: 'Economics' }).getByText('1,750,000,000 ISK')).toBeVisible()

    // TEST-5: assert the wire path too, not just the render.
    expect(detailCalls.some((call) => call.url.pathname === `/api/v1/contracts/${CONTRACT_ID}`)).toBe(
      true,
    )
  })

  test('history back from a filtered list restores the URL search state (button control)', async ({
    page,
  }) => {
    const contract = detailContract()
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractList(page, pageOf([contract]))
    await interceptContractDetail(page, contract)

    await page.goto('/contracts?min_price=5000000')
    await expect(rowLinks(page)).toHaveText([HULL])

    await rowLinks(page).first().click()
    await expect(page.getByRole('heading', { level: 1, name: HULL })).toBeVisible()

    // With the list behind us in this tab's history, the control is a BUTTON
    // (router.history.back()), NOT a plain link — verify exact text.
    const backButton = page.getByRole('button', { name: '← All contracts', exact: true })
    await expect(backButton).toBeVisible()
    expect(await page.getByRole('link', { name: '← All contracts', exact: true }).count()).toBe(0)

    await backButton.click()

    // Back on the list with the prior filter intact and rows re-rendered.
    await expect(page).toHaveURL(/min_price=5000000/)
    await expect(rowLinks(page)).toHaveText([HULL])
  })

  test('cold deep link renders fully and the back control is a link to the list', async ({ page }) => {
    // Prove ONLY the detail endpoint is hit on a cold load: abort anything else —
    // except the header's own /me, which is expected on every page and answered
    // 401 by the intercept registered below (page.route runs last-registered-first,
    // so the more specific /me intercept must come AFTER this catch-all to win).
    await failUnexpectedApiCalls(page)
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractDetail(page, detailContract())

    await page.goto(`/contracts/${CONTRACT_ID}`)

    await expect(page.getByRole('heading', { level: 1, name: HULL })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Economics' })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Identification' })).toBeVisible()
    await expect(page.getByRole('region', { name: /Contents/ })).toBeVisible()

    // No in-app history → the control is a LINK to the default list, not a button.
    const backLink = page.getByRole('link', { name: '← All contracts', exact: true })
    await expect(backLink).toBeVisible()
    await expect(backLink).toHaveAttribute('href', '/contracts')
    expect(await page.getByRole('button', { name: '← All contracts', exact: true }).count()).toBe(0)
  })

  test('404 shows the not-found heading and the back control still returns to the list', async ({
    page,
  }) => {
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractList(page, pageOf([detailContract()]))
    await interceptContractDetail(page, { status: 404 })

    await page.goto('/contracts/424242')

    await expect(page.getByRole('heading', { level: 1, name: 'Contract not found.' })).toBeVisible()

    // Cold deep link → back control is a link; clicking it lands on the list.
    await page.getByRole('link', { name: '← All contracts', exact: true }).click()
    await expect(page).toHaveURL(/\/contracts(\?|$)/)
    await expect(page.getByRole('heading', { level: 1, name: 'Ship Contracts' })).toBeVisible()
  })

  test('document title becomes "<hull> — Hangar Bay"', async ({ page }) => {
    // Same last-registered-first ordering as the cold-deep-link test above: the
    // catch-all must be registered before the /me intercept so the specific
    // route still wins.
    await failUnexpectedApiCalls(page)
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractDetail(page, detailContract())

    await page.goto(`/contracts/${CONTRACT_ID}`)

    await expect(page.getByRole('heading', { level: 1, name: HULL })).toBeVisible()
    await expect(page).toHaveTitle(`${HULL} — Hangar Bay`)
  })
})
