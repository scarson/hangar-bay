// ABOUTME: WatchlistPage tests over the real /watchlist route — auth branches, add-by-name form, clear-to-null edit, two-step remove.
// ABOUTME: Asserts add-form and clear-to-null PUT wire payloads (TEST-5); TEST-8 skeleton-unmount sync before list assertions.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, screen, waitFor, waitForElementToBeRemoved } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

const AUTHED = { character_id: 91000001, character_name: 'Sesta Hound' }
const ROWS = [{ id: 1, type_id: 587, type_name: 'Rifter', max_price: 5000000, notes: 'cheap', created_at: 'x', updated_at: 'x' }]

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

describe('WatchlistPage', () => {
  it('prompts anonymous users to sign in', async () => {
    stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse({ detail: 'unauth' }, 401) : jsonResponse([])))
    renderApp('/watchlist')
    expect(await screen.findByRole('heading', { name: /sign in to use your watchlist/i })).toBeInTheDocument()
  })

  it('lists rows after the skeleton unmounts (TEST-8)', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse(ROWS)
      return jsonResponse([])
    })
    renderApp('/watchlist')
    const skeleton = await screen.findByRole('status', { name: /loading watchlist/i })
    await waitForElementToBeRemoved(skeleton)
    expect(screen.getByText('Rifter')).toBeInTheDocument()
  })

  it('adds by name with the optional price + notes payload', async () => {
    // GET (list) and POST (create) share the /me/watchlist-items/ collection URL; the list query needs
    // an array, so branch on method — return the created object only for the POST.
    const calls = stubFetch((url, call) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\//.test(url)) {
        return call.method === 'POST'
          ? jsonResponse({ id: 2, type_id: 24694, type_name: 'Maelstrom', max_price: 300000000, notes: 'flagship', created_at: 'x', updated_at: 'x' }, 201)
          : jsonResponse([])
      }
      return jsonResponse([])
    })
    renderApp('/watchlist')
    await screen.findByRole('heading', { level: 1, name: /watchlist/i })
    await userEvent.type(screen.getByLabelText(/ship name/i), 'Maelstrom')
    await userEvent.type(screen.getByLabelText(/max price/i), '300000000')
    await userEvent.type(screen.getByLabelText(/notes/i), 'flagship')
    await userEvent.click(screen.getByRole('button', { name: /add to watchlist/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/watchlist-items\//.test(c.url) && c.method === 'POST')).toBe(true))
    const post = calls.find((c) => /\/me\/watchlist-items\//.test(c.url) && c.method === 'POST')!
    expect(JSON.parse(post.body!)).toEqual({ type_name: 'Maelstrom', max_price: 300000000, notes: 'flagship' })
  })

  it('shows an inline error when the name is unknown (400)', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse({ detail: 'unknown ship name' }, 400)
      return jsonResponse([])
    })
    renderApp('/watchlist')
    await screen.findByRole('heading', { level: 1, name: /watchlist/i })
    await userEvent.type(screen.getByLabelText(/ship name/i), 'Rlfter')
    await userEvent.click(screen.getByRole('button', { name: /add to watchlist/i }))
    expect(await screen.findByText(/couldn.t find a ship/i)).toBeInTheDocument()
  })

  it('clears max_price to null via the clear affordance (PUT body is JSON null)', async () => {
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\/1/.test(url)) return jsonResponse({ ...ROWS[0], max_price: null })
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse(ROWS)
      return jsonResponse([])
    })
    renderApp('/watchlist')
    await screen.findByText('Rifter')
    await userEvent.click(screen.getByRole('button', { name: /clear max price/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/watchlist-items\/1/.test(c.url) && c.method === 'PUT')).toBe(true))
    const put = calls.find((c) => /\/me\/watchlist-items\/1/.test(c.url) && c.method === 'PUT')!
    expect(JSON.parse(put.body!)).toHaveProperty('max_price', null)
  })

  it('requires a second click to remove (two-step)', async () => {
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\/1/.test(url)) return new Response(null, { status: 204 })
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse(ROWS)
      return jsonResponse([])
    })
    renderApp('/watchlist')
    await screen.findByText('Rifter')
    await userEvent.click(screen.getByRole('button', { name: /^remove$/i }))
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
    await userEvent.click(screen.getByRole('button', { name: /confirm remove/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/watchlist-items\/1/.test(c.url) && c.method === 'DELETE')).toBe(true))
  })

  it('rejects an entered max price of 0 with an inline message and does not POST', async () => {
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse([])
      return jsonResponse([])
    })
    renderApp('/watchlist')
    await screen.findByRole('heading', { level: 1, name: /watchlist/i })
    await userEvent.type(screen.getByLabelText(/ship name/i), 'Rifter')
    await userEvent.type(screen.getByLabelText(/max price/i), '0')
    await userEvent.click(screen.getByRole('button', { name: /add to watchlist/i }))
    expect(await screen.findByText(/max price must be at least 0\.01/i)).toBeInTheDocument()
    expect(calls.some((c) => /\/me\/watchlist-items\//.test(c.url) && c.method === 'POST')).toBe(false)
  })

  it('auto-disarms the two-step remove after 5s (timeout reset)', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse(ROWS)
      return jsonResponse([])
    })
    renderApp('/watchlist')
    await screen.findByText('Rifter')
    // Enable fake timers AFTER the initial load so the arming click schedules the 5s timeout on the
    // fake clock. The arming click uses fireEvent (synchronous), not userEvent: userEvent's async
    // event wrapper awaits an internal setTimeout-based flush that deadlocks once the global clock is
    // faked (the advanceTimers hook only drives userEvent's own inter-event delay, not that flush).
    vi.useFakeTimers()
    try {
      fireEvent.click(screen.getByRole('button', { name: /^remove$/i }))
      expect(screen.getByRole('button', { name: /confirm remove/i })).toBeInTheDocument()
      act(() => { vi.advanceTimersByTime(5000) })
      expect(screen.queryByRole('button', { name: /confirm remove/i })).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })
})
