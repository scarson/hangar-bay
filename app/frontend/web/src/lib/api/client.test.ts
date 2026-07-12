import { describe, expect, it } from 'vitest'
import createClient from 'openapi-fetch'
import type { paths } from './schema'
import { ApiError } from './client'
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
})
