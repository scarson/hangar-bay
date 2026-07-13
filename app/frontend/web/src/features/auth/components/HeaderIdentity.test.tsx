// ABOUTME: Header identity states over the real routeTree — anonymous link, authenticated cluster, logout.
// ABOUTME: The login href must carry next=encodeURIComponent(pathname+search) exactly.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

afterEach(() => vi.unstubAllGlobals())

describe('HeaderIdentity', () => {
  it('renders a login link with the encoded next when anonymous', async () => {
    vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse({ detail: 'unauthenticated' }, 401)
      return jsonResponse({ total: 0, page: 1, size: 50, items: [] })
    })
    const { router } = renderApp('/contracts?is_bpc=true')
    const link = await screen.findByRole('link', { name: /log in with eve/i })
    // The /contracts route's validateSearch defaults every field (page, size,
    // sort_by, …) and TanStack Router writes the fully-resolved search back
    // onto the location (confirmed even at the browser-history level — see
    // e2e/sorting.spec.ts's bare `goto('/contracts')` asserting sort_by/
    // sort_direction land in the URL). So "next" is derived from the SAME
    // resolved location the app itself would carry, not a bare '?is_bpc=true'.
    const expectedNext = encodeURIComponent(
      router.state.location.pathname + router.state.location.searchStr,
    )
    expect(link).toHaveAttribute('href', `/api/v1/auth/sso/login?next=${expectedNext}`)
    expect(expectedNext).toContain('is_bpc%3Dtrue')
  })

  it('strips a stale ?sso flag out of the encoded next', async () => {
    // A transient ?sso=error|denied on the current URL must not survive into `next` —
    // otherwise a successful login round-trips the user right back to the stale
    // error/denied notice. Derive the expectation from the router's own resolved
    // location (same non-vacuous pattern as the test above), stripped of sso, so this
    // doesn't degrade into a hand-rolled string that could pass for the wrong reason.
    vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse({ detail: 'unauthenticated' }, 401)
      return jsonResponse({ total: 0, page: 1, size: 50, items: [] })
    })
    const { router } = renderApp('/contracts?sso=error&is_bpc=true')
    const link = await screen.findByRole('link', { name: /log in with eve/i })
    const params = new URLSearchParams(router.state.location.searchStr)
    params.delete('sso')
    const strippedSearch = params.toString()
    const expectedNext = encodeURIComponent(
      router.state.location.pathname + (strippedSearch ? `?${strippedSearch}` : ''),
    )
    expect(link).toHaveAttribute('href', `/api/v1/auth/sso/login?next=${expectedNext}`)
    expect(expectedNext).toContain('is_bpc%3Dtrue')
    expect(expectedNext).not.toContain('sso')
  })

  it('renders portrait + name + logout when authenticated', async () => {
    vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse({ character_id: 91000001, character_name: 'Sesta Hound' })
      return jsonResponse({ total: 0, page: 1, size: 50, items: [] })
    })
    renderApp('/contracts')
    expect(await screen.findByText('Sesta Hound')).toBeInTheDocument()
    // The portrait is decorative (alt="") so it has no accessible role — query the
    // DOM directly; the src must carry the character id at 2x (size=64 for 24px).
    const portrait = document.querySelector('img[src*="images.evetech.net"]') as HTMLImageElement
    expect(portrait.getAttribute('src')).toBe('https://images.evetech.net/characters/91000001/portrait?size=64')
    expect(screen.getByRole('button', { name: /log out/i })).toBeInTheDocument()
  })

  it('logs out and returns to anonymous', async () => {
    const calls: { url: string; method?: string }[] = []
    let authed = true
    vi.stubGlobal('fetch', async (input: RequestInfo | URL, init?: RequestInit) => {
      const req = input as Request
      const url = req.url ?? String(input)
      if (/\/api\/v1\/auth\/sso\/logout$/.test(url)) {
        calls.push({ url, method: req.method ?? init?.method })
        authed = false
        return new Response(null, { status: 204 })
      }
      if (/\/api\/v1\/me$/.test(url)) {
        return authed
          ? jsonResponse({ character_id: 91000001, character_name: 'Sesta Hound' })
          : jsonResponse({ detail: 'unauthenticated' }, 401)
      }
      return jsonResponse({ total: 0, page: 1, size: 50, items: [] })
    })
    renderApp('/contracts')
    await userEvent.click(await screen.findByRole('button', { name: /log out/i }))
    expect(calls[0].method).toBe('POST')
    expect(await screen.findByRole('link', { name: /log in with eve/i })).toBeInTheDocument()
  })
})
