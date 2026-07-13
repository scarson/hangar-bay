import type { Page } from '@playwright/test'
import type { WireContract, WirePage } from '../fixtures/contracts'
import type { WireCurrentUser } from '../fixtures/auth'

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

/** Serve a tiny PNG for EVE portrait requests so authenticated specs stay fully offline. */
export async function stubPortraits(page: Page): Promise<void> {
  await page.route('**://images.evetech.net/**', (route) =>
    route.fulfill({ status: 200, contentType: 'image/png', body: PORTRAIT_PNG }),
  )
}
