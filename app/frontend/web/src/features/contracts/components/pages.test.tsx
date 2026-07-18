import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { anonymousMe, jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

const CONTRACT = {
  contract_id: 101,
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
  start_location_name: 'Jita IV - Moon 4 - Caldari Navy Assembly Plant',
  is_ship_contract: true,
  items: [
    {
      record_id: 1011,
      type_id: 587,
      quantity: 1,
      is_included: true,
      is_singleton: false,
      type_name: 'Tristan',
    },
  ],
}

function stubFetch(handler: (url: string) => Response) {
  const calls: string[] = []
  vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
    const url =
      typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    calls.push(url)
    return handler(url)
  })
  return calls
}

afterEach(() => vi.unstubAllGlobals())

describe('ContractsPage', () => {
  it('renders fetched contracts in the table', async () => {
    stubFetch(anonymousMe(() => jsonResponse({ total: 1, page: 1, size: 50, items: [CONTRACT] })))

    renderApp('/contracts')

    expect(await screen.findByText('Tristan')).toBeInTheDocument()
    expect(screen.getByText(/1,000,000/)).toBeInTheDocument()
    // Descriptive per-view title (WCAG 2.4.2), not the scaffold's "web".
    expect(document.title).toBe('Ship Contracts — Hangar Bay')
    // Column headers are sticky so the labels/sort toggles survive a 50-row
    // scroll (JSDOM can't lay out `position: sticky`; guard the intent instead).
    expect(screen.getAllByRole('columnheader')[0].className).toContain('sticky')
  })

  it('announces the result count in a polite status region (WCAG 4.1.3)', async () => {
    stubFetch(anonymousMe(() => jsonResponse({ total: 1, page: 1, size: 50, items: [CONTRACT] })))

    renderApp('/contracts')

    // Wait for load so the skeleton's own role="status" has unmounted, leaving
    // only the count region — filter/sort/page outcomes reach assistive tech
    // without moving focus off a rail control.
    await screen.findByText('Tristan')
    const status = screen.getByRole('status')
    expect(status).toHaveTextContent('1 contract matches your filters')
    expect(status).toHaveAttribute('aria-live', 'polite')
  })

  it('falls back to "Contract <id>" when the title is empty and no item name resolves', async () => {
    // Real ESI data: title is "" (not null) and non-ship contracts often have
    // no resolvable type_name — ?? alone leaves an empty, unclickable-looking
    // link (found live during Task 9 acceptance).
    const untitled = {
      ...CONTRACT,
      contract_id: 555,
      title: '',
      items: [{ ...CONTRACT.items[0], type_name: null }],
    }
    stubFetch(anonymousMe(() => jsonResponse({ total: 1, page: 1, size: 50, items: [untitled] })))

    renderApp('/contracts')

    expect(await screen.findByRole('link', { name: 'Contract 555' })).toBeInTheDocument()
  })

  it('shows the empty state for zero results', async () => {
    stubFetch(anonymousMe(() => jsonResponse({ total: 0, page: 1, size: 50, items: [] })))

    renderApp('/contracts')

    expect(await screen.findByText(/no contracts match/i)).toBeInTheDocument()
  })

  it('shows the error state with a retry control on failure', async () => {
    stubFetch(anonymousMe(() => jsonResponse({ detail: 'boom' }, 500)))

    renderApp('/contracts')

    expect(await screen.findByRole('alert')).toHaveTextContent(/failed to load/i)
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('reads filters from the URL and sends them to the API', async () => {
    const calls = stubFetch(
      anonymousMe(() => jsonResponse({ total: 0, page: 1, size: 50, items: [] })),
    )

    renderApp('/contracts?region_ids=10000002&is_bpc=true&sort_by=price&sort_direction=asc')

    await screen.findByText(/no contracts match/i)
    // Order-independent: whether /me or the contracts query fires first is
    // scheduling, not contract (the header now issues its own /me request).
    const listCall = calls.find((u) => u.includes('/api/v1/contracts/'))!
    expect(listCall).toContain('region_ids=10000002')
    expect(listCall).toContain('is_bpc=true')
    expect(listCall).toContain('sort_by=price')
  })

  it('carries a repeated region_ids URL through to repeated API params (shareable-URL contract)', async () => {
    // Drives the full multi-value inbound seam end-to-end: TanStack Router's
    // qss decode of ?region_ids=…&region_ids=… -> parseContractSearch array
    // coercion -> toApiQuery -> openapi-fetch's repeated-array serializer.
    // Guards the two-repeat case that single-value URL tests can't (TEST-5).
    const calls = stubFetch(
      anonymousMe(() => jsonResponse({ total: 0, page: 1, size: 50, items: [] })),
    )

    renderApp('/contracts?region_ids=10000002&region_ids=10000020')

    await screen.findByText(/no contracts match/i)
    // Order-independent: see the rationale above.
    const listCall = calls.find((u) => u.includes('/api/v1/contracts/'))!
    expect(listCall).toContain('region_ids=10000002&region_ids=10000020')
  })

  it('redirects an out-of-range page to the last page instead of a false empty state', async () => {
    // A shared ?page=9 URL past the last page: the backend echoes {total>0,
    // items:[]} without clamping. The app must navigate to the last valid page
    // and render the row — never the contradictory "no contracts match" card
    // (which the "30 matching" header would flatly contradict).
    stubFetch(
      anonymousMe((url) =>
        url.includes('page=9')
          ? jsonResponse({ total: 30, page: 9, size: 50, items: [] })
          : jsonResponse({ total: 30, page: 1, size: 50, items: [CONTRACT] }),
      ),
    )

    const { router } = renderApp('/contracts?page=9')

    expect(await screen.findByText('Tristan')).toBeInTheDocument()
    await waitFor(() => expect(router.state.location.search).toMatchObject({ page: 1 }))
    expect(screen.queryByText(/no contracts match/i)).not.toBeInTheDocument()
  })

  it('resets to page 1 when a filter changes', async () => {
    const calls = stubFetch(
      anonymousMe(() => jsonResponse({ total: 200, page: 3, size: 50, items: [CONTRACT] })),
    )

    const { router } = renderApp('/contracts?page=3')
    await screen.findByText('Tristan')

    await userEvent.click(screen.getByLabelText(/blueprint copies only/i))

    await waitFor(() => expect(router.state.location.search).toMatchObject({ page: 1 }))
    // Router state updates before TanStack Query issues the refetch — the
    // request assertions must also wait (TEST-2: fix the sync, never weaken).
    await waitFor(() => {
      expect(calls.at(-1)).toContain('is_bpc=true')
      expect(calls.at(-1)).toContain('page=1')
    })
  })
})

describe('ContractDetailPage', () => {
  it('renders a contract with its items', async () => {
    stubFetch(anonymousMe(() => jsonResponse(CONTRACT)))

    renderApp('/contracts/101')

    // Heading is hull-first; the seller's title renders as a quoted subtitle.
    expect(await screen.findByRole('heading', { name: 'Tristan' })).toBeInTheDocument()
    expect(screen.getByText(/Tristan for Sale/)).toBeInTheDocument()
    // The list item renders as "1× Tristan" across text nodes — match the
    // full normalized text, not the bare name (which also appears in the h1).
    expect(screen.getByText(/1× Tristan/)).toBeInTheDocument()
    expect(screen.getByText(/jita/i)).toBeInTheDocument()
    // Detail title carries the hull name (WCAG 2.4.2 / shareable-URL principle).
    expect(document.title).toBe('Tristan — Hangar Bay')
  })

  it('heads with the item name when the title is blank, and "Contract <id>" as last resort', async () => {
    // Hull-first heading (primaryLabel): item name beats the seller title,
    // and the blank-"" ESI-title trap still falls through to the id when no
    // item name resolves (M1 acceptance discovery, preserved).
    const untitled = { ...CONTRACT, contract_id: 777, title: '' }
    stubFetch(anonymousMe(() => jsonResponse(untitled)))
    const named = renderApp('/contracts/777')
    expect(await screen.findByRole('heading', { name: 'Tristan' })).toBeInTheDocument()
    named.unmount()
    vi.unstubAllGlobals()

    const bare = {
      ...CONTRACT,
      contract_id: 778,
      title: '',
      items: [{ ...CONTRACT.items[0], type_name: null }],
    }
    stubFetch(anonymousMe(() => jsonResponse(bare)))
    renderApp('/contracts/778')
    expect(await screen.findByRole('heading', { name: 'Contract 778' })).toBeInTheDocument()
  })

  it('shows not-found for a 404', async () => {
    stubFetch(anonymousMe(() => jsonResponse({ detail: 'Contract not found' }, 404)))

    renderApp('/contracts/999')

    expect(await screen.findByText(/not found/i)).toBeInTheDocument()
    expect(document.title).toBe('Contract not found — Hangar Bay')
  })

  it('shows not-found for a non-numeric id without issuing a request', async () => {
    // /contracts/abc -> Number('abc') -> NaN. The component's NaN guard must
    // short-circuit to NotFound; useContract(NaN) is a disabled query, so no
    // request should ever leave. Locks both the NotFound rendering and the
    // no-wasted-request behavior — if the guard is reordered below the
    // isPending branch, the disabled query's isPending stays true forever and
    // this page would render an eternal "Loading contract…" instead.
    const calls = stubFetch(anonymousMe(() => jsonResponse(CONTRACT)))

    renderApp('/contracts/abc')

    expect(await screen.findByText(/not found/i)).toBeInTheDocument()
    // The guarded behavior is "no CONTRACTS request" — the header's own /me
    // request is expected and unrelated to the NaN-guard this test pins.
    expect(calls.filter((u) => !u.includes('/api/v1/me'))).toHaveLength(0)
  })

  it('back link restores the exact list filter/sort state via history when navigated in-app', async () => {
    // Detail is reached from a FILTERED list, so the back link must return to
    // that list with every URL param intact (PRODUCT #2: the URL is the
    // interface). It uses router.history.back() when the list is behind us,
    // rather than a bare to="/contracts" that would reset to defaults.
    stubFetch(
      anonymousMe((url) =>
        /\/contracts\/\d+/.test(url)
          ? jsonResponse(CONTRACT)
          : jsonResponse({ total: 1, page: 1, size: 50, items: [CONTRACT] }),
      ),
    )

    const { router } = renderApp(
      '/contracts?is_bpc=true&sort_by=price&sort_direction=asc&ships_only=false',
    )

    await userEvent.click(await screen.findByRole('link', { name: 'Tristan' }))
    await screen.findByRole('heading', { name: 'Tristan' })
    expect(router.state.location.pathname).toBe('/contracts/101')

    await userEvent.click(screen.getByRole('button', { name: /all contracts/i }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/contracts'))
    expect(router.state.location.search).toMatchObject({
      is_bpc: true,
      sort_by: 'price',
      sort_direction: 'asc',
      ships_only: false,
    })
  })

  it('back link falls back to the default list on a cold deep link (no in-app history)', async () => {
    // A shared /contracts/$id opened fresh has nothing behind it, so the back
    // control is a plain link to the list rather than a history button.
    stubFetch(anonymousMe(() => jsonResponse(CONTRACT)))

    renderApp('/contracts/101')

    await screen.findByRole('heading', { name: 'Tristan' })
    const back = screen.getByRole('link', { name: /all contracts/i })
    expect(back).toHaveAttribute('href', '/contracts')
  })
})
