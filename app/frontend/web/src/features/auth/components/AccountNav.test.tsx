// ABOUTME: AccountNav over the real routeTree — authed-only header links to /saved-searches and /watchlist.
// ABOUTME: Anonymous and pending states render no nav; the authed state exposes both links by role/name.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

afterEach(() => vi.unstubAllGlobals())

describe('AccountNav', () => {
  it('renders no account nav when anonymous', async () => {
    vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse({ detail: 'unauthenticated' }, 401)
      return jsonResponse({ total: 0, page: 1, size: 50, items: [] })
    })
    renderApp('/contracts')
    // Wait for the anonymous header to settle before asserting the nav's absence.
    await screen.findByRole('link', { name: /log in with eve/i })
    expect(screen.queryByRole('navigation', { name: /account/i })).not.toBeInTheDocument()
  })

  it('renders Saved searches and Watchlist links when authenticated', async () => {
    vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse({ character_id: 91000001, character_name: 'Sesta Hound' })
      return jsonResponse({ total: 0, page: 1, size: 50, items: [] })
    })
    renderApp('/contracts')
    const nav = await screen.findByRole('navigation', { name: /account/i })
    const savedSearches = screen.getByRole('link', { name: /saved searches/i })
    const watchlist = screen.getByRole('link', { name: /watchlist/i })
    expect(nav).toContainElement(savedSearches)
    expect(nav).toContainElement(watchlist)
    expect(savedSearches).toHaveAttribute('href', '/saved-searches')
    expect(watchlist).toHaveAttribute('href', '/watchlist')
  })

  it('renders no account nav while the identity is still pending', async () => {
    vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      // /me never resolves → useCurrentUser stays pending → the nav must stay hidden.
      if (/\/api\/v1\/me$/.test(url)) return new Promise<Response>(() => {})
      return jsonResponse({ total: 0, page: 1, size: 50, items: [] })
    })
    renderApp('/contracts')
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument())
    expect(screen.queryByRole('navigation', { name: /account/i })).not.toBeInTheDocument()
  })
})
