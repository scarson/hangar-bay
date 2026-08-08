import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { jsonResponse } from '../../../test/http'
import { parseContractSearch } from '../filters'
import { useContracts } from './useContracts'
import { useContract } from './useContract'
import { useItemSurfaceRefresh, useTaxonomy } from './useTaxonomy'

const PAGE = {
  total: 1,
  page: 1,
  size: 50,
  items: [
    {
      contract_id: 101,
      issuer_id: 1,
      issuer_corporation_id: 101,
      start_location_id: 60003760,
      collateral: 0,
      type: 'item_exchange',
      title: 'Tristan for Sale',
      for_corporation: false,
      date_issued: '2026-07-01T00:00:00Z',
      date_expired: '2026-07-08T00:00:00Z',
      price: 1000000,
      is_ship_contract: true,
      is_blueprint_copy_contract: false,
      primary_label: 'Tristan',
      composition: null,
    },
  ],
  segment_counts: { item_exchange: 1, auction: 0, courier: 0, loan: 0, unknown: 0 },
  coverage: { ingested_region_ids: [10000002], as_of: null },
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

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useContracts', () => {
  it('fetches a page and exposes the data', async () => {
    const calls = stubFetch(() => jsonResponse(PAGE))

    const { result } = renderHook(() => useContracts(parseContractSearch({})), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.total).toBe(1)
    expect(result.current.data?.items[0]?.contract_id).toBe(101)
    expect(calls[0]).toContain('/api/v1/contracts/?')
  })

  it('never sends a sub-3-char search', async () => {
    const calls = stubFetch(() => jsonResponse(PAGE))

    const { result } = renderHook(
      () => useContracts(parseContractSearch({ search: 'ab' })),
      { wrapper },
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls[0]).not.toContain('search')
  })

  it('surfaces server errors as isError', async () => {
    stubFetch(() => jsonResponse({ detail: 'boom' }, 500))

    const { result } = renderHook(() => useContracts(parseContractSearch({})), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

describe('useContract', () => {
  it('fetches a single contract by id', async () => {
    const calls = stubFetch(() => jsonResponse(PAGE.items[0]))

    const { result } = renderHook(() => useContract(101), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.contract_id).toBe(101)
    expect(calls[0]).toContain('/api/v1/contracts/101')
  })

  it('exposes a 404 as an ApiError without retrying', async () => {
    const calls = stubFetch(() => jsonResponse({ detail: 'Contract not found' }, 404))

    const { result } = renderHook(() => useContract(999), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(calls).toHaveLength(1)
  })
})

/**
 * The readiness signal's two freshness properties. Both were review findings:
 * `staleTime` alone never refetches, and a readiness flip left the rows it now
 * describes untouched in the cache.
 */
describe('useItemSurfaceRefresh', () => {
  const TAXONOMY = (coverage: string) => ({ categories: [], groups: [], coverage })

  function harness(coverageRef: { value: string }) {
    const counts = { list: 0, taxonomy: 0 }
    vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
      const url =
        typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
      if (/\/contracts\/taxonomy$/.test(url)) {
        counts.taxonomy += 1
        return jsonResponse(TAXONOMY(coverageRef.value))
      }
      counts.list += 1
      return jsonResponse(PAGE)
    })
    return counts
  }

  it('leaves the rows alone when readiness first arrives, and refetches them when it changes', async () => {
    const coverage = { value: 'partial' }
    const counts = harness(coverage)
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const wrap = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )

    const { result } = renderHook(
      () => {
        useItemSurfaceRefresh()
        return useContracts(parseContractSearch({}))
      },
      { wrapper: wrap },
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    // undefined -> partial is the first answer of the session, not a change.
    // Treating it as one would cost a second corpus-scale list request on every
    // cold load — the expense decision D13 weighed and refused.
    await waitFor(() => expect(counts.taxonomy).toBeGreaterThan(0))
    expect(counts.list).toBe(1)

    coverage.value = 'complete'
    await queryClient.refetchQueries({ queryKey: ['contracts', 'taxonomy'] })

    // partial -> complete IS a change: the rows on screen were fetched from a
    // corpus that has since been enriched, and the columns now describing them
    // would otherwise show a BPC badge beside empty Runs/ME/TE cells.
    await waitFor(() => expect(counts.list).toBe(2))
  })

  it('polls the readiness endpoint, because staleness alone never refetches', async () => {
    // `staleTime` marks data stale without scheduling anything, so a tab left
    // open across an ENRICHMENT_VERSION resweep would keep reporting the old
    // answer for the whole ~80 minutes it is false.
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      const coverage = { value: 'complete' }
      const counts = harness(coverage)
      const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
      const wrap = ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      )

      renderHook(() => useTaxonomy(), { wrapper: wrap })
      await waitFor(() => expect(counts.taxonomy).toBe(1))

      await vi.advanceTimersByTimeAsync(5 * 60_000 + 1_000)

      await waitFor(() => expect(counts.taxonomy).toBeGreaterThan(1))
    } finally {
      vi.useRealTimers()
    }
  })
})
