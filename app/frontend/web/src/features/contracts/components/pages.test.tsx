import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse } from '../../../test/http'
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
    stubFetch(() => jsonResponse({ total: 1, page: 1, size: 50, items: [CONTRACT] }))

    renderApp('/contracts')

    expect(await screen.findByText('Tristan')).toBeInTheDocument()
    expect(screen.getByText(/1,000,000/)).toBeInTheDocument()
  })

  it('shows the empty state for zero results', async () => {
    stubFetch(() => jsonResponse({ total: 0, page: 1, size: 50, items: [] }))

    renderApp('/contracts')

    expect(await screen.findByText(/no contracts match/i)).toBeInTheDocument()
  })

  it('shows the error state with a retry control on failure', async () => {
    stubFetch(() => jsonResponse({ detail: 'boom' }, 500))

    renderApp('/contracts')

    expect(await screen.findByRole('alert')).toHaveTextContent(/failed to load/i)
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('reads filters from the URL and sends them to the API', async () => {
    const calls = stubFetch(() =>
      jsonResponse({ total: 0, page: 1, size: 50, items: [] }),
    )

    renderApp('/contracts?region_ids=10000002&is_bpc=true&sort_by=price&sort_direction=asc')

    await screen.findByText(/no contracts match/i)
    expect(calls[0]).toContain('region_ids=10000002')
    expect(calls[0]).toContain('is_bpc=true')
    expect(calls[0]).toContain('sort_by=price')
  })

  it('resets to page 1 when a filter changes', async () => {
    const calls = stubFetch(() =>
      jsonResponse({ total: 200, page: 3, size: 50, items: [CONTRACT] }),
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
    stubFetch(() => jsonResponse(CONTRACT))

    renderApp('/contracts/101')

    expect(await screen.findByText('Tristan for Sale')).toBeInTheDocument()
    // The list item renders as "1× Tristan" across text nodes — match the
    // full normalized text, not the bare name (which also appears in the h1).
    expect(screen.getByText(/1× Tristan/)).toBeInTheDocument()
    expect(screen.getByText(/jita/i)).toBeInTheDocument()
  })

  it('shows not-found for a 404', async () => {
    stubFetch(() => jsonResponse({ detail: 'Contract not found' }, 404))

    renderApp('/contracts/999')

    expect(await screen.findByText(/not found/i)).toBeInTheDocument()
  })
})
