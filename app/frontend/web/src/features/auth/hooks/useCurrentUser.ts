// ABOUTME: TanStack Query hook for GET /api/v1/me — the SPA's only identity source.
// ABOUTME: Resolves null on ANY failure (401/HTTP/network) so anonymous is a state, not an error.
import { useQuery } from '@tanstack/react-query'
import { api, type CurrentUser } from '../../../lib/api/client'

// ANY failure — 401, other HTTP errors, or a network-level rejection — resolves to
// null (anonymous) rather than throwing (spec §5). Resolving bypasses the global
// retry:1, so there is no retry storm and no error UI for the anonymous state.
// openapi-fetch returns { error } for HTTP statuses but THROWS on fetch failure,
// hence the try/catch.
export function useCurrentUser() {
  return useQuery<CurrentUser | null>({
    queryKey: ['auth', 'me'],
    staleTime: 60_000,
    queryFn: async () => {
      try {
        const { data } = await api.GET('/me')
        return data ?? null
      } catch {
        return null
      }
    },
  })
}
