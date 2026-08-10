import { describe, expect, it } from 'vitest'
import createClient from 'openapi-fetch'
import { QueryClient } from '@tanstack/react-query'
import type { paths } from './schema'
import { ApiError, extractDetail, raiseApiError } from './client'
import { jsonResponse } from '../../test/http'

const EMPTY_PAGE = { total: 0, page: 1, size: 50, items: [] }

function clientWithRecorder(calls: string[]) {
  const recordingFetch: typeof fetch = async (input) => {
    const url =
      typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    calls.push(url)
    return jsonResponse(EMPTY_PAGE)
  }
  return createClient<paths>({ baseUrl: 'http://test/api/v1', fetch: recordingFetch })
}

describe('api client request contract', () => {
  it('serializes ID arrays as repeated query params (FastAPI form/explode)', async () => {
    const calls: string[] = []
    const client = clientWithRecorder(calls)

    await client.GET('/contracts/', {
      params: { query: { region_ids: [10000002, 10000020], page: 1, size: 50 } },
    })

    expect(calls[0]).toContain('region_ids=10000002&region_ids=10000020')
  })

  it('hits the trailing-slash list path under the /api/v1 base (PROXY-1)', async () => {
    const calls: string[] = []
    const client = clientWithRecorder(calls)

    await client.GET('/contracts/', { params: { query: { page: 1, size: 50 } } })

    expect(calls[0].startsWith('http://test/api/v1/contracts/?')).toBe(true)
  })

  it('omits undefined query params entirely', async () => {
    const calls: string[] = []
    const client = clientWithRecorder(calls)

    await client.GET('/contracts/', {
      params: { query: { search: undefined, page: 1, size: 50 } },
    })

    expect(calls[0]).not.toContain('search')
  })
})

describe('ApiError', () => {
  it('carries the HTTP status and is an Error', () => {
    const error = new ApiError(404)
    expect(error.status).toBe(404)
    expect(error).toBeInstanceOf(Error)
    expect(error.message).toContain('404')
  })

  it('carries an optional backend detail and surfaces it as the message', () => {
    const error = new ApiError(400, 'watchlist is full (max 200 items)')
    expect(error.status).toBe(400)
    expect(error.detail).toBe('watchlist is full (max 200 items)')
    expect(error.message).toContain('watchlist is full')
  })

  it('leaves detail undefined when none is provided (e.g. a network error)', () => {
    expect(new ApiError(500).detail).toBeUndefined()
  })
})

describe('extractDetail', () => {
  it('lifts a string detail off a parsed error body', () => {
    expect(extractDetail({ detail: 'unknown ship name' })).toBe('unknown ship name')
  })

  it('returns undefined for a non-string detail, missing detail, or non-object', () => {
    expect(extractDetail({ detail: [{ msg: 'x' }] })).toBeUndefined() // 422 validation array shape
    expect(extractDetail({})).toBeUndefined()
    expect(extractDetail(undefined)).toBeUndefined()
    expect(extractDetail('boom')).toBeUndefined()
  })
})

describe('raiseApiError', () => {
  it('throws an ApiError carrying the status and the parsed detail', () => {
    const qc = new QueryClient()
    try {
      raiseApiError(qc, 400, 'watchlist is full (max 200 items)')
      expect.unreachable('raiseApiError must throw')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).status).toBe(400)
      expect((error as ApiError).detail).toBe('watchlist is full (max 200 items)')
    }
  })
})

describe('raiseApiError leaves the identity cache alone on a non-401', () => {
  it('invalidates the identity query for a 401 and for nothing else', async () => {
    // The 401 arm is what collapses the header to anonymous when the server-side
    // session is gone. Its converse is the part nothing asserted: a 400 from an
    // unrelated mutation must NOT invalidate ['auth','me'], because doing so refetches
    // identity and flickers the header on every ordinary validation error.
    //
    // Observed by INVALIDATION STATE rather than by counting refetches: a refetch
    // counter is blind here, since an invalidated query with no mounted observer does
    // not refetch at all (TEST-25 — pick an observable that differs under the mutation).
    const qc = new QueryClient()
    const identity = ['auth', 'me']
    qc.setQueryData(identity, { character_name: 'Pilot' })

    const isStale = () => qc.getQueryState(identity)?.isInvalidated === true

    expect(isStale()).toBe(false) // the instrument can read the un-invalidated state

    expect(() => raiseApiError(qc, 400, 'watchlist is full')).toThrow(ApiError)
    expect(isStale()).toBe(false)

    expect(() => raiseApiError(qc, 403, 'forbidden')).toThrow(ApiError)
    expect(isStale()).toBe(false)

    // And the positive arm, so the check above is not passing because the instrument
    // cannot see an invalidation at all (TEST-15).
    expect(() => raiseApiError(qc, 401)).toThrow(ApiError)
    expect(isStale()).toBe(true)
  })
})
