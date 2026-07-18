// ABOUTME: useLogout hook contract — POSTs /api/v1/auth/sso/logout and invalidates ['auth','me'].
// ABOUTME: Asserts URL + METHOD at the fetch seam, not just query invalidation (TEST-5).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useLogout } from './useLogout'

afterEach(() => vi.unstubAllGlobals())

describe('useLogout', () => {
  it('POSTs /api/v1/auth/sso/logout and invalidates the me query on success (2xx)', async () => {
    const calls: { url: string; method?: string }[] = []
    vi.stubGlobal('fetch', async (input: RequestInfo | URL, init?: RequestInit) => {
      const req = input as Request
      calls.push({ url: req.url ?? String(input), method: req.method ?? init?.method })
      return new Response(null, { status: 204 })
    })
    const qc = new QueryClient()
    const spy = vi.spyOn(qc, 'invalidateQueries')
    const w = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    const { result } = renderHook(() => useLogout(), { wrapper: w })
    result.current.mutate()
    await waitFor(() => expect(calls.length).toBe(1))
    expect(calls[0].url).toContain('/api/v1/auth/sso/logout')
    expect(calls[0].method).toBe('POST')
    await waitFor(() => expect(spy).toHaveBeenCalledWith({ queryKey: ['auth', 'me'] }))
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
  })

  it('does NOT invalidate the me query when the server returns a non-2xx response', async () => {
    // openapi-fetch resolves non-2xx as { error, response }, it does not throw. A prior
    // bug invalidated ['auth','me'] on every settlement regardless of status, which — if
    // the follow-up /me request also failed — rendered a false logged-out header even
    // though the server-side session was never destroyed.
    vi.stubGlobal('fetch', async () =>
      new Response(JSON.stringify({ detail: 'boom' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    const qc = new QueryClient()
    const spy = vi.spyOn(qc, 'invalidateQueries')
    const w = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    const { result } = renderHook(() => useLogout(), { wrapper: w })
    result.current.mutate()
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).not.toHaveBeenCalled()
  })

  it('does NOT invalidate the me query when the request rejects (network failure)', async () => {
    vi.stubGlobal('fetch', async () => {
      throw new TypeError('Failed to fetch')
    })
    const qc = new QueryClient()
    const spy = vi.spyOn(qc, 'invalidateQueries')
    const w = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    const { result } = renderHook(() => useLogout(), { wrapper: w })
    result.current.mutate()
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).not.toHaveBeenCalled()
  })
})
