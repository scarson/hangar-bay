// ABOUTME: useCurrentUser hook contract — 200 → user, 401 → null, network failure → null.
// ABOUTME: Asserts the request URL and that resolving (not rejecting) bypasses retry:1.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { jsonResponse } from '../../../test/http'
import { useCurrentUser } from './useCurrentUser'

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: 1 } } })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('useCurrentUser', () => {
  it('returns the user on 200 and requests /api/v1/me', async () => {
    const calls: string[] = []
    vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
      calls.push(typeof input === 'string' ? input : (input as Request).url ?? String(input))
      return jsonResponse({ character_id: 91000001, character_name: 'Sesta Hound' })
    })
    const { result } = renderHook(() => useCurrentUser(), { wrapper: wrapper() })
    await waitFor(() => expect(result.current.data).toEqual({ character_id: 91000001, character_name: 'Sesta Hound' }))
    expect(calls[0]).toContain('/api/v1/me')
  })

  it('resolves null on 401 without throwing (no retry storm)', async () => {
    let count = 0
    vi.stubGlobal('fetch', async () => {
      count += 1
      return jsonResponse({ detail: 'unauthenticated' }, 401)
    })
    const { result } = renderHook(() => useCurrentUser(), { wrapper: wrapper() })
    await waitFor(() => expect(result.current.isPending).toBe(false))
    expect(result.current.data).toBeNull()
    expect(result.current.isError).toBe(false)
    expect(count).toBe(1)   // resolved, not retried
  })

  it('resolves null when fetch itself rejects (network failure)', async () => {
    // Spec §5: "any failure" resolves to anonymous. openapi-fetch only returns
    // { error } for HTTP statuses — it THROWS on network-level failure, so the
    // hook's catch must convert the rejection into null too.
    let count = 0
    vi.stubGlobal('fetch', async () => {
      count += 1
      throw new TypeError('network down')
    })
    const { result } = renderHook(() => useCurrentUser(), { wrapper: wrapper() })
    await waitFor(() => expect(result.current.isPending).toBe(false))
    expect(result.current.data).toBeNull()
    expect(result.current.isError).toBe(false)
    expect(count).toBe(1)   // resolved, not retried — the catch bypasses retry:1
  })
})
