import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { jsonResponse } from '../../../test/http'
import { parseContractSearch } from '../filters'
import { useContracts } from './useContracts'
import { useContract } from './useContract'
import { useTaxonomy } from './useTaxonomy'

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

describe('useContract retry policy', () => {
  // retryDelay is flattened so the assertion is about the retry COUNT rather than
  // about how long the backoff makes the test wait; `retry` is deliberately left
  // to the hook, which is the thing under test.
  function retryWrapper({ children }: { children: ReactNode }) {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retryDelay: 0 } } })
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }

  it('retries a non-404 detail failure exactly once', async () => {
    // `failureCount < 1` means one retry, not none and not the library default of
    // three. A 500 on a detail page is usually transient; three attempts against a
    // genuinely down backend is three times the load for the same failure.
    let calls = 0
    vi.stubGlobal('fetch', async () => {
      calls += 1
      return new Response('', { status: 500 })
    })

    const { result } = renderHook(() => useContract(101), { wrapper: retryWrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(calls).toBe(2) // the initial attempt plus exactly one retry
  })

  it('never retries a 404, which is an answer rather than a failure', async () => {
    let calls = 0
    vi.stubGlobal('fetch', async () => {
      calls += 1
      return new Response('', { status: 404 })
    })

    const { result } = renderHook(() => useContract(999), { wrapper: retryWrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(calls).toBe(1)
  })
})

describe('useTaxonomy polling', () => {
  it('re-polls readiness on its own, so a not-ready surface recovers unattended', async () => {
    // Decision-log D1: the item surface "degrades on its own" — a corpus that
    // finishes enriching must light the item filters up without a reload. That is
    // refetchInterval and nothing else; delete it and the app stays not-ready until
    // the reader navigates. Nothing asserted it.
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      let taxonomyCalls = 0
      vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
        const url =
          typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
        if (/\/contracts\/taxonomy$/.test(url)) {
          taxonomyCalls += 1
          return jsonResponse({ categories: [], groups: [], coverage: null })
        }
        return jsonResponse(PAGE)
      })

      const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
      const wrap = ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      )
      const { result } = renderHook(() => useTaxonomy(), { wrapper: wrap })

      await waitFor(() => expect(result.current.isSuccess).toBe(true))
      expect(taxonomyCalls).toBe(1)

      // Just short of the poll interval nothing more has been asked for...
      await vi.advanceTimersByTimeAsync(5 * 60_000 - 1_000)
      expect(taxonomyCalls).toBe(1)

      // ...and past it, the probe goes again with no interaction at all.
      await vi.advanceTimersByTimeAsync(2_000)
      await waitFor(() => expect(taxonomyCalls).toBe(2))
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('search freezing and field-wise search equality', () => {
  it('converges when the caller hands it a fresh search object every render', async () => {
    // The route's validateSearch builds a NEW ContractSearch (and new id arrays) on
    // every render, so `sameSearch` has to compare by VALUE. Compare the id lists by
    // reference instead and the adjust-state-during-render below fires on every pass,
    // which React reports as "Too many re-renders" — a hard crash of the app's main
    // view that nothing in the suite reproduced.
    const calls = stubFetch(() => jsonResponse(PAGE))
    const { result, rerender } = renderHook(
      () => useContracts(parseContractSearch({ region_ids: [10000002, 10000043] })),
      { wrapper },
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    const settled = calls.filter((url) => listCall([url])).length

    rerender()
    rerender()
    rerender()

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    // Equal-by-value lists in fresh arrays must not look like a changed query.
    expect(calls.filter((url) => listCall([url])).length).toBe(settled)
  })

  it('treats a NaN bound as equal to itself, per Object.is', async () => {
    // Defence in depth: the parser sanitizes NaN away, so this is unreachable from
    // the address bar today. It is asserted because the comparison is written with
    // Object.is specifically — swapping in `!==` makes NaN perpetually unequal to
    // itself and reintroduces the render loop above by a different route.
    const calls = stubFetch(() => jsonResponse(PAGE))
    const withNaN = { ...parseContractSearch({}), min_price: Number.NaN }
    const { result, rerender } = renderHook(() => useContracts({ ...withNaN }), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    const settled = calls.filter((url) => listCall([url])).length
    rerender()
    rerender()

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls.filter((url) => listCall([url])).length).toBe(settled)
  })

  it('folds a sort click during the debounce window into the settled request', async () => {
    // Documented behaviour (useContracts.ts): while the text is mid-edit the WHOLE
    // effective query freezes, so an independent control click does not fire a
    // request under the OLD text and then a second under the new one. Nothing
    // asserted it, so a regression that unfroze the non-search params would double
    // every mid-word sort click into two corpus-scale requests.
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      const calls = stubFetch(() => jsonResponse(PAGE))
      const listCalls = () => calls.filter((url) => listCall([url])).length

      const { result, rerender } = renderHook(
        ({ raw }: { raw: Record<string, unknown> }) => useContracts(parseContractSearch(raw)),
        { wrapper, initialProps: { raw: { search: 'rifter' } as Record<string, unknown> } },
      )
      await waitFor(() => expect(result.current.isSuccess).toBe(true))
      const beforeTyping = listCalls()
      expect(beforeTyping).toBeGreaterThan(0)

      // A keystroke opens the window...
      rerender({ raw: { search: 'rifterr' } })
      // ...and a sort click lands inside it.
      rerender({ raw: { search: 'rifterr', sort_by: 'price' } })

      // Frozen: neither the new text nor the new sort has been requested yet.
      await vi.advanceTimersByTimeAsync(100)
      expect(listCalls()).toBe(beforeTyping)

      // Once the text settles, ONE request carries both changes.
      await vi.advanceTimersByTimeAsync(400)
      await waitFor(() => expect(listCalls()).toBe(beforeTyping + 1))
      const last = calls.filter((url) => listCall([url])).at(-1)!
      expect(last).toContain('search=rifterr')
      expect(last).toContain('sort_by=price')
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('lastSettled tracks the newest settled search', () => {
  it('freezes against the LATEST settled search, not a stale one', async () => {
    // sameSearch wrongly reporting two unequal searches as equal is invisible to the
    // fresh-object test (which only proves equal-by-value converges) AND to a
    // call-count assertion: reverting to an earlier query key is served from the
    // react-query cache with no fetch at all. So this asserts on DATA — the responder
    // echoes the requested size into `total`, making the effective query observable.
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      stubFetch((url) => {
        const size = Number(new URL(url, 'http://x').searchParams.get('size') ?? 50)
        return jsonResponse({ ...PAGE, total: size })
      })

      const { result, rerender } = renderHook(
        ({ raw }: { raw: Record<string, unknown> }) => useContracts(parseContractSearch(raw)),
        { wrapper, initialProps: { raw: { search: 'rifter' } as Record<string, unknown> } },
      )
      await waitFor(() => expect(result.current.data?.total).toBe(50))

      // Settled: the new size is requested immediately and must be RECORDED.
      rerender({ raw: { search: 'rifter', size: 25 } })
      await waitFor(() => expect(result.current.data?.total).toBe(25))

      // Now type. The query freezes — and it must freeze at size=25. A lastSettled
      // that stopped advancing would fall back to the initial search and the rows
      // would revert to the size=50 page underneath the reader mid-word.
      rerender({ raw: { search: 'rifterr', size: 25 } })
      await vi.advanceTimersByTimeAsync(100)
      expect(result.current.data?.total).toBe(25)

      await vi.advanceTimersByTimeAsync(400)
      await waitFor(() => expect(result.current.data?.total).toBe(25))
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('sameSearch array comparison', () => {
  // The id lists are compared length-then-elementwise. Each transition below breaks a
  // DIFFERENT clause, and all three are invisible to an equal-arrays test:
  //   append      -> defeats `left.length !== right.length` alone
  //   substitute  -> defeats `left.some(...)` alone
  //   clear       -> defeats the Array.isArray(left) && Array.isArray(right) guard,
  //                  where one side becomes undefined
  // A clause that stops discriminating makes lastSettled miss the change, so the next
  // mid-word edit freezes the rows against a filter the reader has already left.
  it.each([
    { label: 'an appended id (length)', next: [10000002, 10000043], expected: [10000002, 10000043] },
    { label: 'a substituted id (element)', next: [10000043], expected: [10000043] },
    { label: 'a reordered, sum-preserving pair', next: [10000043, 10000002], expected: [10000043, 10000002] },
    { label: 'a cleared list (array vs undefined)', next: undefined, expected: [] },
  ])('records $label as a change and freezes against it', async ({ next, expected }) => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      // The responder echoes the ORDERED region_ids the request carried, so the
      // effective query is observable through data. Deliberately the exact list and
      // not a digest of it: a count cannot see a same-length substitution, and a sum
      // cannot see a reorder or any swap that preserves the total ([1,4] vs [2,3]).
      // Every lossy observable admits a comparator that is wrong in exactly the way
      // the observable is blind to (TEST-25). A call-count assertion is blinder
      // still — reverting to an earlier key is served from the react-query cache
      // with no fetch at all.
      stubFetch((url) => {
        const regions = new URL(url, 'http://x').searchParams.getAll('region_ids').map(Number)
        return jsonResponse({ ...PAGE, coverage: { ...PAGE.coverage, ingested_region_ids: regions } })
      })

      const { result, rerender } = renderHook(
        ({ raw }: { raw: Record<string, unknown> }) => useContracts(parseContractSearch(raw)),
        {
          wrapper,
          initialProps: {
            raw: { search: 'rifter', region_ids: [10000002] } as Record<string, unknown>,
          },
        },
      )
      const observed = () => result.current.data?.coverage.ingested_region_ids
      await waitFor(() => expect(observed()).toEqual([10000002]))

      // Settled: the changed list is requested and must be RECORDED as the new settled.
      rerender({ raw: { search: 'rifter', region_ids: next } })
      await waitFor(() => expect(observed()).toEqual(expected))

      // Now type. The freeze must hold the NEW list, not revert to the original.
      rerender({ raw: { search: 'rifterr', region_ids: next } })
      await vi.advanceTimersByTimeAsync(100)
      expect(observed()).toEqual(expected)

      await vi.advanceTimersByTimeAsync(400)
      await waitFor(() => expect(observed()).toEqual(expected))
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('sameSearch resists digest-shaped comparators', () => {
  it('records a length- AND sum-preserving id swap as a change', async () => {
    // [A, D] -> [B, C] with A+D === B+C and both length 2. Every digest a plausible
    // "cheap" comparator might use — length, sum, or both — is identical across this
    // transition, so only a genuine elementwise comparison sees it. The parametrized
    // cases above cannot reach this shape because each changes the length.
    //
    // The FREEZE is the discriminator, not the settled request: while settled the
    // hook reads the live search either way, so a comparator that wrongly reported
    // "equal" only reveals itself once lastSettled has to supply the frozen query.
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      stubFetch((url) => {
        const regions = new URL(url, 'http://x').searchParams.getAll('region_ids').map(Number)
        return jsonResponse({ ...PAGE, coverage: { ...PAGE.coverage, ingested_region_ids: regions } })
      })

      const before = [10000001, 10000004]
      const after = [10000002, 10000003] // same length, same sum, different elements

      const { result, rerender } = renderHook(
        ({ raw }: { raw: Record<string, unknown> }) => useContracts(parseContractSearch(raw)),
        {
          wrapper,
          initialProps: { raw: { search: 'rifter', region_ids: before } as Record<string, unknown> },
        },
      )
      const observed = () => result.current.data?.coverage.ingested_region_ids
      await waitFor(() => expect(observed()).toEqual(before))

      rerender({ raw: { search: 'rifter', region_ids: after } })
      await waitFor(() => expect(observed()).toEqual(after))

      // Type: the frozen query must be the swapped list, not the original.
      rerender({ raw: { search: 'rifterr', region_ids: after } })
      await vi.advanceTimersByTimeAsync(100)
      expect(observed()).toEqual(after)

      await vi.advanceTimersByTimeAsync(400)
      await waitFor(() => expect(observed()).toEqual(after))
    } finally {
      vi.useRealTimers()
    }
  })
})
