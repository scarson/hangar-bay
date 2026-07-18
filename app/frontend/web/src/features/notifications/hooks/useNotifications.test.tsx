// ABOUTME: useNotifications hook contracts — list, unread-count queryOptions factory, mark-read/all, settings.
// ABOUTME: Asserts count queryOptions fields (refetchInterval/enabled) directly + the count URL; mutations assert URL/method/invalidation (TEST-5).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  useNotifications,
  unreadCountQueryOptions,
  useMarkRead,
  useMarkAllRead,
  useNotificationSettings,
  useUpdateNotificationSettings,
} from './useNotifications'

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

describe('unreadCountQueryOptions', () => {
  it('carries the polling config and count query key', () => {
    const qc = new QueryClient()
    const opts = unreadCountQueryOptions(qc, true)
    expect(opts.queryKey).toEqual(['notifications', 'unreadCount'])
    expect(opts.refetchInterval).toBe(60_000)
    expect(opts.enabled).toBe(true)
    expect(unreadCountQueryOptions(qc, false).enabled).toBe(false)
  })

  it('queryFn hits the size=1 unread endpoint and returns total', async () => {
    const qc = new QueryClient()
    const calls = stubFetch(() => new Response(JSON.stringify({ total: 5, page: 1, size: 1, items: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const opts = unreadCountQueryOptions(qc, true)
    const total = await (opts.queryFn as () => Promise<number>)()
    expect(total).toBe(5)
    expect(calls[0].url).toContain('/api/v1/me/notifications/')
    expect(calls[0].url).toContain('is_read=false')
    expect(calls[0].url).toContain('size=1')
  })

  it('invalidates ["auth","me"] when the count poll 401s', async () => {
    const qc = new QueryClient()
    const spy = vi.spyOn(qc, 'invalidateQueries')
    stubFetch(() => new Response(JSON.stringify({ detail: 'unauth' }), { status: 401, headers: { 'Content-Type': 'application/json' } }))
    const opts = unreadCountQueryOptions(qc, true)
    await expect((opts.queryFn as () => Promise<number>)()).rejects.toThrow()
    expect(spy).toHaveBeenCalledWith({ queryKey: ['auth', 'me'] })
  })
})

describe('useNotifications (list)', () => {
  it('GETs the list with page/size params', async () => {
    const calls = stubFetch(() => new Response(JSON.stringify({ total: 0, page: 2, size: 20, items: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const { wrapper } = wrap()
    const { result } = renderHook(() => useNotifications({ page: 2, size: 20 }), { wrapper })
    await waitFor(() => expect(result.current.data).toBeDefined())
    expect(calls[0].url).toContain('/api/v1/me/notifications/')
    expect(calls[0].url).toContain('page=2')
    expect(calls[0].url).toContain('size=20')
  })

  it('surfaces an error after a persistent failure (TEST-7)', async () => {
    stubFetch(() => new Response(JSON.stringify({ detail: 'boom' }), { status: 500, headers: { 'Content-Type': 'application/json' } }))
    const { wrapper } = wrap()
    const { result } = renderHook(() => useNotifications({ page: 1, size: 20 }), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })

  it('invalidates ["auth","me"] when the list 401s', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'unauth' }), { status: 401, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useNotifications({ page: 1, size: 20 }), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).toHaveBeenCalledWith({ queryKey: ['auth', 'me'] })
  })
})

describe('useMarkRead / useMarkAllRead', () => {
  it('marks one read and invalidates ["notifications"]', async () => {
    const calls = stubFetch(() => new Response(null, { status: 204 }))
    const { spy, wrapper } = wrap()
    const { result } = renderHook(() => useMarkRead(), { wrapper })
    result.current.mutate(7)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls[0].url).toContain('/api/v1/me/notifications/7/mark-read')
    expect(calls[0].method).toBe('POST')
    expect(spy).toHaveBeenCalledWith({ queryKey: ['notifications'] })
  })

  it('marks all read', async () => {
    const calls = stubFetch(() => new Response(null, { status: 204 }))
    const { spy, wrapper } = wrap()
    const { result } = renderHook(() => useMarkAllRead(), { wrapper })
    result.current.mutate()
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls[0].url).toContain('/api/v1/me/notifications/mark-all-read')
    expect(calls[0].method).toBe('POST')
    expect(spy).toHaveBeenCalledWith({ queryKey: ['notifications'] })
  })

  it('invalidates ["auth","me"] when mark-read 401s', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'unauth' }), { status: 401, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useMarkRead(), { wrapper })
    result.current.mutate(7)
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).toHaveBeenCalledWith({ queryKey: ['auth', 'me'] })
  })
})

describe('notification settings', () => {
  it('GETs the settings', async () => {
    const calls = stubFetch(() => new Response(JSON.stringify({ watchlist_alerts_enabled: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const { wrapper } = wrap()
    const { result } = renderHook(() => useNotificationSettings(), { wrapper })
    await waitFor(() => expect(result.current.data).toEqual({ watchlist_alerts_enabled: true }))
    expect(calls[0].url).toContain('/api/v1/me/notification-settings')
  })

  it('invalidates ["auth","me"] when the settings GET 401s', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'unauth' }), { status: 401, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useNotificationSettings(), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).toHaveBeenCalledWith({ queryKey: ['auth', 'me'] })
  })

  it('PUTs the settings body and invalidates the settings key', async () => {
    const calls = stubFetch(() => new Response(JSON.stringify({ watchlist_alerts_enabled: false }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const { spy, wrapper } = wrap()
    const { result } = renderHook(() => useUpdateNotificationSettings(), { wrapper })
    result.current.mutate({ watchlist_alerts_enabled: false })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls[0].method).toBe('PUT')
    expect(JSON.parse(calls[0].body!)).toEqual({ watchlist_alerts_enabled: false })
    expect(spy).toHaveBeenCalledWith({ queryKey: ['notifications', 'settings'] })
  })
})
