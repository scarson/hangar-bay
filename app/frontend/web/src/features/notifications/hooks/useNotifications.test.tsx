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
  return { qc, spy, wrapper }
}
afterEach(() => vi.unstubAllGlobals())

const AUTHED = { character_id: 91000001, character_name: 'Sesta Hound' }
const meResponse = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

describe('unreadCountQueryOptions', () => {
  it('carries the polling config and identity-scoped count query key', () => {
    const qc = new QueryClient()
    const opts = unreadCountQueryOptions(qc, true, 91000001)
    expect(opts.queryKey).toEqual(['notifications', 'unreadCount', 91000001])
    expect(opts.refetchInterval).toBe(60_000)
    expect(opts.enabled).toBe(true)
    expect(unreadCountQueryOptions(qc, false, 91000001).enabled).toBe(false)
  })

  it('queryFn hits the size=1 unread endpoint and returns total', async () => {
    const qc = new QueryClient()
    const calls = stubFetch(() => new Response(JSON.stringify({ total: 5, page: 1, size: 1, items: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const opts = unreadCountQueryOptions(qc, true, 91000001)
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
    const opts = unreadCountQueryOptions(qc, true, 91000001)
    await expect((opts.queryFn as () => Promise<number>)()).rejects.toThrow()
    expect(spy).toHaveBeenCalledWith({ queryKey: ['auth', 'me'] })
  })
})

describe('useNotifications (list)', () => {
  it('GETs the list with page/size params and caches under the character id', async () => {
    const calls = stubFetch((call) =>
      /\/api\/v1\/me$/.test(call.url) ? meResponse(200, AUTHED) : meResponse(200, { total: 0, page: 2, size: 20, items: [] }),
    )
    const { qc, wrapper } = wrap()
    const params = { page: 2, size: 20 }
    const { result } = renderHook(() => useNotifications(params), { wrapper })
    await waitFor(() => expect(result.current.data).toBeDefined())
    const domain = calls.find((c) => /\/me\/notifications\//.test(c.url))!
    expect(domain.url).toContain('/api/v1/me/notifications/')
    expect(domain.url).toContain('page=2')
    expect(domain.url).toContain('size=20')
    // Identity-scoped key (finding 1): character id precedes the params.
    expect(qc.getQueryData(['notifications', 'list', AUTHED.character_id, params])).toBeDefined()
  })

  it('does not fetch while anonymous (enabled gates on the identity)', async () => {
    const calls = stubFetch((call) =>
      /\/api\/v1\/me$/.test(call.url) ? meResponse(401, { detail: 'unauth' }) : meResponse(200, { total: 0, page: 1, size: 20, items: [] }),
    )
    const { wrapper } = wrap()
    const { result } = renderHook(() => useNotifications({ page: 1, size: 20 }), { wrapper })
    await waitFor(() => expect(calls.some((c) => /\/api\/v1\/me$/.test(c.url))).toBe(true))
    expect(result.current.fetchStatus).toBe('idle')
    expect(result.current.data).toBeUndefined()
    expect(calls.some((c) => /\/me\/notifications\//.test(c.url))).toBe(false)
  })

  it('surfaces an error after a persistent failure (TEST-7)', async () => {
    stubFetch((call) =>
      /\/api\/v1\/me$/.test(call.url) ? meResponse(200, AUTHED) : new Response(JSON.stringify({ detail: 'boom' }), { status: 500, headers: { 'Content-Type': 'application/json' } }),
    )
    const { wrapper } = wrap()
    const { result } = renderHook(() => useNotifications({ page: 1, size: 20 }), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })

  it('invalidates ["auth","me"] when the list 401s', async () => {
    const { spy, wrapper } = wrap()
    stubFetch((call) =>
      /\/api\/v1\/me$/.test(call.url) ? meResponse(200, AUTHED) : meResponse(401, { detail: 'unauth' }),
    )
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
  it('GETs the settings for the authed identity and caches under the character id', async () => {
    const calls = stubFetch((call) =>
      /\/api\/v1\/me$/.test(call.url) ? meResponse(200, AUTHED) : meResponse(200, { watchlist_alerts_enabled: true }),
    )
    const { qc, wrapper } = wrap()
    const { result } = renderHook(() => useNotificationSettings(), { wrapper })
    await waitFor(() => expect(result.current.data).toEqual({ watchlist_alerts_enabled: true }))
    expect(calls.some((c) => /\/api\/v1\/me\/notification-settings/.test(c.url))).toBe(true)
    // Identity-scoped key (finding 1): per-user settings cache under the character id.
    expect(qc.getQueryData(['notifications', 'settings', AUTHED.character_id])).toEqual({ watchlist_alerts_enabled: true })
  })

  it('invalidates ["auth","me"] when the settings GET 401s', async () => {
    const { spy, wrapper } = wrap()
    stubFetch((call) =>
      /\/api\/v1\/me$/.test(call.url) ? meResponse(200, AUTHED) : meResponse(401, { detail: 'unauth' }),
    )
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
