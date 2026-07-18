import type { Page } from '@playwright/test'
import type { WireContract, WirePage } from '../fixtures/contracts'
import type { WireCurrentUser } from '../fixtures/auth'
import { makeSavedSearch, type WireSavedSearch } from '../fixtures/account'
import type { WireWatchlistItem } from '../fixtures/account'

/**
 * Route-interception helpers for the fixture lane.
 *
 * The app calls the list endpoint at `/api/v1/contracts/` — trailing slash
 * included — and the detail endpoint at `/api/v1/contracts/{id}` (no slash).
 * The slash is load-bearing (implementation-pitfalls PROXY-1): tests should
 * assert pathname === '/api/v1/contracts/' so a regression to the bare path
 * fails here instead of 307-escaping the proxy in dev.
 */

const LIST_URL = /\/api\/v1\/contracts\/(\?|$)/
const DETAIL_URL = /\/api\/v1\/contracts\/\d+$/

export interface CapturedCall {
  /** Full request URL. */
  url: URL
  /** Query params of the request (repeated keys preserved). */
  params: URLSearchParams
}

export type ListResponder =
  | WirePage
  | ((params: URLSearchParams, call: number) => WirePage | ErrorResponse)

export interface ErrorResponse {
  status: number
  body?: unknown
}

function isErrorResponse(value: unknown): value is ErrorResponse {
  return typeof value === 'object' && value !== null && 'status' in value && !('items' in value)
}

/**
 * Intercept the contract-list endpoint. Returns the (live) array of captured
 * calls so tests can assert the request contract — both the rendered outcome
 * AND the request URL matter (testing-pitfalls TEST-5).
 *
 * `responder` may be a static page or a function of (params, callIndex),
 * which lets a single test serve page 1 and page 2 correctly, or fail the
 * first call and succeed the retry.
 */
export async function interceptContractList(page: Page, responder: ListResponder): Promise<CapturedCall[]> {
  const calls: CapturedCall[] = []
  await page.route(LIST_URL, async (route) => {
    const url = new URL(route.request().url())
    calls.push({ url, params: url.searchParams })
    const result = typeof responder === 'function' ? responder(url.searchParams, calls.length - 1) : responder
    if (isErrorResponse(result)) {
      await route.fulfill({
        status: result.status,
        contentType: 'application/json',
        body: JSON.stringify(result.body ?? { detail: 'error' }),
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(result),
    })
  })
  return calls
}

export type DetailResponder = WireContract | ErrorResponse | ((contractId: number) => WireContract | ErrorResponse)

/** Intercept the contract-detail endpoint. */
export async function interceptContractDetail(page: Page, responder: DetailResponder): Promise<CapturedCall[]> {
  const calls: CapturedCall[] = []
  await page.route(DETAIL_URL, async (route) => {
    const url = new URL(route.request().url())
    calls.push({ url, params: url.searchParams })
    const contractId = Number(url.pathname.split('/').at(-1))
    const result = typeof responder === 'function' ? responder(contractId) : responder
    if (isErrorResponse(result)) {
      await route.fulfill({
        status: result.status,
        contentType: 'application/json',
        body: JSON.stringify(result.body ?? { detail: 'Contract not found' }),
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(result),
    })
  })
  return calls
}

/**
 * Block every /api/v1 request that no more-specific route handled. Register
 * FIRST in tests that must prove a request is never sent (e.g. the 3-char
 * search gate): page.route handlers run last-registered-first, so specific
 * intercepts still win, and anything else aborts loudly instead of leaking
 * to the real backend.
 */
export async function failUnexpectedApiCalls(page: Page): Promise<void> {
  await page.route('**/api/v1/**', async (route) => {
    await route.abort('failed')
  })
}

const ME_URL = /\/api\/v1\/me$/
const LOGOUT_URL = /\/api\/v1\/auth\/sso\/logout$/

export type CurrentUserResponder = WireCurrentUser | ErrorResponse

/** Intercept GET /me. Pass `{ status: 401 }` for the anonymous default. */
export async function interceptCurrentUser(page: Page, responder: CurrentUserResponder): Promise<void> {
  await page.route(ME_URL, async (route) => {
    if (isErrorResponse(responder)) {
      await route.fulfill({
        status: responder.status,
        contentType: 'application/json',
        body: JSON.stringify(responder.body ?? { detail: 'unauthenticated' }),
      })
      return
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(responder) })
  })
}

export interface LogoutCall extends CapturedCall {
  /** HTTP method of the captured request — the spec must assert it is POST. */
  method: string
}

/** Intercept /auth/sso/logout (any method — capture, then assert POST), fulfilling 204.
 * `onFulfill` runs before the 204 is sent: use it to flip sibling /me route state so
 * the post-logout /me refetch — which can only fire after the 204 — deterministically
 * observes the anonymous state (retries are 0; TEST-2 forbids masking timing). */
export async function interceptLogout(page: Page, onFulfill?: () => void): Promise<LogoutCall[]> {
  const calls: LogoutCall[] = []
  await page.route(LOGOUT_URL, async (route) => {
    const url = new URL(route.request().url())
    calls.push({ url, params: url.searchParams, method: route.request().method() })
    onFulfill?.()
    await route.fulfill({ status: 204, body: '' })
  })
  return calls
}

// 1x1 transparent PNG. The character portrait points at images.evetech.net, which is
// OUTSIDE /api/v1/** — without this stub, authenticated-header specs fire a live CDN
// request from the hermetic fixture lane (offline/throttled CI runners would hang on it).
const PORTRAIT_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
  'base64',
)

/** Serve a tiny PNG for ALL images.evetech.net requests — character portraits AND type renders
 * (e.g. /types/{id}/render on the watchlist page) — so authenticated specs stay fully offline. */
export async function stubPortraits(page: Page): Promise<void> {
  await page.route('**://images.evetech.net/**', (route) =>
    route.fulfill({ status: 200, contentType: 'image/png', body: PORTRAIT_PNG }),
  )
}

export interface AccountCall {
  url: URL
  method: string
  body: unknown
}

function readBody(route: import('@playwright/test').Route): unknown {
  try {
    return route.request().postDataJSON()
  } catch {
    return undefined
  }
}

/** Intercept /me/notifications/* and /me/notification-settings. The count query (is_read=false&size=1)
 * returns { total: unread, items: [] }; the list query returns the page; mark-read/all return 204;
 * settings GET returns `settings`, PUT captures + echoes. Shared by the header bell's auth specs and
 * the notifications spec (Task 9.4). */
export async function interceptNotifications(
  page: Page,
  opts: { items?: ReadonlyArray<{ is_read: boolean }>; unread?: number; settings?: { watchlist_alerts_enabled: boolean } } = {},
): Promise<AccountCall[]> {
  const calls: AccountCall[] = []
  const items = opts.items ?? []
  const unread = opts.unread ?? items.filter((n) => !n.is_read).length
  let settings = opts.settings ?? { watchlist_alerts_enabled: true }
  await page.route(/\/api\/v1\/me\/notification-settings/, async (route) => {
    const req = route.request()
    const method = req.method()
    if (method === 'PUT') {
      const body = readBody(route) as { watchlist_alerts_enabled: boolean }
      settings = body
      calls.push({ url: new URL(req.url()), method, body })
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(settings) })
    }
    calls.push({ url: new URL(req.url()), method, body: undefined })
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(settings) })
  })
  await page.route(/\/api\/v1\/me\/notifications/, async (route) => {
    const req = route.request()
    const method = req.method()
    const url = new URL(req.url())
    calls.push({ url, method, body: method === 'POST' ? readBody(route) : undefined })
    if (/\/mark-all-read$/.test(url.pathname) || /\/mark-read$/.test(url.pathname)) {
      return route.fulfill({ status: 204, body: '' })
    }
    if (url.searchParams.get('is_read') === 'false' && url.searchParams.get('size') === '1') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ total: unread, page: 1, size: 1, items: [] }) })
    }
    const pageNum = Number(url.searchParams.get('page') ?? '1')
    const size = Number(url.searchParams.get('size') ?? '20')
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ total: items.length, page: pageNum, size, items }) })
  })
  return calls
}

/** Intercept /me/saved-searches/* — GET returns `list`, POST echoes a made row (201), PUT 200, DELETE 204. */
export async function interceptSavedSearches(page: Page, list: WireSavedSearch[] = []): Promise<AccountCall[]> {
  const calls: AccountCall[] = []
  await page.route(/\/api\/v1\/me\/saved-searches\//, async (route) => {
    const req = route.request()
    const method = req.method()
    const body = method === 'POST' || method === 'PUT' ? readBody(route) : undefined
    calls.push({ url: new URL(req.url()), method, body })
    if (method === 'GET') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(list) })
    if (method === 'DELETE') return route.fulfill({ status: 204, body: '' })
    const echo = makeSavedSearch(body as Partial<WireSavedSearch>)
    return route.fulfill({ status: method === 'POST' ? 201 : 200, contentType: 'application/json', body: JSON.stringify(echo) })
  })
  return calls
}

/** Intercept /me/watchlist-items/* — GET returns `list`, POST echoes (201), PUT 200, DELETE 204. */
export async function interceptWatchlist(page: Page, list: WireWatchlistItem[] = []): Promise<AccountCall[]> {
  const calls: AccountCall[] = []
  await page.route(/\/api\/v1\/me\/watchlist-items\//, async (route) => {
    const req = route.request()
    const method = req.method()
    const body = method === 'POST' || method === 'PUT' ? readBody(route) : undefined
    calls.push({ url: new URL(req.url()), method, body })
    if (method === 'GET') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(list) })
    if (method === 'DELETE') return route.fulfill({ status: 204, body: '' })
    const src = (body ?? {}) as Partial<WireWatchlistItem>
    return route.fulfill({ status: method === 'POST' ? 201 : 200, contentType: 'application/json', body: JSON.stringify({ id: 999, type_id: src.type_id ?? 587, type_name: src.type_name ?? 'Rifter', max_price: src.max_price ?? null, notes: src.notes ?? null, created_at: 'x', updated_at: 'x' }) })
  })
  return calls
}
