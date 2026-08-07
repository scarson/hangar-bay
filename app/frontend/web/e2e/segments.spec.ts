import { expect, test, type Page } from '@playwright/test'
import {
  AUCTION_CONTRACTS,
  COURIER_CONTRACTS,
  SEVEN_SHIPS,
  countByType,
  pageOf,
} from './fixtures/contracts'
import { interceptContractList, interceptCurrentUser } from './helpers/api'
import { openFiltersIfCollapsed, rowLinks } from './helpers/ui'

/**
 * F008 contract-type segmentation (Criteria 1.3–1.9).
 *
 * Every test asserts BOTH the rendered outcome AND the request contract
 * (testing-pitfalls TEST-5). The responder keys off `contract_type` so the rows
 * can't drift from the request, and serves the SAME per-type counts whatever
 * segment is asked for — which is what the server does: counts are computed
 * with the contract_type predicate lifted and, for the item-less types, with
 * ships-only lifted too (Criterion 1.8), so they describe the whole population
 * rather than the page.
 */
const CORPUS = [...SEVEN_SHIPS, ...AUCTION_CONTRACTS, ...COURIER_CONTRACTS]
/** 7 item_exchange, 3 auction, 3 courier, 0 loan, 0 unknown. */
const SEGMENT_COUNTS = countByType(CORPUS)

/** All while ships-only is on: the item-bearing types only (7 + 3). */
const ALL_SHIPS_ONLY = 10
/** All once widened: every type (7 + 3 + 3). */
const ALL_WIDENED = 13

function respond(params: URLSearchParams) {
  const type = params.get('contract_type')
  const rows =
    type === 'courier'
      ? COURIER_CONTRACTS
      : type === 'auction'
        ? AUCTION_CONTRACTS
        : type === 'item_exchange'
          ? SEVEN_SHIPS
          : params.get('is_ship_contract') === 'true'
            ? SEVEN_SHIPS
            : CORPUS
  return pageOf(rows, { segment_counts: SEGMENT_COUNTS })
}

const segment = (page: Page, name: string) => page.getByRole('button', { name, exact: true })

test.describe('contract-type segments', () => {
  test('the default view offers one control per browsable type, with honest counts', async ({
    page,
  }) => {
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractList(page, respond)

    await page.goto('/contracts')
    await expect(rowLinks(page)).toHaveCount(7)

    // All is selected and counts only what the ships-only view can show.
    await expect(segment(page, `All ${ALL_SHIPS_ONLY}`)).toHaveAttribute('aria-pressed', 'true')
    await expect(segment(page, 'Item exchange 7')).toBeVisible()
    await expect(segment(page, 'Auction 3')).toBeVisible()
    // Criterion 1.8: the courier count is its true total, not the 0 the
    // ships-only view would return — the label must not flip on click.
    await expect(segment(page, 'Courier 3')).toHaveAttribute('aria-pressed', 'false')
    // Criterion 1.1: loan and unknown are counted but get no control.
    await expect(page.getByRole('button', { name: /^Loan/ })).toHaveCount(0)
    await expect(page.getByRole('button', { name: /^Unknown/ })).toHaveCount(0)
  })

  test('selecting Courier clears Ships only visibly and asks the API for couriers', async ({
    page,
  }) => {
    await interceptCurrentUser(page, { status: 401 })
    const calls = await interceptContractList(page, respond)

    await page.goto('/contracts')
    await expect(rowLinks(page)).toHaveCount(7)

    await segment(page, 'Courier 3').click()

    // Criterion 1.4: the selection reaches the URL, together with the cleared
    // ships-only that Criterion 1.7 requires — one navigation, both halves. An
    // array param goes in as TanStack Router's JSON form, the same shape
    // region_ids has always used, so assert the decoded value and then prove it
    // restores (below) rather than pinning an encoding.
    await expect(page).toHaveURL(/contract_type=/)
    await expect(page).toHaveURL(/[?&]ships_only=false(&|$)/)
    expect(new URL(page.url()).searchParams.get('contract_type')).toBe('["courier"]')
    await expect(page.getByRole('heading', { level: 1, name: 'Courier Contracts' })).toBeVisible()
    await expect(rowLinks(page)).toHaveCount(COURIER_CONTRACTS.length)
    await expect(segment(page, 'Courier 3')).toHaveAttribute('aria-pressed', 'true')

    // The checkbox visibly reflects the clearing rather than contradicting it.
    await openFiltersIfCollapsed(page)
    await expect(page.getByLabel('Ships only')).not.toBeChecked()

    const last = calls.at(-1)!
    expect(last.url.pathname).toBe('/api/v1/contracts/')
    expect(last.params.getAll('contract_type')).toEqual(['courier'])
    expect(last.params.has('is_ship_contract')).toBe(false)

    // The URL the app itself wrote is shareable: reloading it restores the
    // segment and the rows, with no in-app state left over to carry it.
    await page.reload()
    await expect(rowLinks(page)).toHaveCount(COURIER_CONTRACTS.length)
    await expect(segment(page, 'Courier 3')).toHaveAttribute('aria-pressed', 'true')
  })

  test('returning to All restores the ships-only default and drops both params', async ({
    page,
  }) => {
    await interceptCurrentUser(page, { status: 401 })
    const calls = await interceptContractList(page, respond)

    await page.goto('/contracts?contract_type=courier&ships_only=false')
    await expect(rowLinks(page)).toHaveCount(COURIER_CONTRACTS.length)

    await segment(page, `All ${ALL_SHIPS_ONLY}`).click()

    // Criterion 1.9: the patch removes ships_only rather than setting it true,
    // and validateSearch re-derives the default on the way into the URL — the
    // same shape Clear filters produces. The cleared `false` must not survive.
    await expect(page).not.toHaveURL(/contract_type=/)
    await expect(page).not.toHaveURL(/ships_only=false/)
    await expect(page).toHaveURL(/[?&]ships_only=true(&|$)/)
    await expect(page.getByRole('heading', { level: 1, name: 'Ship Contracts' })).toBeVisible()
    await expect(rowLinks(page)).toHaveCount(7)

    await openFiltersIfCollapsed(page)
    await expect(page.getByLabel('Ships only')).toBeChecked()

    const last = calls.at(-1)!
    expect(last.params.get('is_ship_contract')).toBe('true')
    expect(last.params.has('contract_type')).toBe(false)
  })

  test('All counts every type once the view is already widened', async ({ page }) => {
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractList(page, respond)

    // ships_only=false with no segment selected: the item-less types are part of
    // what All renders, so they are part of what it claims.
    await page.goto('/contracts?ships_only=false')
    await expect(rowLinks(page)).toHaveCount(CORPUS.length)

    await expect(segment(page, `All ${ALL_WIDENED}`)).toHaveAttribute('aria-pressed', 'true')
    await expect(segment(page, 'Courier 3')).toBeVisible()
  })

  test('the auction segment splits the price into a starting bid and a buyout', async ({ page }) => {
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractList(page, respond)

    await page.goto('/contracts?contract_type=auction')
    await expect(rowLinks(page)).toHaveCount(AUCTION_CONTRACTS.length)

    // Criterion 4.2: a bid is not a price, and a buyout is neither. The type
    // badge goes with the split — every row here is an auction already.
    await expect(page.getByRole('columnheader', { name: 'Starting bid', exact: true })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Buyout', exact: true })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Price (ISK)', exact: true })).toHaveCount(0)
    await expect(page.getByRole('columnheader', { name: 'Type', exact: true })).toHaveCount(0)

    await expect(page.getByText('1,900,000,000', { exact: true })).toBeVisible()
    await expect(page.getByText('2,600,000,000', { exact: true })).toBeVisible()
    // Criterion 4.3: the auction whose seller set no buyout says so in words.
    await expect(page.getByText('No buyout', { exact: true })).toBeVisible()
  })

  test('the courier segment shows the route and the reward per m³, naming an unresolved endpoint', async ({
    page,
  }) => {
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractList(page, respond)

    await page.goto('/contracts?contract_type=courier&ships_only=false')
    await expect(rowLinks(page)).toHaveCount(COURIER_CONTRACTS.length)

    // Criteria 5.3/5.4. Location is gone because the origin is half the route.
    await expect(page.getByRole('columnheader', { name: 'Route', exact: true })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Reward', exact: true })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Reward/m³', exact: true })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Location', exact: true })).toHaveCount(0)

    // Criterion 5.3 names the deadline, and this project runs at 412px too: the
    // days a hauler has to deliver in appear NOWHERE else in the app, so a
    // breakpoint that drops the column drops the field entirely. It is also the
    // narrowest cell the set has.
    await expect(page.getByRole('columnheader', { name: 'Deadline', exact: true })).toBeVisible()
    await expect(page.getByText('7d', { exact: true })).toBeVisible()

    const origin = 'Jita IV - Moon 4 - Caldari Navy Assembly Plant'
    await expect(
      page.getByText(`${origin} → Amarr VIII (Oris) - Emperor Family Academy`, { exact: true }),
    ).toBeVisible()
    // Spec §8: a destination no public token can resolve reads as unknown —
    // never blank, never the raw id, never a plausible-looking station.
    await expect(page.getByText(`${origin} → Unknown structure`, { exact: true })).toBeVisible()
    await expect(page.getByText(/1038000000/)).toHaveCount(0)

    // 120,000,000 ISK over 60,000 m³. Criterion 5.6 — the rate is the only
    // normalization on the row, and nothing here reads as near or far.
    await expect(page.getByText('2,000', { exact: true })).toBeVisible()
  })

  test('a shared courier URL restores the segment', async ({ page }) => {
    await interceptCurrentUser(page, { status: 401 })
    const calls = await interceptContractList(page, respond)

    await page.goto('/contracts?contract_type=courier&ships_only=false')

    await expect(rowLinks(page)).toHaveCount(COURIER_CONTRACTS.length)
    await expect(segment(page, 'Courier 3')).toHaveAttribute('aria-pressed', 'true')
    await expect(segment(page, `All ${ALL_SHIPS_ONLY}`)).toHaveAttribute('aria-pressed', 'false')

    const first = calls[0]
    expect(first.params.getAll('contract_type')).toEqual(['courier'])
    expect(first.params.has('is_ship_contract')).toBe(false)
  })
})
