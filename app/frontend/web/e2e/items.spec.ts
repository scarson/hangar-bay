import { expect, test } from '@playwright/test'
import {
  makeBpcItem,
  makeContract,
  makeItem,
  makeShipItem,
  pageOf,
  taxonomy,
} from './fixtures/contracts'
import { interceptContractList, interceptCurrentUser, interceptTaxonomy } from './helpers/api'
import { rowLinks } from './helpers/ui'

/**
 * The item-level row surface (Criteria 2.2, 6.1, §8's discriminator).
 *
 * Every cell here is behind the readiness gate, so each test states which side
 * of it the corpus is on. The three blueprint states are the point: exactly one
 * offered copy shows its terms, several show a count and a way to see them, and
 * a contract with none shows nothing at all.
 */

/** Exactly one offered copy — its terms describe the contract without ambiguity. */
const ONE_COPY = makeContract({
  contract_id: 232_700_001,
  is_ship_contract: false,
  items: [makeBpcItem('Draugur Blueprint')],
})

/** Several copies: no single ME/TE describes them, so the row counts instead. */
const THREE_COPIES = makeContract({
  contract_id: 232_700_002,
  title: 'Blueprint lot',
  is_ship_contract: false,
  items: [
    makeBpcItem('Phoenix Blueprint'),
    makeBpcItem('Revelation Blueprint', { runs: 3, material_efficiency: 2, time_efficiency: 0 }),
    makeBpcItem('Moros Blueprint', { runs: 1, material_efficiency: 10, time_efficiency: 20 }),
  ],
})

/** A mixed lot — the case a bare "+N more" says nothing useful about. */
const MIXED_LOT = makeContract({
  contract_id: 232_700_003,
  volume: 120_000,
  items: [
    makeShipItem('Myrmidon'),
    makeItem({ type_name: 'Damage Control II', category: null, category_id: 7, group_id: 60 }),
    makeItem({ type_name: 'Large Shield Extender II', category: null, category_id: 7, group_id: 77 }),
    makeItem({ type_name: 'Warrior II', category: null, category_id: 7, group_id: 100 }),
  ],
})

const CORPUS = [ONE_COPY, THREE_COPIES, MIXED_LOT]

// Every contracts view queries the taxonomy endpoint for the item-level
// readiness signal. Routing it here keeps the fixture lane hermetic; a test
// that needs the surface open registers its own interceptTaxonomy, which wins
// because page.route handlers run last-registered-first.
test.beforeEach(async ({ page }) => {
  await interceptTaxonomy(page)
})

test.describe('blueprint and composition cells', () => {
  test('the three blueprint states each read differently', async ({ page }) => {
    // Runs on BOTH projects: the three columns are never hidden at a
    // breakpoint, because Criterion 2.2 states the display with no exemption
    // and three narrow numeric cells cost less width than one combined one.
    await interceptCurrentUser(page, { status: 401 })
    await interceptTaxonomy(page, taxonomy({ coverage: 'complete' }))
    await interceptContractList(page, pageOf(CORPUS))

    await page.goto('/contracts?ships_only=false')
    for (const label of ['Runs', 'ME', 'TE']) {
      await expect(page.getByRole('columnheader', { name: label, exact: true })).toBeVisible()
    }

    const results = page.getByRole('region', { name: 'Contract results' })
    // One copy: its three figures, each under the column that names it.
    const single = results.getByRole('row', { name: /Draugur Blueprint/ })
    await expect(single.getByRole('cell')).toContainText(['10', '4', '8'])
    // Three copies: a count that leads to them, not one copy's numbers.
    const lot = results.getByRole('link', { name: '3 BPCs' })
    await expect(lot).toBeVisible()
    await expect(lot).toHaveAttribute('href', `/contracts/${THREE_COPIES.contract_id}`)
    // None: nothing at all, rather than a dash that would read as "we looked".
    const noCopies = page.getByRole('row', { name: /Myrmidon/ }).getByRole('cell')
    await expect(noCopies.filter({ hasText: /run|ME |BPC/ })).toHaveCount(0)
  })

  test('the blueprint column is absent while the corpus is still being enriched', async ({
    page,
  }) => {
    // The default taxonomy route reports `partial`. Absent, not blank: mid-
    // resweep the columns would be empty down their whole length.
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractList(page, pageOf(CORPUS))

    await page.goto('/contracts?ships_only=false')
    await expect(rowLinks(page)).toHaveCount(CORPUS.length)

    for (const label of ['Runs', 'ME', 'TE']) {
      await expect(page.getByRole('columnheader', { name: label, exact: true })).toHaveCount(0)
    }
  })

  test('a mixed lot is described by category rather than counted', async ({ page }) => {
    // The breakdown lives in the row's own name cell, which no breakpoint hides.
    await interceptCurrentUser(page, { status: 401 })
    await interceptTaxonomy(page, taxonomy({ coverage: 'complete' }))
    await interceptContractList(page, pageOf(CORPUS))

    await page.goto('/contracts?ships_only=false')

    // Three modules and a hull, plus the lot's volume — enough to judge the
    // bundle without opening it (Criterion 6.1). Counts are item ROWS.
    await expect(page.getByText('3 Modules · 1 Ship · 120,000 m³')).toBeVisible()
    await expect(page.getByText('+3 more')).toHaveCount(0)
  })
})
