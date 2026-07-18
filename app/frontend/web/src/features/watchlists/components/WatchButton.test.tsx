// ABOUTME: WatchButton over the real contract-detail route — authed-only, one-click add by type_id, 409 "already watching".
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { anonymousMe, jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

const AUTHED = { character_id: 91000001, character_name: 'Sesta Hound' }
const CONTRACT = {
  contract_id: 101, issuer_id: 1, issuer_corporation_id: 101, start_location_id: 60003760,
  type: 'item_exchange', status: 'unknown', title: 'Rifter for sale', for_corporation: false,
  date_issued: '2026-07-01T00:00:00Z', date_expired: '2030-07-08T00:00:00Z', date_completed: null,
  price: 1000000, reward: 0, volume: 27, start_location_name: 'Jita IV - Moon 4', issuer_name: 'Sesta Hound',
  issuer_corporation_name: 'COB', is_ship_contract: true,
  items: [{ record_id: 1011, type_id: 587, quantity: 1, is_included: true, is_singleton: false, is_blueprint_copy: false, raw_quantity: null, type_name: 'Rifter', category: 'ship', market_group_id: 61 }],
}

interface Call { url: string; method?: string; body?: string }
function stubFetch(handler: (url: string, call: Call) => Response): Call[] {
  const calls: Call[] = []
  vi.stubGlobal('fetch', async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input as Request
    const url = req.url ?? String(input)
    const call: Call = { url, method: req.method ?? init?.method, body: await req.clone().text() }
    calls.push(call)
    return handler(url, call)
  })
  return calls
}
afterEach(() => vi.unstubAllGlobals())

describe('WatchButton', () => {
  it('is hidden for anonymous users', async () => {
    stubFetch(anonymousMe(() => jsonResponse(CONTRACT)))
    renderApp('/contracts/101')
    await screen.findByRole('heading', { level: 1, name: 'Rifter' })
    expect(screen.queryByRole('button', { name: /^watch$/i })).not.toBeInTheDocument()
  })

  it('adds by type_id on click for an authed user', async () => {
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse({ id: 1, type_id: 587, type_name: 'Rifter', max_price: null, notes: null, created_at: 'x', updated_at: 'x' }, 201)
      return jsonResponse(CONTRACT)
    })
    renderApp('/contracts/101')
    await userEvent.click(await screen.findByRole('button', { name: /^watch$/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/watchlist-items\//.test(c.url) && c.method === 'POST')).toBe(true))
    const post = calls.find((c) => /\/me\/watchlist-items\//.test(c.url) && c.method === 'POST')!
    expect(JSON.parse(post.body!)).toEqual({ type_id: 587 })
    expect(await screen.findByText(/watching/i)).toBeInTheDocument()
  })

  it('shows "already watching" on a 409', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse({ detail: 'dup' }, 409)
      return jsonResponse(CONTRACT)
    })
    renderApp('/contracts/101')
    await userEvent.click(await screen.findByRole('button', { name: /^watch$/i }))
    expect(await screen.findByText(/already watching/i)).toBeInTheDocument()
  })
})
