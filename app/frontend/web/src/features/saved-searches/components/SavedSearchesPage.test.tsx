// ABOUTME: SavedSearchesPage tests over the real /saved-searches route — auth branches, empty state, Apply/Rename/Delete, error + skeleton sync.
// ABOUTME: TEST-8: wait for the loading skeleton (role=status "Loading saved searches") to unmount before asserting list content.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, screen, waitFor, waitForElementToBeRemoved } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'
import { summarizeSearch } from './SavedSearchesPage'

const AUTHED = { character_id: 91000001, character_name: 'Sesta Hound' }
const SAVED = [
  { id: 1, name: 'Cheap frigates', search_parameters: { ships_only: true, min_price: 0, max_price: 5000000, size: 50, sort_by: 'price', sort_direction: 'asc' }, created_at: '2026-07-17T00:00:00Z', updated_at: '2026-07-17T00:00:00Z' },
]

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

describe('SavedSearchesPage', () => {
  it('prompts anonymous users to sign in', async () => {
    stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse({ detail: 'unauthenticated' }, 401) : jsonResponse([])))
    renderApp('/saved-searches')
    expect(await screen.findByRole('heading', { name: /sign in to use saved searches/i })).toBeInTheDocument()
  })

  it('lists saved searches for an authed user after the skeleton unmounts (TEST-8)', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse(SAVED)
      return jsonResponse([])
    })
    renderApp('/saved-searches')
    // Skeleton and the always-mounted live region are both role=status while loading;
    // sync on the skeleton unmounting before asserting content (TEST-8).
    const skeleton = await screen.findByRole('status', { name: /loading saved searches/i })
    await waitForElementToBeRemoved(skeleton)
    expect(screen.getByText('Cheap frigates')).toBeInTheDocument()
  })

  it('shows the empty state when the user has no saved searches', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse([])
      return jsonResponse([])
    })
    renderApp('/saved-searches')
    expect(await screen.findByText(/no saved searches yet/i)).toBeInTheDocument()
  })

  it('shows an error state when the list fails to load (TEST-7: every call fails)', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse({ detail: 'boom' }, 500)
      return jsonResponse([])
    })
    renderApp('/saved-searches')
    expect(await screen.findByRole('alert')).toHaveTextContent(/couldn.t load your saved searches/i)
  })

  it('applies a saved search by navigating to /contracts with the parsed params', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse(SAVED)
      return jsonResponse({ total: 0, page: 1, size: 50, items: [] })
    })
    const { router } = renderApp('/saved-searches')
    await screen.findByText('Cheap frigates')
    await userEvent.click(screen.getByRole('button', { name: /apply/i }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/contracts'))
    expect(router.state.location.searchStr).toContain('sort_by=price')
  })

  it('renames a saved search (PUT with the new name)', async () => {
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/saved-searches\/1/.test(url)) return jsonResponse({ ...SAVED[0], name: 'Renamed' })
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse(SAVED)
      return jsonResponse([])
    })
    renderApp('/saved-searches')
    await screen.findByText('Cheap frigates')
    await userEvent.click(screen.getByRole('button', { name: /rename/i }))
    const input = screen.getByLabelText(/new name/i)
    await userEvent.clear(input)
    await userEvent.type(input, 'Renamed')
    await userEvent.click(screen.getByRole('button', { name: /^save$/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/saved-searches\/1/.test(c.url) && c.method === 'PUT')).toBe(true))
    const put = calls.find((c) => /\/me\/saved-searches\/1/.test(c.url) && c.method === 'PUT')!
    expect(JSON.parse(put.body!)).toEqual({ name: 'Renamed' })
  })

  it('requires a second click to delete (two-step)', async () => {
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/saved-searches\/1/.test(url)) return new Response(null, { status: 204 })
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse(SAVED)
      return jsonResponse([])
    })
    renderApp('/saved-searches')
    await screen.findByText('Cheap frigates')
    await userEvent.click(screen.getByRole('button', { name: /^delete$/i }))
    // First click arms; no request yet.
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
    await userEvent.click(screen.getByRole('button', { name: /confirm delete/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/saved-searches\/1/.test(c.url) && c.method === 'DELETE')).toBe(true))
  })

  it('auto-disarms the two-step delete after 5s (timeout reset)', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse(SAVED)
      return jsonResponse([])
    })
    renderApp('/saved-searches')
    await screen.findByText('Cheap frigates')
    // Enable fake timers AFTER the initial load so the arming click schedules the 5s timeout on the
    // fake clock. The arming click uses fireEvent (synchronous), not userEvent: userEvent's async
    // event wrapper awaits an internal setTimeout-based flush that deadlocks once the global clock is
    // faked (the advanceTimers hook only drives userEvent's own inter-event delay, not that flush).
    vi.useFakeTimers()
    try {
      fireEvent.click(screen.getByRole('button', { name: /^delete$/i }))
      expect(screen.getByRole('button', { name: /confirm delete/i })).toBeInTheDocument()
      act(() => { vi.advanceTimersByTime(5000) })
      expect(screen.queryByRole('button', { name: /confirm delete/i })).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('summarizeSearch', () => {
  it('defaults the sort fields when an older stored blob omits them', () => {
    // Older blobs may omit the server-defaulted sort_by/sort_direction; the summary must still render
    // (a `.replace()` on undefined would be a TS build error and a runtime crash).
    expect(summarizeSearch({})).toContain('sorted by date issued desc')
  })
})
