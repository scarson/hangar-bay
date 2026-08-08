import { expect, test } from '@playwright/test'
import {
  makeBpcItem,
  makeContract,
  makeContractDetail,
  makeItem,
  makeShipItem,
  pageOf,
} from './fixtures/contracts'
import {
  failUnexpectedApiCalls,
  interceptContractDetail,
  interceptContractList,
  interceptCurrentUser,
  interceptTaxonomy,
} from './helpers/api'
import { rowLinks } from './helpers/ui'

/**
 * F003 contract detail view + the back-navigation seam (PRODUCT principle #2:
 * the URL is the interface). Fixture lane only — every list/detail call is
 * intercepted, so assertions never depend on the wiped-and-reingested dev DB.
 */

const CONTRACT_ID = 232_500_001
const HULL = 'Maelstrom'

const CONTRACT_FIELDS = {
  contract_id: CONTRACT_ID,
  price: 1_750_000_000,
  type: 'item_exchange' as const,
}

/**
 * One contract carrying BOTH a ship item and a blueprint-copy item, so the
 * offered list exercises the SHIP badge and the BPC badge in a single fixture.
 * Fresh items each call (record_id auto-increments) keep list keys unique.
 */
function detailContract() {
  return makeContractDetail({
    ...CONTRACT_FIELDS,
    items: [makeShipItem(HULL), makeBpcItem('Raven Blueprint')],
  })
}

/**
 * The same contract as a list row — same item inputs, so the derived label
 * matches the detail heading, and no item array (the list serves none).
 */
function listRow() {
  return makeContract({
    ...CONTRACT_FIELDS,
    items: [makeShipItem(HULL), makeBpcItem('Raven Blueprint')],
  })
}


// Every contracts view queries the taxonomy endpoint for the item-level
// readiness signal. Routing it here keeps the fixture lane hermetic; a test
// that needs the surface open registers its own interceptTaxonomy, which wins
// because page.route handlers run last-registered-first.
test.beforeEach(async ({ page }) => {
  await interceptTaxonomy(page)
})

test.describe('contract detail (F003)', () => {
  test('row click opens the detail view with hull, badges, sections, items, and priced ISK', async ({
    page,
  }) => {
    const contract = detailContract()
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractList(page, pageOf([listRow()]))
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
    // The items region is named for the side of the trade it holds now
    // (Criterion 8.1); this fixture offers both its items and asks for nothing.
    const offered = page.getByRole('region', { name: /^Offered/ })
    await expect(offered).toBeVisible()
    await expect(page.getByRole('region', { name: /^Requested/ })).toHaveCount(0)

    // Ship item shows the SHIP badge, the BPC item shows the BPC badge — scoped
    // to the offered side so the header's own BPC badge doesn't stand in for
    // the row's.
    await expect(offered.getByText('Ship', { exact: true })).toBeVisible()
    await expect(offered.getByText('BPC', { exact: true })).toBeVisible()

    // Price renders with grouping separators and a trailing " ISK".
    await expect(page.getByRole('region', { name: 'Economics' }).getByText('1,750,000,000 ISK')).toBeVisible()

    // Criterion 7.1: when ingestion last saw this contract still listed. The
    // fixture stamps eleven minutes back off the live clock (TEST-17).
    const identification = page.getByRole('region', { name: 'Identification' })
    await expect(identification.getByText('Last seen', { exact: true })).toBeVisible()
    await expect(identification.getByText('11m ago', { exact: true })).toBeVisible()

    // TEST-5: assert the wire path too, not just the render.
    expect(detailCalls.some((call) => call.url.pathname === `/api/v1/contracts/${CONTRACT_ID}`)).toBe(
      true,
    )
  })

  test('history back from a filtered list restores the URL search state (button control)', async ({
    page,
  }) => {
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractList(page, pageOf([listRow()]))
    await interceptContractDetail(page, detailContract())

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
    await expect(page.getByRole('region', { name: /^Offered/ })).toBeVisible()

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
    await interceptContractList(page, pageOf([listRow()]))
    await interceptContractDetail(page, { status: 404 })

    await page.goto('/contracts/424242')

    await expect(page.getByRole('heading', { level: 1, name: 'Contract not found.' })).toBeVisible()

    // Cold deep link → back control is a link; clicking it lands on the list.
    await page.getByRole('link', { name: '← All contracts', exact: true }).click()
    await expect(page).toHaveURL(/\/contracts(\?|$)/)
    await expect(page.getByRole('heading', { level: 1, name: 'Ship Contracts' })).toBeVisible()
  })

  test('a want-to-buy contract keeps the two sides of the trade apart', async ({ page }) => {
    // Criterion 8.1. Merged into one list, a want-to-buy contract reads as a
    // sale of the very thing it is asking to buy — and the offered side of this
    // one is empty, so a merged list would have shown nothing but the request.
    const wtb = makeContractDetail({
      contract_id: 232_800_001,
      title: 'WTB Tritanium',
      price: 0,
      items: [
        makeItem({ type_name: 'Tritanium', category: null, category_id: 4, quantity: 1_000_000, is_included: false }),
      ],
    })
    await failUnexpectedApiCalls(page)
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractDetail(page, wtb)

    await page.goto(`/contracts/${wtb.contract_id}`)

    const requested = page.getByRole('region', { name: /^Requested/ })
    await expect(requested.getByText(/Tritanium/)).toBeVisible()
    await expect(page.getByRole('region', { name: /^Offered/ })).toHaveCount(0)
  })

  test('each offered copy carries its own terms, which is what the row’s count promises', async ({
    page,
  }) => {
    // The list renders "N BPCs" as a link here rather than one arbitrary
    // blueprint's numbers; this page is where the reader collects them.
    const lot = makeContractDetail({
      contract_id: 232_800_002,
      title: 'Blueprint lot',
      items: [
        makeBpcItem('Phoenix Blueprint'),
        makeBpcItem('Moros Blueprint', { runs: 3, material_efficiency: 2, time_efficiency: 0 }),
      ],
    })
    await failUnexpectedApiCalls(page)
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractDetail(page, lot)

    await page.goto(`/contracts/${lot.contract_id}`)

    const offered = page.getByRole('region', { name: /^Offered/ })
    await expect(offered.getByText('10 runs · ME 4 · TE 8')).toBeVisible()
    await expect(offered.getByText('3 runs · ME 2 · TE 0')).toBeVisible()
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
