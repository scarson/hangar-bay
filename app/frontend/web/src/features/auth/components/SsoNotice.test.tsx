// ABOUTME: ?sso=denied|error notice — renders, dismiss strips only the sso param (replace navigation).
// ABOUTME: Includes the root-redirect passthrough: /?sso=error must survive to /contracts.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

afterEach(() => vi.unstubAllGlobals())

function stubAnonymous() {
  vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : (input as Request).url
    if (/\/api\/v1\/me$/.test(url)) return jsonResponse({ detail: 'unauthenticated' }, 401)
    return jsonResponse({ total: 0, page: 1, size: 50, items: [] })
  })
}

describe('SsoNotice', () => {
  it('renders the denied notice and strips ?sso on dismiss', async () => {
    stubAnonymous()
    const { router } = renderApp('/contracts?sso=denied')
    const notice = await screen.findByText(/cancelled/i)
    expect(notice).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /dismiss/i }))
    await waitFor(() => expect((router.state.location.search as Record<string, unknown>).sso).toBeUndefined())
    expect(screen.queryByText(/cancelled/i)).not.toBeInTheDocument()
  })

  it('renders the error notice', async () => {
    stubAnonymous()
    renderApp('/contracts?sso=error')
    expect(await screen.findByText(/went wrong/i)).toBeInTheDocument()
  })

  it('renders the error notice when the flag lands on the root redirect', async () => {
    // The state-missing callback exit redirects to FRONTEND_ORIGIN/?sso=error (no next
    // is recoverable there — spec §4.1). The index route's redirect must forward the
    // search (search: true) or the flag dies before SsoNotice ever mounts.
    stubAnonymous()
    const { router } = renderApp('/?sso=error')
    expect(await screen.findByText(/went wrong/i)).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/contracts')
    expect((router.state.location.search as Record<string, unknown>).sso).toBe('error')
  })

  it('renders nothing without an sso param', async () => {
    stubAnonymous()
    renderApp('/contracts')
    await screen.findByRole('link', { name: /log in with eve/i })
    expect(screen.queryByText(/cancelled|went wrong/i)).not.toBeInTheDocument()
  })

  it('dismiss on a contract detail page stays on that page (does not fall back to the list)', async () => {
    // The notice is mounted at root, so an SSO redirect can land on ANY route, not just
    // the list. A previous bug resolved dismiss against a hard-coded `from: '/contracts/'`,
    // which discarded the detail segment: /contracts/123?sso=error&foo=bar -> /contracts?foo=bar.
    vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse({ detail: 'unauthenticated' }, 401)
      if (/\/api\/v1\/contracts\/123$/.test(url)) {
        return jsonResponse({
          contract_id: 123,
          issuer_id: 1,
          issuer_corporation_id: 101,
          start_location_id: 60003760,
          type: 'item_exchange',
          status: 'outstanding',
          title: 'Tristan for Sale',
          for_corporation: false,
          date_issued: '2026-07-01T00:00:00Z',
          date_expired: '2026-07-08T00:00:00Z',
          price: 1000000,
          is_ship_contract: true,
          items: [],
        })
      }
      return jsonResponse({ total: 0, page: 1, size: 50, items: [] })
    })
    const { router } = renderApp('/contracts/123?sso=error&foo=bar#items')
    const notice = await screen.findByText(/went wrong/i)
    expect(notice).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /dismiss/i }))
    await waitFor(() => expect((router.state.location.search as Record<string, unknown>).sso).toBeUndefined())
    expect(router.state.location.pathname).toBe('/contracts/123')
    expect((router.state.location.search as Record<string, unknown>).foo).toBe('bar')
    expect(router.state.location.hash).toBe('items')   // deep-linked #anchor survives dismiss
    expect(screen.queryByText(/went wrong/i)).not.toBeInTheDocument()
  })
})
