import { expect, test, type Page } from '@playwright/test'
import { SEVEN_SHIPS, makeContract, makeShipItem, pageOf } from './fixtures/contracts'
import { interceptContractDetail, interceptContractList, interceptCurrentUser } from './helpers/api'
import { openFiltersIfCollapsed, rowLinks } from './helpers/ui'

/**
 * M1 spec lines 165-169: the load lifecycle states — loading skeleton, empty
 * result, error + retry, the polite live-region count — plus the detail page's
 * own loading and error branches. Read from the source of truth:
 * ContractsPage.tsx (skeleton / alert / empty / status branches) and
 * ContractDetailPage.tsx (loading status / error alert).
 *
 * Delayed-response scenarios use a manually released gate rather than a wall-clock
 * sleep, so "skeleton is up while the request is in flight" is proven by holding
 * the response open, not by racing an ~800ms timer (testing-pitfalls TEST-2:
 * deterministic synchronization, never timing bounds). The list/detail URL
 * regexes mirror helpers/api.ts; they live here only because the shared
 * interceptors resolve synchronously and cannot hold a response open.
 */

const LIST_URL = /\/api\/v1\/contracts\/(\?|$)/
const DETAIL_URL = /\/api\/v1\/contracts\/\d+$/

/** A promise plus its resolver, so a route handler can block until released. */
function gate() {
  let release!: () => void
  const opened = new Promise<void>((resolve) => {
    release = resolve
  })
  return { opened, release }
}

async function jsonFulfill(route: import('@playwright/test').Route, body: unknown) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
}

/**
 * The always-mounted polite live region (the "N contracts match" p). role=status
 * takes no accessible name from its text content, so it can't be selected by name;
 * once data has rendered (not pending) it is the only status node on the page, so
 * a bare getByRole('status') is unambiguous — same selector the exemplar uses.
 * BUT the loading skeleton is ALSO a status node (named "Loading contracts"), so
 * any live-region assertion that can poll while the fetch is in flight must first
 * wait for the skeleton to unmount (strict-mode race otherwise — TEST-2:
 * deterministic synchronization, not retries).
 */
function liveRegion(page: Page) {
  return page.getByRole('status')
}

async function waitForDataRendered(page: Page) {
  await expect(page.getByRole('status', { name: 'Loading contracts' })).toHaveCount(0)
}

test.describe('states', () => {
  test('loading skeleton shows while the list request is in flight, then rows replace it', async ({
    page,
  }) => {
    await interceptCurrentUser(page, { status: 401 })
    const { opened, release } = gate()
    await page.route(LIST_URL, async (route) => {
      await opened
      await jsonFulfill(route, pageOf(SEVEN_SHIPS))
    })

    await page.goto('/contracts')

    // The skeleton (role=status, accessible name "Loading contracts") is the only
    // status node while pending — the count live region is empty until data lands,
    // so the name disambiguates it from that second role=status element.
    const skeleton = page.getByRole('status', { name: 'Loading contracts' })
    await expect(skeleton).toBeVisible()
    await expect(rowLinks(page)).toHaveCount(0)

    release()

    await expect(rowLinks(page)).toHaveText([
      'Revelation',
      'Raven',
      'Maelstrom',
      'Purifier',
      'Hound',
      'Breacher',
      'Minmatar Shuttle',
    ])
    await expect(skeleton).toHaveCount(0)
  })

  test('empty result shows the no-match card, Clear filters, and announces zero', async ({
    page,
  }) => {
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractList(page, pageOf([]))

    await page.goto('/contracts')

    const results = page.getByRole('region', { name: 'Contract results' })
    await expect(
      results.getByRole('heading', { name: 'No contracts match these filters' }),
    ).toBeVisible()
    await expect(results.getByRole('button', { name: 'Clear filters' })).toBeVisible()
    await expect(rowLinks(page)).toHaveCount(0)

    // Live region reports the zero count (wording is always plural — match loosely).
    await waitForDataRendered(page)
    await expect(liveRegion(page)).toHaveText(/0 contracts? match/)
  })

  test('error state shows the failure alert + Retry; retry recovers to rows', async ({ page }) => {
    // Production QueryClient runs retry:1, so the initial load makes TWO attempts
    // before surfacing an error — failing only call 0 would auto-recover on call 1
    // and never reach the alert. Fail both initial attempts, then let the manual
    // Retry (call 2) succeed.
    await interceptCurrentUser(page, { status: 401 })
    const calls = await interceptContractList(page, (_params, call) =>
      call < 2 ? { status: 500 } : pageOf(SEVEN_SHIPS),
    )

    await page.goto('/contracts')

    const alert = page.getByRole('alert')
    await expect(alert).toBeVisible()
    await expect(alert).toContainText(
      'Failed to load contracts. The market data service may be unreachable.',
    )
    expect(calls.length).toBe(2)

    await page.getByRole('button', { name: 'Retry' }).click()

    await expect(rowLinks(page)).toHaveText([
      'Revelation',
      'Raven',
      'Maelstrom',
      'Purifier',
      'Hound',
      'Breacher',
      'Minmatar Shuttle',
    ])
    await expect(page.getByRole('alert')).toHaveCount(0)
  })

  test('live region updates the count when a filter narrows the set', async ({ page }) => {
    // Responder keyed on the wire param: is_bpc=true narrows to two rows. This is a
    // synthetic narrowing to exercise the announcement, not a product claim about
    // ship/BPC overlap; the fixture lane is authoritative for what comes back.
    await interceptCurrentUser(page, { status: 401 })
    const calls = await interceptContractList(page, (params) =>
      pageOf(params.get('is_bpc') === 'true' ? SEVEN_SHIPS.slice(0, 2) : SEVEN_SHIPS),
    )

    await page.goto('/contracts')
    await expect(page.getByRole('heading', { level: 1, name: 'Ship Contracts' })).toBeVisible()
    await waitForDataRendered(page)
    await expect(liveRegion(page)).toHaveText(/7 contracts? match/)

    await openFiltersIfCollapsed(page)
    await page.getByLabel('Blueprint copies only').check()

    await waitForDataRendered(page)
    await expect(liveRegion(page)).toHaveText(/2 contracts? match/)

    // TEST-5: the wire carried the filter AND the render/announcement changed.
    const last = calls[calls.length - 1]
    expect(last.params.get('is_bpc')).toBe('true')
  })

  test('detail page shows its loading status while the request is in flight', async ({ page }) => {
    const contract = makeContract({
      contract_id: 232_100_001,
      items: [makeShipItem('Revelation')],
    })
    await interceptCurrentUser(page, { status: 401 })
    const { opened, release } = gate()
    await page.route(DETAIL_URL, async (route) => {
      await opened
      await jsonFulfill(route, contract)
    })

    await page.goto('/contracts/232100001')

    const loading = page.getByRole('status', { name: 'Loading contract' })
    await expect(loading).toBeVisible()

    release()

    await expect(page.getByRole('heading', { level: 1, name: 'Revelation' })).toBeVisible()
    await expect(loading).toHaveCount(0)
  })

  test('detail page shows its error alert + Retry when the request fails', async ({ page }) => {
    // useContract retries non-404s once, so a persistent 500 makes two attempts and
    // then renders the error branch (not the 404 NotFound branch).
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractDetail(page, { status: 500 })

    await page.goto('/contracts/232100001')

    const alert = page.getByRole('alert')
    await expect(alert).toBeVisible()
    await expect(alert).toContainText('Failed to load this contract.')
    await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible()
  })
})
