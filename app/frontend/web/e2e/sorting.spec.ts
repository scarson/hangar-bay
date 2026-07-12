import { expect, test } from '@playwright/test'
import { makeContract, makeShipItem, paginate, type WireContract } from './fixtures/contracts'
import { interceptContractList, type ListResponder } from './helpers/api'
import { rowLinks } from './helpers/ui'

/**
 * F002 Criterion 7: column-header sorting. The sortable table headers
 * (ContractTable.tsx COLUMNS) map to API sort fields —
 *   'Ship / Contract' → ship_name, 'Price (ISK)' → price,
 *   'Time left' → date_expired, 'Issued' → date_issued —
 * and the active header carries aria-sort ('ascending' | 'descending').
 * A new field starts in ContractsPage's DEFAULT_DIRECTION (date_issued: desc,
 * everything used here: asc); re-clicking the active field flips it.
 *
 * The frontend never sorts client-side — handleSort only navigates and the
 * table renders whatever order the response returns. To prove that, the
 * fixture serves each (sort_by, sort_direction) as a genuinely re-ordered page
 * (strictly-ordered, all-distinct keys — testing-pitfalls TEST-3) and every
 * test asserts the rendered row order matches THE RESPONSE, plus the request
 * URL that produced it (TEST-5). All four orderings below are mutually
 * distinct, so no row-order assertion can pass on a stale render.
 */

// Five ship contracts with distinct hull names, prices, and issued dates,
// chosen so date_issued-desc, price-asc, price-desc, and ship_name-asc are all
// different permutations.
const SHIPS: { name: string; price: number; issued: string; expired: string }[] = [
  { name: 'Nyx', price: 5_000_000_000, issued: '2026-06-05T05:00:00Z', expired: '2026-07-05T05:00:00Z' },
  { name: 'Rifter', price: 10_000_000, issued: '2026-06-01T01:00:00Z', expired: '2026-07-09T09:00:00Z' },
  { name: 'Thorax', price: 250_000_000, issued: '2026-06-03T03:00:00Z', expired: '2026-07-07T07:00:00Z' },
  { name: 'Osprey', price: 90_000_000, issued: '2026-06-04T04:00:00Z', expired: '2026-07-08T08:00:00Z' },
  { name: 'Vexor', price: 400_000_000, issued: '2026-06-02T02:00:00Z', expired: '2026-07-06T06:00:00Z' },
]

const byName: Record<string, WireContract> = Object.fromEntries(
  SHIPS.map((s, i) => [
    s.name,
    makeContract({
      contract_id: 232_500_001 + i,
      price: s.price,
      date_issued: s.issued,
      date_expired: s.expired,
      items: [makeShipItem(s.name)],
    }),
  ]),
)

/**
 * The order the backend would return for a given (sort_by, sort_direction) —
 * the single source of truth for both the fixture responder and every expected
 * row-order assertion, so the two can never drift.
 */
function sortedNames(sortBy: string | null, direction: string | null): string[] {
  const factor = direction === 'asc' ? 1 : -1
  const shipName = (c: WireContract) => c.items[0]?.type_name ?? ''
  return [...SHIPS.map((s) => s.name)].sort((a, b) => {
    const ca = byName[a]
    const cb = byName[b]
    let delta: number
    switch (sortBy) {
      case 'price':
        delta = ca.price - cb.price
        break
      case 'ship_name':
        delta = shipName(ca).localeCompare(shipName(cb))
        break
      case 'date_expired':
        delta = ca.date_expired.localeCompare(cb.date_expired)
        break
      default:
        delta = ca.date_issued.localeCompare(cb.date_issued)
    }
    return delta * factor
  })
}

// Serve the page the backend would for the requested sort + pagination.
const listResponder: ListResponder = (params) => {
  const page = Number(params.get('page') ?? '1')
  const size = Number(params.get('size') ?? '50')
  const ordered = sortedNames(params.get('sort_by'), params.get('sort_direction')).map((n) => byName[n])
  return paginate(ordered, page, size)
}

const shipsHeading = (page: import('@playwright/test').Page) =>
  page.getByRole('heading', { level: 1, name: 'Ship Contracts' })

// Exactly one header is sorted at a time; target it by attribute so the
// assertion is viewport-agnostic — the Issued column is `max-sm:hidden`, so on
// the mobile project (Pixel 7, 412px) its <th> is display:none and absent from
// the accessibility tree, but the aria-sort DOM state is still assertable here.
const activeSortHeader = (page: import('@playwright/test').Page) => page.locator('thead th[aria-sort]')

test.describe('column-header sorting', () => {
  test('default sort is Issued descending on the wire and in the header', async ({ page }) => {
    const calls = await interceptContractList(page, listResponder)

    await page.goto('/contracts')
    await expect(shipsHeading(page)).toBeVisible()

    // Server order (date_issued desc) is what renders.
    await expect(rowLinks(page)).toHaveText(sortedNames('date_issued', 'desc'))

    // Exactly one active header, and it's Issued, descending.
    await expect(activeSortHeader(page)).toHaveCount(1)
    await expect(activeSortHeader(page)).toHaveAttribute('aria-sort', 'descending')
    await expect(activeSortHeader(page)).toContainText('Issued')

    await expect(page).toHaveURL(/sort_by=date_issued/)
    await expect(page).toHaveURL(/sort_direction=desc/)

    const first = calls[0]
    expect(first.url.pathname).toBe('/api/v1/contracts/')
    expect(first.params.get('sort_by')).toBe('date_issued')
    expect(first.params.get('sort_direction')).toBe('desc')
  })

  test('clicking Price (ISK) sorts price ascending, resets to page 1, renders server order', async ({
    page,
  }) => {
    const calls = await interceptContractList(page, listResponder)

    // Start on page 2 so the reset-to-1 on sort is observable (5 items / size 3
    // → 2 pages; page 2 is valid, no out-of-range redirect).
    await page.goto('/contracts?page=2&size=3')
    await expect(shipsHeading(page)).toBeVisible()
    await expect(rowLinks(page)).toHaveText(sortedNames('date_issued', 'desc').slice(3))

    await page.getByRole('button', { name: 'Price (ISK)' }).click()

    // Page reset to 1 → price-asc page 1 (size 3). The rows follow the response.
    await expect(rowLinks(page)).toHaveText(sortedNames('price', 'asc').slice(0, 3))

    // aria-sort moved to Price (and left Issued: still exactly one active header).
    await expect(activeSortHeader(page)).toHaveCount(1)
    await expect(activeSortHeader(page)).toContainText('Price (ISK)')
    await expect(page.getByRole('columnheader', { name: 'Price (ISK)' })).toHaveAttribute(
      'aria-sort',
      'ascending',
    )

    await expect(page).toHaveURL(/sort_by=price/)
    await expect(page).toHaveURL(/sort_direction=asc/)
    await expect(page).toHaveURL(/[?&]page=1(&|$)/)

    const priceCall = calls.filter((c) => c.params.get('sort_by') === 'price').at(-1)
    expect(priceCall).toBeDefined()
    expect(priceCall!.params.get('sort_by')).toBe('price')
    expect(priceCall!.params.get('sort_direction')).toBe('asc')
    expect(priceCall!.params.get('page')).toBe('1')
  })

  test('re-clicking Price flips the direction asc↔desc everywhere', async ({ page }) => {
    const calls = await interceptContractList(page, listResponder)

    await page.goto('/contracts')
    await expect(shipsHeading(page)).toBeVisible()
    await expect(rowLinks(page)).toHaveText(sortedNames('date_issued', 'desc'))

    // First click: price ascending (DEFAULT_DIRECTION.price).
    await page.getByRole('button', { name: 'Price (ISK)' }).click()
    await expect(rowLinks(page)).toHaveText(sortedNames('price', 'asc'))
    await expect(page.getByRole('columnheader', { name: 'Price (ISK)' })).toHaveAttribute(
      'aria-sort',
      'ascending',
    )
    await expect(page).toHaveURL(/sort_direction=asc/)

    // Second click on the same field: flip to descending.
    await page.getByRole('button', { name: 'Price (ISK)' }).click()
    await expect(rowLinks(page)).toHaveText(sortedNames('price', 'desc'))
    await expect(page.getByRole('columnheader', { name: 'Price (ISK)' })).toHaveAttribute(
      'aria-sort',
      'descending',
    )
    await expect(page).toHaveURL(/sort_by=price/)
    await expect(page).toHaveURL(/sort_direction=desc/)

    const priceDescCall = calls
      .filter((c) => c.params.get('sort_by') === 'price' && c.params.get('sort_direction') === 'desc')
      .at(-1)
    expect(priceDescCall).toBeDefined()
    expect(priceDescCall!.params.get('sort_by')).toBe('price')
    expect(priceDescCall!.params.get('sort_direction')).toBe('desc')
  })

  test('switching to a different header resets direction to that column initial', async ({ page }) => {
    const calls = await interceptContractList(page, listResponder)

    // Deep-link into price DESCENDING so the reset is unmistakable: switching
    // columns must NOT carry desc — ship_name starts at its own initial (asc).
    await page.goto('/contracts?sort_by=price&sort_direction=desc')
    await expect(shipsHeading(page)).toBeVisible()
    await expect(rowLinks(page)).toHaveText(sortedNames('price', 'desc'))
    await expect(page.getByRole('columnheader', { name: 'Price (ISK)' })).toHaveAttribute(
      'aria-sort',
      'descending',
    )

    await page.getByRole('button', { name: 'Ship / Contract' }).click()

    // ship_name's initial direction is ascending, not the inherited desc.
    await expect(rowLinks(page)).toHaveText(sortedNames('ship_name', 'asc'))
    await expect(activeSortHeader(page)).toHaveCount(1)
    await expect(page.getByRole('columnheader', { name: 'Ship / Contract' })).toHaveAttribute(
      'aria-sort',
      'ascending',
    )
    await expect(page).toHaveURL(/sort_by=ship_name/)
    await expect(page).toHaveURL(/sort_direction=asc/)

    const shipCall = calls.filter((c) => c.params.get('sort_by') === 'ship_name').at(-1)
    expect(shipCall).toBeDefined()
    expect(shipCall!.params.get('sort_direction')).toBe('asc')
    expect(shipCall!.params.get('page')).toBe('1')
  })

  test('deep-link restores the sorted header and sends the params on first load', async ({ page }) => {
    const calls = await interceptContractList(page, listResponder)

    await page.goto('/contracts?sort_by=price&sort_direction=asc')
    await expect(shipsHeading(page)).toBeVisible()

    await expect(rowLinks(page)).toHaveText(sortedNames('price', 'asc'))
    await expect(activeSortHeader(page)).toHaveCount(1)
    await expect(page.getByRole('columnheader', { name: 'Price (ISK)' })).toHaveAttribute(
      'aria-sort',
      'ascending',
    )

    // The very first request carries the deep-linked sort (and the ships-only default).
    const first = calls[0]
    expect(first.url.pathname).toBe('/api/v1/contracts/')
    expect(first.params.get('sort_by')).toBe('price')
    expect(first.params.get('sort_direction')).toBe('asc')
    expect(first.params.get('is_ship_contract')).toBe('true')
  })
})
