import createClient from 'openapi-fetch'
import type { QueryClient } from '@tanstack/react-query'
import type { components, paths } from './schema'

export type Contract = components['schemas']['ContractSchema']
export type ContractItem = components['schemas']['ContractItemSchema']
export type PaginatedContracts = components['schemas']['PaginatedResponse_ContractSchema_']
export type CurrentUser = components['schemas']['CurrentUserSchema']
export type SavedSearch = components['schemas']['SavedSearchSchema']
export type WatchlistItem = components['schemas']['WatchlistItemSchema']
export type Notification = components['schemas']['NotificationSchema']
export type NotificationSettings = components['schemas']['NotificationSettingsSchema']
export type PaginatedNotifications = components['schemas']['PaginatedResponse_NotificationSchema_']

export class ApiError extends Error {
  status: number
  // The backend's FastAPI `detail` string, when the failure carried one. Undefined for a
  // network-level failure (which never produces a response body) or a non-string detail (e.g. a
  // 422 validation array). Lets callers distinguish, say, a 400 cap from a 400 unknown-ship.
  detail?: string

  constructor(status: number, detail?: string) {
    super(detail ?? `API request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

// Lift a FastAPI `detail` string off openapi-fetch's parsed error body (it does the
// `await response.json()` internally and hands it back as `error` on a non-2xx). Ignores a
// missing/non-object body and the array-shaped detail of a 422 validation error.
export function extractDetail(error: unknown): string | undefined {
  if (error && typeof error === 'object' && 'detail' in error) {
    const detail = (error as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
  }
  return undefined
}

// after the ApiError class — the ONE shared 401 handler every /me/* hook (queries AND mutations)
// routes failures through: a 401 means get_current_user destroyed the server-side session
// (design §4.1), so invalidate ['auth','me'] to collapse the header to anonymous in the same breath
// (design §5); then always throw so the query/mutation still surfaces the error to the caller.
// `detail` (optional) carries the backend message through to ApiError for callers that render it.
export function raiseApiError(queryClient: QueryClient, status: number, detail?: string): never {
  if (status === 401) {
    queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
  }
  throw new ApiError(status, detail)
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
