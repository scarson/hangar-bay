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
  const isMobile = () => test.info().project.name === 'mobile'

  test('the three blueprint states each read differently', async ({ page }) => {
    test.skip(
      isMobile(),
      'the Blueprint column hides below lg, where the detail page carries the terms instead (asserted by the mobile test below)',
    )
    await interceptCurrentUser(page, { status: 401 })
    await interceptTaxonomy(page, taxonomy({ coverage: 'complete' }))
    await interceptContractList(page, pageOf(CORPUS))

    await page.goto('/contracts?ships_only=false')
    await expect(page.getByRole('columnheader', { name: 'Blueprint' })).toBeVisible()

    const results = page.getByRole('region', { name: 'Contract results' })
    // One copy: its terms, each figure named so none needs a legend.
    await expect(results.getByText('10 runs · ME 4 · TE 8')).toBeVisible()
    // Three copies: a count that leads to them, not one copy's numbers.
    const lot = results.getByRole('link', { name: '3 BPCs' })
    await expect(lot).toBeVisible()
    await expect(lot).toHaveAttribute('href', `/contracts/${THREE_COPIES.contract_id}`)
    // None: nothing at all, rather than a dash that would read as "we looked".
    const noCopies = page.getByRole('row', { name: /Myrmidon/ }).getByRole('cell')
    await expect(noCopies.filter({ hasText: /run|ME |BPC/ })).toHaveCount(0)
  })

  test('below lg the blueprint column gives way rather than crowding the row', async ({ page }) => {
    // The seam itself, so the desktop skip above is not the only word on it:
    // the column is genuinely absent at this width, and the row's own link is
    // still the way to the terms.
    test.skip(!isMobile(), 'the Blueprint column is shown at and above lg')
    await interceptCurrentUser(page, { status: 401 })
    await interceptTaxonomy(page, taxonomy({ coverage: 'complete' }))
    await interceptContractList(page, pageOf(CORPUS))

    await page.goto('/contracts?ships_only=false')
    await expect(rowLinks(page)).toHaveCount(CORPUS.length)

    // Hidden by a breakpoint rule, so the cells are still in the DOM but out of
    // the accessibility tree and off the screen — unlike the enrichment gate
    // below, which does not render them at all.
    await expect(page.getByRole('columnheader', { name: 'Blueprint' })).toHaveCount(0)
    await expect(page.getByText('10 runs · ME 4 · TE 8')).toBeHidden()
  })

  test('the blueprint column is absent while the corpus is still being enriched', async ({
    page,
  }) => {
    // The default taxonomy route reports `partial`. Absent, not blank: mid-
    // resweep the column would be empty down its whole length. This holds at
    // every width, so it runs on both projects.
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractList(page, pageOf(CORPUS))

    await page.goto('/contracts?ships_only=false')
    await expect(rowLinks(page)).toHaveCount(CORPUS.length)

    await expect(page.getByRole('columnheader', { name: 'Blueprint' })).toHaveCount(0)
    await expect(page.getByText('10 runs · ME 4 · TE 8')).toHaveCount(0)
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
