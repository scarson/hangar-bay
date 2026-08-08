import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { jsonResponse } from '../../../test/http'
import { parseContractSearch } from '../filters'
import { useContracts } from './useContracts'
import { useContract } from './useContract'

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

/**
 * The contract-LIST request among the captured calls. The list now waits for
 * the taxonomy answer (readiness must be known before rows are fetched, so it
 * can travel with them — WEB-1), so the taxonomy call comes FIRST and an
 * index-based assertion would read the wrong request.
 */
function listCall(calls: string[]): string | undefined {
  return calls.find((url) => /\/api\/v1\/contracts\/\?/.test(url))
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
    expect(listCall(calls)).toBeDefined()
    // Ordering is part of the contract now: nothing is fetched until readiness
    // is known, so the taxonomy request precedes the list request.
    expect(calls[0]).toContain('/api/v1/contracts/taxonomy')
  })

  it('never sends a sub-3-char search', async () => {
    const calls = stubFetch(() => jsonResponse(PAGE))

    const { result } = renderHook(
      () => useContracts(parseContractSearch({ search: 'ab' })),
      { wrapper },
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(listCall(calls)).toBeDefined()
    expect(listCall(calls)).not.toContain('search')
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
/**
 * The readiness signal's freshness properties, both of them review findings:
 * `staleTime` alone never refetches, and a readiness change has to start a NEW
 * list query rather than try to redirect the one in flight.
 */
describe('readiness and the rows', () => {
  const TAXONOMY = (coverage: string) => ({ categories: [], groups: [], coverage })

  function harness(coverageRef: { value: string }, holdList = false) {
    const counts = { list: 0, taxonomy: 0 }
    const captured: boolean[] = []
    let releaseList: (() => void) | undefined
    vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
      const url =
        typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
      if (/\/contracts\/taxonomy$/.test(url)) {
        counts.taxonomy += 1
        return jsonResponse(TAXONOMY(coverageRef.value))
      }
      counts.list += 1
      if (holdList && counts.list === 1) {
        return new Promise<Response>((resolve) => {
          releaseList = () => resolve(jsonResponse(PAGE))
        })
      }
      return jsonResponse(PAGE)
    })
    return { counts, captured, release: () => releaseList?.() }
  }

  const wrapperFor = (queryClient: QueryClient) =>
    function Wrap({ children }: { children: ReactNode }) {
      return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    }

  it('fetches once on a cold load, then refetches when readiness changes', async () => {
    const coverage = { value: 'partial' }
    const { counts } = harness(coverage)
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })

    const { result } = renderHook(() => useContracts(parseContractSearch({})), {
      wrapper: wrapperFor(queryClient),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    // Readiness is in the key, but the list waits for it, so the key never
    // moves from unknown to known and a cold load costs ONE list request.
    expect(counts.list).toBe(1)
    expect(result.current.data?.itemSurfaceReady).toBe(false)

    coverage.value = 'complete'
    await queryClient.refetchQueries({ queryKey: ['contracts', 'taxonomy'] })

    await waitFor(() => expect(result.current.data?.itemSurfaceReady).toBe(true))
    expect(counts.list).toBe(2)
  })

  it('never lands a response under a readiness that changed while it was in flight', async () => {
    // Invalidation alone could not fix this: for a key with no cached data yet,
    // React Query reuses the in-flight promise, so the response landed carrying
    // the value captured BEFORE the change, with nothing left to correct it.
    // Keying on readiness starts a genuinely new query instead.
    const coverage = { value: 'complete' }
    const { counts, release } = harness(coverage, true)
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })

    const { result } = renderHook(() => useContracts(parseContractSearch({})), {
      wrapper: wrapperFor(queryClient),
    })

    await waitFor(() => expect(counts.list).toBe(1))

    // The corpus regresses mid-request (a future ENRICHMENT_VERSION resweep).
    coverage.value = 'partial'
    await queryClient.refetchQueries({ queryKey: ['contracts', 'taxonomy'] })
    release()

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    // Whatever is on screen must describe itself as partial. The stale `true`
    // must never be what the rows are rendered under.
    expect(result.current.data?.itemSurfaceReady).toBe(false)
  })
})

describe('useTaxonomy timeout', () => {
  it('gives up on an unanswered readiness probe so the list is never held hostage', async () => {
    // The list waits for a readiness answer so it can capture one with its rows
    // (WEB-1). An ERROR is an answer and unblocks it; a request that neither
    // resolves nor rejects would not, and would leave the app's core view on
    // its skeleton for as long as the connection stayed open. The abort turns
    // that into a bounded wait.
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      let listCalls = 0
      vi.stubGlobal('fetch', async (input: RequestInfo | URL, init?: RequestInit) => {
        const url =
          typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
        if (/\/contracts\/taxonomy$/.test(url)) {
          const signal = (input as Request).signal ?? init?.signal
          // Never resolves on its own — only the abort ends it.
          return new Promise<Response>((_resolve, reject) => {
            signal?.addEventListener('abort', () => reject(new Error('aborted')))
          })
        }
        listCalls += 1
        return jsonResponse(PAGE)
      })

      // retry:1 is the PRODUCTION default, deliberately used here: the taxonomy
      // query sets retry:false itself, so the five-second bound has to hold
      // even when the surrounding client would otherwise retry. Without that,
      // a hang costs two attempts plus the retry delay before the rows can be
      // fetched, and the bound the comment states would be false.
      const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1 } } })
      const wrap = ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      )
      const { result } = renderHook(() => useContracts(parseContractSearch({})), { wrapper: wrap })

      expect(listCalls).toBe(0)

      await vi.advanceTimersByTimeAsync(6_000)

      await waitFor(() => expect(result.current.isSuccess).toBe(true))
      expect(listCalls).toBe(1)
    } finally {
      vi.useRealTimers()
    }
  })
})
