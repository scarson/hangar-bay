import { expect, test } from '@playwright/test'
import { BPC_CONTRACTS, SEVEN_SHIPS, bigDataset, pageOf, paginate, taxonomy } from './fixtures/contracts'
import { interceptContractList, interceptCurrentUser, interceptTaxonomy } from './helpers/api'
import { openFiltersIfCollapsed, rowLinks } from './helpers/ui'

/**
 * F002 filter behaviors (search gate, price bounds, region multi-select, the
 * Blueprint-copies toggle, Clear filters, and pagination reset).
 *
 * Every test asserts BOTH the rendered outcome AND the request contract
 * (testing-pitfalls TEST-5): the captured-calls array from the list intercept
 * proves what actually went over the wire, and the fixture responder narrows the
 * visible rows so the render can't drift from the request. All fixtures return
 * non-empty pages so the only "Clear filters" button in the tree is the rail's.
 */

// Every contracts view queries the taxonomy endpoint for the item-level
// readiness signal. Routing it here keeps the fixture lane hermetic; a test
// that needs the surface open registers its own interceptTaxonomy, which wins
// because page.route handlers run last-registered-first.
test.beforeEach(async ({ page }) => {
  await interceptTaxonomy(page)
})

test.describe('contract filters', () => {
  test('search gate: sub-3-char stays in the URL but is never sent; the 3rd char fires it', async ({
    page,
  }) => {
    // filters.ts::toApiQuery gates `search` below MIN_SEARCH_LENGTH (3): a 1–2
    // char value produces the SAME toApiQuery output as empty, so useContracts'
    // query key is unchanged and NO new request fires — the value only lives in
    // the URL while the user is mid-typing.
    await interceptCurrentUser(page, { status: 401 })
    const calls = await interceptContractList(page, (params) =>
      pageOf(params.get('search') === 'abc' ? SEVEN_SHIPS.slice(0, 1) : SEVEN_SHIPS),
    )

    await page.goto('/contracts')
    await expect(rowLinks(page)).toHaveCount(7)
    await openFiltersIfCollapsed(page)

    const searchBox = page.getByLabel('Search', { exact: true })

    // Two characters: the URL carries the value and the input reflects it...
    await searchBox.fill('ab')
    await expect(searchBox).toHaveValue('ab')
    await expect(page).toHaveURL(/[?&]search=ab(&|$)/)
    // ...but no list request has ever carried a `search` param.
    expect(calls.some((c) => c.params.has('search'))).toBe(false)

    // Third character crosses the gate: a request fires with the full value and
    // the rendered rows narrow to the search-matched fixture.
    await searchBox.fill('abc')
    await expect(page).toHaveURL(/[?&]search=abc(&|$)/)
    await expect(rowLinks(page)).toHaveText(['Revelation'])

    const searchCalls = calls.filter((c) => c.params.has('search'))
    expect(searchCalls.length).toBeGreaterThan(0)
    // No call ever carried a shorter-than-3 value, and the first to carry one is 'abc'.
    expect(searchCalls.every((c) => (c.params.get('search') ?? '').length >= 3)).toBe(true)
    expect(searchCalls[0].params.get('search')).toBe('abc')
  })

  test('price bounds: min/max reach the URL and the wire, and the rows update', async ({ page }) => {
    await interceptCurrentUser(page, { status: 401 })
    const priced = SEVEN_SHIPS.slice(2, 5) // Maelstrom, Purifier, Hound
    const calls = await interceptContractList(page, (params) =>
      pageOf(params.has('min_price') || params.has('max_price') ? priced : SEVEN_SHIPS),
    )

    await page.goto('/contracts')
    await expect(rowLinks(page)).toHaveCount(7)
    await openFiltersIfCollapsed(page)

    // sr-only labels, verified in FilterRail.tsx.
    await page.getByLabel('Minimum price').fill('60000000')
    await page.getByLabel('Maximum price').fill('300000000')

    await expect(page).toHaveURL(/[?&]min_price=60000000(&|$)/)
    await expect(page).toHaveURL(/[?&]max_price=300000000(&|$)/)
    await expect(rowLinks(page)).toHaveText(['Maelstrom', 'Purifier', 'Hound'])

    const bounded = calls.find((c) => c.params.get('max_price') === '300000000')
    expect(bounded).toBeDefined()
    expect(bounded!.params.get('min_price')).toBe('60000000')
  })

  test('region multi-select: filter the list, pick two, wire carries repeated region_ids', async ({
    page,
  }) => {
    await interceptCurrentUser(page, { status: 401 })
    const regional = SEVEN_SHIPS.slice(0, 2) // Revelation, Raven
    const calls = await interceptContractList(page, (params) =>
      pageOf(params.has('region_ids') ? regional : SEVEN_SHIPS),
    )

    await page.goto('/contracts')
    await expect(rowLinks(page)).toHaveCount(7)
    await openFiltersIfCollapsed(page)

    // Narrowing the 69-entry region list drops non-matching regions from the DOM.
    await page.getByLabel('Filter region list').fill('de')
    await expect(page.getByLabel('Delve', { exact: true })).toBeVisible()
    await expect(page.getByLabel('Deklein', { exact: true })).toBeVisible()
    await expect(page.getByLabel('The Forge', { exact: true })).toHaveCount(0)

    // Deklein = 10000035, Delve = 10000060 — toggleRegion sorts ids ascending, so
    // the wire order is stable regardless of which box the user ticks first.
    await page.getByLabel('Delve', { exact: true }).check()
    await page.getByLabel('Deklein', { exact: true }).check()

    await expect(page.getByLabel('Delve', { exact: true })).toBeChecked()
    await expect(page.getByLabel('Deklein', { exact: true })).toBeChecked()
    await expect(rowLinks(page)).toHaveText(['Revelation', 'Raven'])
    await expect(page).toHaveURL(/region_ids/)

    const twoRegionCall = calls.filter((c) => c.params.getAll('region_ids').length === 2).at(-1)
    expect(twoRegionCall).toBeDefined()
    // Both values present as repeated keys (testing-pitfalls TEST-5), ascending.
    expect(twoRegionCall!.params.getAll('region_ids')).toEqual(['10000035', '10000060'])
  })

  test('blueprint-copies toggle: is_bpc reaches URL + wire and rows show the BPC badge', async ({
    page,
  }) => {
    await interceptCurrentUser(page, { status: 401 })
    const calls = await interceptContractList(page, (params) =>
      pageOf(params.get('is_bpc') === 'true' ? BPC_CONTRACTS : SEVEN_SHIPS),
    )

    await page.goto('/contracts')
    await expect(rowLinks(page)).toHaveCount(7)
    await openFiltersIfCollapsed(page)

    await page.getByLabel('Blueprint copies only').check()

    await expect(page).toHaveURL(/[?&]is_bpc=true(&|$)/)
    await expect(rowLinks(page)).toHaveCount(BPC_CONTRACTS.length)
    // The copper BPC badge renders once per row, off the row's own
    // is_blueprint_copy_contract flag.
    const results = page.getByRole('region', { name: 'Contract results' })
    await expect(results.getByText('BPC', { exact: true })).toHaveCount(BPC_CONTRACTS.length)

    const last = calls.at(-1)!
    expect(last.params.get('is_bpc')).toBe('true')
  })

  test('blueprint stat windows: an ME bound reaches the URL and the wire', async ({ page }) => {
    // Criterion 2.5. Live production on 2026-08-01 answered min_me=10 with the
    // identical count to no ME filter at all — the control was not merely
    // inert, it returned a large plausible wrong answer. The wire assertion is
    // what would catch that class of regression here.
    await interceptCurrentUser(page, { status: 401 })
    await interceptTaxonomy(page, taxonomy({ coverage: 'complete' }))
    const calls = await interceptContractList(page, (params) =>
      pageOf(params.get('min_me') === '5' ? BPC_CONTRACTS.slice(0, 1) : SEVEN_SHIPS),
    )

    await page.goto('/contracts')
    await expect(rowLinks(page)).toHaveCount(7)
    await openFiltersIfCollapsed(page)

    await page.getByLabel('Minimum material efficiency').fill('5')

    await expect(page).toHaveURL(/[?&]min_me=5(&|$)/)
    await expect(rowLinks(page)).toHaveCount(1)
    await expect.poll(() => calls.some((c) => c.params.get('min_me') === '5')).toBe(true)
  })

  test('clear filters resets the URL + controls and the button removes itself', async ({ page }) => {
    await interceptCurrentUser(page, { status: 401 })
    // The responder narrows to 2 rows whenever a search is sent, so the return to
    // 7 rows after Clear is a deterministic sync point proving the reset re-fetched.
    const calls = await interceptContractList(page, (params) =>
      pageOf(params.has('search') ? SEVEN_SHIPS.slice(0, 2) : SEVEN_SHIPS),
    )

    await page.goto('/contracts')
    await expect(rowLinks(page)).toHaveCount(7)
    await openFiltersIfCollapsed(page)

    // Apply two filters so the (rail-only) Clear button appears.
    await page.getByLabel('Search', { exact: true }).fill('drake')
    await expect(rowLinks(page)).toHaveCount(2)
    await page.getByLabel('Minimum price').fill('1000000')
    await expect(page).toHaveURL(/[?&]search=drake(&|$)/)
    await expect(page).toHaveURL(/[?&]min_price=1000000(&|$)/)

    // The active filters reached the wire before we clear them.
    expect(calls.some((c) => c.params.get('search') === 'drake')).toBe(true)

    // A segment too — it lives above the table rather than in the rail, but
    // Clear filters owns it like every other param, and selecting an item-less
    // one also clears Ships only, so the reset has both to put back.
    await page.getByRole('button', { name: 'Courier' }).click()
    await expect(page).toHaveURL(/contract_type=/)
    await expect(page).toHaveURL(/[?&]ships_only=false(&|$)/)

    const clear = page.getByRole('button', { name: 'Clear filters' })
    await expect(clear).toBeVisible()
    await clear.click()

    // Reset restores the unfiltered set (React Query serves the now-default view
    // from cache, so this is a render sync, not necessarily a fresh request)...
    await expect(rowLinks(page)).toHaveCount(7)
    // ...controls return to defaults...
    await expect(page.getByLabel('Search', { exact: true })).toHaveValue('')
    await expect(page.getByLabel('Minimum price')).toHaveValue('')
    await expect(page.getByLabel('Ships only')).toBeChecked()
    await expect(page.getByLabel('Blueprint copies only')).not.toBeChecked()
    // ...the button removes itself (rendered only while a filter is active)...
    await expect(clear).toHaveCount(0)
    // ...and the URL is exactly the default filter state: every default param is
    // present and no filter param lingers (the URL is what drives toApiQuery).
    await expect(page).toHaveURL(/[?&]ships_only=true(&|$)/)
    await expect(page).toHaveURL(/[?&]page=1(&|$)/)
    await expect(page).toHaveURL(/[?&]size=50(&|$)/)
    // Time left, not Issued: the courier detour above reconciled the sort to a
    // field the courier set can disclose (its header showed it, aria-sort and
    // all), and Clear preserves the current sort — sort is not a filter. Had
    // the flow never entered a segment, the default Issued sort would survive
    // untouched instead.
    await expect(page).toHaveURL(/[?&]sort_by=date_expired(&|$)/)
    await expect(page).toHaveURL(/[?&]sort_direction=desc(&|$)/)
    await expect(page).not.toHaveURL(/search=/)
    await expect(page).not.toHaveURL(/min_price=/)
    await expect(page).not.toHaveURL(/max_price=/)
    await expect(page).not.toHaveURL(/region_ids=/)
    await expect(page).not.toHaveURL(/is_bpc=/)
    // Every filter param the URL layer parses, whether or not this test set it:
    // Clear filters rebuilds the search from scratch, so a param that survives
    // it is one resetFilters forgot to drop.
    await expect(page).not.toHaveURL(/contract_type=/)
    await expect(page).not.toHaveURL(/category_id=/)
    await expect(page).not.toHaveURL(/group_id=/)
    for (const bound of ['runs', 'me', 'te']) {
      await expect(page).not.toHaveURL(new RegExp(`min_${bound}=`))
      await expect(page).not.toHaveURL(new RegExp(`max_${bound}=`))
    }
  })

  test('applying a filter resets pagination to page 1', async ({ page }) => {
    await interceptCurrentUser(page, { status: 401 })
    const all = bigDataset(60)
    const calls = await interceptContractList(page, (params) =>
      paginate(all, Number(params.get('page') ?? 1), Number(params.get('size') ?? 50)),
    )

    await page.goto('/contracts?page=2&size=50')
    // Page 2 of a 60-row, 50-per-page set = the final 10 rows.
    await expect(rowLinks(page)).toHaveCount(10)
    await expect(page.getByText(/Page 2 of 2/)).toBeVisible()
    await openFiltersIfCollapsed(page)

    // ContractsPage.update() folds page:1 into every filter patch.
    await page.getByLabel('Minimum price').fill('5000000')

    await expect(page.getByText(/Page 1 of 2/)).toBeVisible()
    await expect(page).toHaveURL(/[?&]page=1(&|$)/)

    const filtered = calls.find((c) => c.params.get('min_price') === '5000000')
    expect(filtered).toBeDefined()
    expect(filtered!.params.get('page')).toBe('1')
  })
})
