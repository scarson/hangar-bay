// ABOUTME: WatchlistPage tests over the real /watchlist route — auth branches, add-by-name form, clear-to-null edit, two-step remove.
// ABOUTME: Asserts add-form and clear-to-null PUT wire payloads (TEST-5); TEST-8 skeleton-unmount sync before list assertions.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, screen, waitFor, waitForElementToBeRemoved } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'
import { parseMaxPrice } from './WatchlistPage'

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

  it('surfaces the cap message (not "unknown ship") when the add hits the 200-item cap', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse({ detail: 'watchlist is full (max 200 items)' }, 400)
      return jsonResponse([])
    })
    renderApp('/watchlist')
    await screen.findByRole('heading', { level: 1, name: /watchlist/i })
    await userEvent.type(screen.getByLabelText(/ship name/i), 'Maelstrom')
    await userEvent.click(screen.getByRole('button', { name: /add to watchlist/i }))
    expect(await screen.findByText(/remove a ship before adding/i)).toBeInTheDocument()
    expect(screen.queryByText(/check the spelling/i)).not.toBeInTheDocument()
  })

  it('surfaces a not-a-ship message when the type is not a ship (400 detail)', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse({ detail: 'type is not a ship' }, 400)
      return jsonResponse([])
    })
    renderApp('/watchlist')
    await screen.findByRole('heading', { level: 1, name: /watchlist/i })
    await userEvent.type(screen.getByLabelText(/ship name/i), 'Tritanium')
    await userEvent.click(screen.getByRole('button', { name: /add to watchlist/i }))
    expect(await screen.findByText(/isn.t a ship/i)).toBeInTheDocument()
  })

  it('surfaces an upstream-outage message on a 502', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse({ detail: 'Ship metadata service is unavailable; try again.' }, 502)
      return jsonResponse([])
    })
    renderApp('/watchlist')
    await screen.findByRole('heading', { level: 1, name: /watchlist/i })
    await userEvent.type(screen.getByLabelText(/ship name/i), 'Maelstrom')
    await userEvent.click(screen.getByRole('button', { name: /add to watchlist/i }))
    expect(await screen.findByText(/eve.s api is unavailable/i)).toBeInTheDocument()
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

  it('rejects an edited max price of 0 with an inline message and does not PUT', async () => {
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse(ROWS)
      return jsonResponse([])
    })
    renderApp('/watchlist')
    await screen.findByText('Rifter')
    const input = screen.getByRole('spinbutton', { name: /max price for rifter/i })
    await userEvent.clear(input)
    await userEvent.type(input, '0')
    await userEvent.click(screen.getByRole('button', { name: /^save$/i }))
    expect(await screen.findByText(/max price must be at least 0\.01/i)).toBeInTheDocument()
    expect(calls.some((c) => /\/me\/watchlist-items\/1/.test(c.url) && c.method === 'PUT')).toBe(false)
  })

  it('rejects a negative edited max price with an inline message and does not PUT', async () => {
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse(ROWS)
      return jsonResponse([])
    })
    renderApp('/watchlist')
    await screen.findByText('Rifter')
    const input = screen.getByRole('spinbutton', { name: /max price for rifter/i })
    await userEvent.clear(input)
    await userEvent.type(input, '-5')
    await userEvent.click(screen.getByRole('button', { name: /^save$/i }))
    expect(await screen.findByText(/max price must be at least 0\.01/i)).toBeInTheDocument()
    expect(calls.some((c) => /\/me\/watchlist-items\/1/.test(c.url) && c.method === 'PUT')).toBe(false)
  })

  it('reverts the edited max price and shows an error when the PUT fails (500)', async () => {
    stubFetch((url, call) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\/1/.test(url) && call.method === 'PUT') return jsonResponse({ detail: 'boom' }, 500)
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse(ROWS)
      return jsonResponse([])
    })
    renderApp('/watchlist')
    await screen.findByText('Rifter')
    const input = screen.getByRole('spinbutton', { name: /max price for rifter/i })
    await userEvent.clear(input)
    await userEvent.type(input, '1234')
    await userEvent.click(screen.getByRole('button', { name: /^save$/i }))
    expect(await screen.findByText(/couldn.t save/i)).toBeInTheDocument()
    // The unsaved value is reverted to the last persisted price (5000000), never left dangling.
    await waitFor(() => expect(input).toHaveValue(5000000))
  })

  it('reverts the edited max price and shows an error when the PUT is rejected (422)', async () => {
    stubFetch((url, call) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\/1/.test(url) && call.method === 'PUT') return jsonResponse({ detail: 'invalid' }, 422)
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse(ROWS)
      return jsonResponse([])
    })
    renderApp('/watchlist')
    await screen.findByText('Rifter')
    const input = screen.getByRole('spinbutton', { name: /max price for rifter/i })
    await userEvent.clear(input)
    await userEvent.type(input, '9999')
    await userEvent.click(screen.getByRole('button', { name: /^save$/i }))
    expect(await screen.findByText(/couldn.t save/i)).toBeInTheDocument()
    await waitFor(() => expect(input).toHaveValue(5000000))
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

describe('parseMaxPrice', () => {
  it('treats an empty (or whitespace) field as a clear-to-null', () => {
    expect(parseMaxPrice('')).toEqual({ price: null })
    expect(parseMaxPrice('   ')).toEqual({ price: null })
  })

  it('accepts finite values at or above the 0.01 minimum', () => {
    expect(parseMaxPrice('0.01')).toEqual({ price: 0.01 })
    expect(parseMaxPrice('1000')).toEqual({ price: 1000 })
  })

  it('rejects zero and negative values', () => {
    expect(parseMaxPrice('0')).toHaveProperty('error')
    expect(parseMaxPrice('-5')).toHaveProperty('error')
  })

  it('rejects non-finite values (Infinity / NaN)', () => {
    // 1e309 overflows a double to Infinity; a real number input keeps the string (jsdom sanitizes it,
    // so this guard is exercised here rather than through the DOM). NaN comes from unparseable input.
    expect(parseMaxPrice('1e309')).toHaveProperty('error')
    expect(parseMaxPrice('abc')).toHaveProperty('error')
  })
})
