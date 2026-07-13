// ABOUTME: useLogout hook contract — POSTs /api/v1/auth/sso/logout and invalidates ['auth','me'].
// ABOUTME: Asserts URL + METHOD at the fetch seam, not just query invalidation (TEST-5).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useLogout } from './useLogout'

afterEach(() => vi.unstubAllGlobals())

describe('useLogout', () => {
  it('POSTs /api/v1/auth/sso/logout and invalidates the me query', async () => {
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
  })
})
