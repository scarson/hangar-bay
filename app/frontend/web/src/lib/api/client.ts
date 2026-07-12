import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

export type Contract = components['schemas']['ContractSchema']
export type ContractItem = components['schemas']['ContractItemSchema']
export type PaginatedContracts = components['schemas']['PaginatedResponse_ContractSchema_']

export class ApiError extends Error {
  status: number

  constructor(status: number) {
    super(`API request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
  }
}

// baseUrl owns the /api/v1 prefix (dev proxy strips it — see vite.config.ts).
// All calls use schema paths verbatim, INCLUDING trailing slashes: /contracts
// without the slash triggers a 307 that escapes the rewriting proxy (PROXY-1).
//
// Two testability constraints shape this call (do NOT "simplify" them away):
// - openapi-fetch builds `new Request(url)` internally; a bare relative
//   baseUrl throws "Invalid URL" under Node/jsdom (browsers resolve it,
//   test environments don't). Prefixing location.origin keeps requests
//   same-origin (still routed through the Vite proxy) and test-runnable.
// - openapi-fetch captures fetch at createClient() time; delegating at
//   call time keeps vi.stubGlobal('fetch', ...) effective in tests.
export const api = createClient<paths>({
  baseUrl: (typeof location !== 'undefined' ? location.origin : '') + '/api/v1',
  fetch: (request) => globalThis.fetch(request),
})
