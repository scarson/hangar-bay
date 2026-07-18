// ABOUTME: useSavedSearches hook contracts — query + create/rename/delete mutations at the fetch seam.
// ABOUTME: Asserts URL/method/body (TEST-5) and that only 2xx invalidates ['savedSearches']; 401 also invalidates ['auth','me'].
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  useSavedSearches,
  useCreateSavedSearch,
  useRenameSavedSearch,
  useDeleteSavedSearch,
} from './useSavedSearches'

interface Call {
  url: string
  method?: string
  body?: string
}

function stubFetch(handler: (call: Call) => Response): Call[] {
  const calls: Call[] = []
  vi.stubGlobal('fetch', async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input as Request
    const call: Call = {
      url: req.url ?? String(input),
      method: req.method ?? init?.method,
      body: typeof (req as Request).text === 'function' ? await req.clone().text() : undefined,
    }
    calls.push(call)
    return handler(call)
  })
  return calls
}

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const spy = vi.spyOn(qc, 'invalidateQueries')
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
  return { qc, spy, wrapper }
}

afterEach(() => vi.unstubAllGlobals())

const AUTHED = { character_id: 91000001, character_name: 'Sesta Hound' }
const meResponse = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

describe('useSavedSearches (query)', () => {
  it('GETs /api/v1/me/saved-searches/ for the authed identity and returns the array', async () => {
    const rows = [{ id: 1, name: 'A', search_parameters: { ships_only: true, size: 50, sort_by: 'date_issued', sort_direction: 'desc' }, created_at: '2026-07-17T00:00:00Z', updated_at: '2026-07-17T00:00:00Z' }]
    const calls = stubFetch((call) =>
      /\/api\/v1\/me$/.test(call.url) ? meResponse(200, AUTHED) : meResponse(200, rows),
    )
    const { qc, wrapper } = wrap()
    const { result } = renderHook(() => useSavedSearches(), { wrapper })
    await waitFor(() => expect(result.current.data).toHaveLength(1))
    const domain = calls.find((c) => /\/me\/saved-searches\//.test(c.url))!
    expect(domain.url).toContain('/api/v1/me/saved-searches/')
    expect(domain.method ?? 'GET').toBe('GET')
    expect(result.current.data![0].name).toBe('A')
    // Identity-scoped key: the list caches under the character id so a session swap can't
    // resolve one identity's data under another's key (finding 1).
    expect(qc.getQueryData(['savedSearches', 'list', AUTHED.character_id])).toHaveLength(1)
  })

  it('does not fetch while anonymous (enabled gates on the identity)', async () => {
    const calls = stubFetch((call) =>
      /\/api\/v1\/me$/.test(call.url) ? meResponse(401, { detail: 'unauthenticated' }) : meResponse(200, []),
    )
    const { wrapper } = wrap()
    const { result } = renderHook(() => useSavedSearches(), { wrapper })
    await waitFor(() => expect(calls.some((c) => /\/api\/v1\/me$/.test(c.url))).toBe(true))
    expect(result.current.fetchStatus).toBe('idle')
    expect(result.current.data).toBeUndefined()
    expect(calls.some((c) => /\/me\/saved-searches\//.test(c.url))).toBe(false)
  })

  it('invalidates ["auth","me"] when the query 401s', async () => {
    const { spy, wrapper } = wrap()
    stubFetch((call) =>
      /\/api\/v1\/me$/.test(call.url) ? meResponse(200, AUTHED) : meResponse(401, { detail: 'unauthenticated' }),
    )
    const { result } = renderHook(() => useSavedSearches(), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).toHaveBeenCalledWith({ queryKey: ['auth', 'me'] })
  })
})

describe('useCreateSavedSearch', () => {
  const body = { name: 'Cheap frigates', search_parameters: { ships_only: true, size: 50, sort_by: 'price', sort_direction: 'asc' } } as const

  it('POSTs the body and invalidates ["savedSearches"] on 201', async () => {
    const calls = stubFetch(() => new Response(JSON.stringify({ id: 9, ...body, created_at: 'x', updated_at: 'x' }), { status: 201, headers: { 'Content-Type': 'application/json' } }))
    const { spy, wrapper } = wrap()
    const { result } = renderHook(() => useCreateSavedSearch(), { wrapper })
    result.current.mutate(body)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls[0].url).toContain('/api/v1/me/saved-searches/')
    expect(calls[0].method).toBe('POST')
    expect(JSON.parse(calls[0].body!)).toEqual(body)
    expect(spy).toHaveBeenCalledWith({ queryKey: ['savedSearches'] })
  })

  it('does NOT invalidate on a non-2xx (409) and surfaces the status', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'duplicate' }), { status: 409, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useCreateSavedSearch(), { wrapper })
    result.current.mutate(body)
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).not.toHaveBeenCalledWith({ queryKey: ['savedSearches'] })
  })

  it('does NOT invalidate on a network failure', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => { throw new TypeError('Failed to fetch') })
    const { result } = renderHook(() => useCreateSavedSearch(), { wrapper })
    result.current.mutate(body)
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).not.toHaveBeenCalledWith({ queryKey: ['savedSearches'] })
  })

  it('invalidates ["auth","me"] when the server 401s', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'unauthenticated' }), { status: 401, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useCreateSavedSearch(), { wrapper })
    result.current.mutate(body)
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).toHaveBeenCalledWith({ queryKey: ['auth', 'me'] })
    expect(spy).not.toHaveBeenCalledWith({ queryKey: ['savedSearches'] })
  })
})

describe('useRenameSavedSearch', () => {
  it('PUTs the name to the item route and invalidates on 200', async () => {
    const calls = stubFetch(() => new Response(JSON.stringify({ id: 5, name: 'New', search_parameters: {}, created_at: 'x', updated_at: 'x' }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const { spy, wrapper } = wrap()
    const { result } = renderHook(() => useRenameSavedSearch(), { wrapper })
    result.current.mutate({ id: 5, name: 'New' })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls[0].url).toContain('/api/v1/me/saved-searches/5')
    expect(calls[0].method).toBe('PUT')
    expect(JSON.parse(calls[0].body!)).toEqual({ name: 'New' })
    expect(spy).toHaveBeenCalledWith({ queryKey: ['savedSearches'] })
  })

  it('does NOT invalidate on a non-2xx (404)', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'not found' }), { status: 404, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useRenameSavedSearch(), { wrapper })
    result.current.mutate({ id: 5, name: 'New' })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).not.toHaveBeenCalledWith({ queryKey: ['savedSearches'] })
  })
})

describe('useDeleteSavedSearch', () => {
  it('DELETEs the item route and invalidates on 204', async () => {
    const calls = stubFetch(() => new Response(null, { status: 204 }))
    const { spy, wrapper } = wrap()
    const { result } = renderHook(() => useDeleteSavedSearch(), { wrapper })
    result.current.mutate(7)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls[0].url).toContain('/api/v1/me/saved-searches/7')
    expect(calls[0].method).toBe('DELETE')
    expect(spy).toHaveBeenCalledWith({ queryKey: ['savedSearches'] })
  })

  it('does NOT invalidate on a non-2xx (404)', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'not found' }), { status: 404, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useDeleteSavedSearch(), { wrapper })
    result.current.mutate(7)
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).not.toHaveBeenCalledWith({ queryKey: ['savedSearches'] })
  })
})
