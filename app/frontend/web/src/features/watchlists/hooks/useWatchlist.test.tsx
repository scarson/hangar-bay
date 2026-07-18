// ABOUTME: useWatchlist hook contracts — list query + add/update/remove mutations at the fetch seam.
// ABOUTME: Asserts URL/method/body incl. the clear-to-null PUT ({max_price: null}); only 2xx invalidates ['watchlists']; 401 also invalidates ['auth','me'].
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useWatchlist, useAddWatchlistItem, useUpdateWatchlistItem, useRemoveWatchlistItem } from './useWatchlist'

interface Call { url: string; method?: string; body?: string }
function stubFetch(handler: (call: Call) => Response): Call[] {
  const calls: Call[] = []
  vi.stubGlobal('fetch', async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input as Request
    const call: Call = { url: req.url ?? String(input), method: req.method ?? init?.method, body: await req.clone().text() }
    calls.push(call)
    return handler(call)
  })
  return calls
}
function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const spy = vi.spyOn(qc, 'invalidateQueries')
  const wrapper = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  return { spy, wrapper }
}
afterEach(() => vi.unstubAllGlobals())

describe('useWatchlist (query)', () => {
  it('GETs /api/v1/me/watchlist-items/ and returns the array', async () => {
    const rows = [{ id: 1, type_id: 587, type_name: 'Rifter', max_price: null, notes: null, created_at: 'x', updated_at: 'x' }]
    const calls = stubFetch(() => new Response(JSON.stringify(rows), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const { wrapper } = wrap()
    const { result } = renderHook(() => useWatchlist(), { wrapper })
    await waitFor(() => expect(result.current.data).toHaveLength(1))
    expect(calls[0].url).toContain('/api/v1/me/watchlist-items/')
  })

  it('invalidates ["auth","me"] when the query 401s', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'unauth' }), { status: 401, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useWatchlist(), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).toHaveBeenCalledWith({ queryKey: ['auth', 'me'] })
  })
})

describe('useAddWatchlistItem', () => {
  it('POSTs the body and invalidates on 201', async () => {
    const calls = stubFetch(() => new Response(JSON.stringify({ id: 2, type_id: 587, type_name: 'Rifter', max_price: null, notes: null, created_at: 'x', updated_at: 'x' }), { status: 201, headers: { 'Content-Type': 'application/json' } }))
    const { spy, wrapper } = wrap()
    const { result } = renderHook(() => useAddWatchlistItem(), { wrapper })
    result.current.mutate({ type_id: 587 })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls[0].url).toContain('/api/v1/me/watchlist-items/')
    expect(calls[0].method).toBe('POST')
    expect(JSON.parse(calls[0].body!)).toEqual({ type_id: 587 })
    expect(spy).toHaveBeenCalledWith({ queryKey: ['watchlists'] })
  })

  it('surfaces a 409 without invalidating', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'dup' }), { status: 409, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useAddWatchlistItem(), { wrapper })
    result.current.mutate({ type_name: 'Rifter' })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).not.toHaveBeenCalledWith({ queryKey: ['watchlists'] })
  })

  it('invalidates ["auth","me"] on a 401', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'unauth' }), { status: 401, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useAddWatchlistItem(), { wrapper })
    result.current.mutate({ type_id: 1 })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).toHaveBeenCalledWith({ queryKey: ['auth', 'me'] })
  })
})

describe('useUpdateWatchlistItem', () => {
  it('PUTs {max_price: null} to clear (JSON null, not dropped)', async () => {
    const calls = stubFetch(() => new Response(JSON.stringify({ id: 3, type_id: 1, type_name: 'x', max_price: null, notes: 'keep', created_at: 'x', updated_at: 'x' }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const { spy, wrapper } = wrap()
    const { result } = renderHook(() => useUpdateWatchlistItem(), { wrapper })
    result.current.mutate({ id: 3, body: { max_price: null, notes: 'keep' } })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls[0].url).toContain('/api/v1/me/watchlist-items/3')
    expect(calls[0].method).toBe('PUT')
    const parsed = JSON.parse(calls[0].body!)
    expect(parsed).toHaveProperty('max_price', null)
    expect(parsed.notes).toBe('keep')
    expect(spy).toHaveBeenCalledWith({ queryKey: ['watchlists'] })
  })
})

describe('useRemoveWatchlistItem', () => {
  it('DELETEs the item route and invalidates on 204', async () => {
    const calls = stubFetch(() => new Response(null, { status: 204 }))
    const { spy, wrapper } = wrap()
    const { result } = renderHook(() => useRemoveWatchlistItem(), { wrapper })
    result.current.mutate(4)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls[0].url).toContain('/api/v1/me/watchlist-items/4')
    expect(calls[0].method).toBe('DELETE')
    expect(spy).toHaveBeenCalledWith({ queryKey: ['watchlists'] })
  })
})
