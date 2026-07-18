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

  constructor(status: number) {
    super(`API request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
  }
}

// after the ApiError class — the ONE shared 401 handler every /me/* hook (queries AND mutations)
// routes failures through: a 401 means get_current_user destroyed the server-side session
// (design §4.1), so invalidate ['auth','me'] to collapse the header to anonymous in the same breath
// (design §5); then always throw so the query/mutation still surfaces the error to the caller.
export function raiseApiError(queryClient: QueryClient, status: number): never {
  if (status === 401) {
    queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
  }
  throw new ApiError(status)
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
