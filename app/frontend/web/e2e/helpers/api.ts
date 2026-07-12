import type { Page } from '@playwright/test'
import type { WireContract, WirePage } from '../fixtures/contracts'

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
