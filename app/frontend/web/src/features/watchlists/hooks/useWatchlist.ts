// ABOUTME: TanStack Query hooks for F006 watchlists — list query + add/update/remove mutations.
// ABOUTME: update forwards the body verbatim so an explicit {max_price: null} clears (JSON null); every hook routes non-2xx through raiseApiError (['watchlists'] on 2xx, ['auth','me'] on 401).
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, extractDetail, raiseApiError, type WatchlistItem } from '../../../lib/api/client'
import type { components } from '../../../lib/api/schema'
import { useCurrentUser } from '../../auth/hooks/useCurrentUser'

type WatchlistItemCreate = components['schemas']['WatchlistItemCreate']
type WatchlistItemUpdate = components['schemas']['WatchlistItemUpdate']

export function useWatchlist() {
  const queryClient = useQueryClient()
  // Scope the cache to the authenticated character so a session-cookie swap in another tab can't
  // resolve one identity's watchlist under another's key; gate the fetch on a resolved identity
  // (finding 1). Mutations invalidate the ['watchlists'] prefix, which still matches.
  const { data: user } = useCurrentUser()
  return useQuery<WatchlistItem[]>({
    queryKey: ['watchlists', 'list', user?.character_id],
    enabled: !!user,
    queryFn: async () => {
      const { data, response } = await api.GET('/me/watchlist-items/')
      if (data === undefined) raiseApiError(queryClient, response.status)
      return data
    },
  })
}

export function useAddWatchlistItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: WatchlistItemCreate) => {
      // Capture the parsed error body so ApiError carries the backend detail — the add UI keys the
      // 400 message (cap vs unknown-ship vs not-a-ship) and 502 outage off it (finding 6).
      const { data, error, response } = await api.POST('/me/watchlist-items/', { body })
      if (!response.ok) raiseApiError(queryClient, response.status, extractDetail(error))
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlists'] }),
  })
}

export function useUpdateWatchlistItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: WatchlistItemUpdate }) => {
      const { data, response } = await api.PUT('/me/watchlist-items/{item_id}', {
        params: { path: { item_id: id } },
        body,
      })
      if (!response.ok) raiseApiError(queryClient, response.status)
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlists'] }),
  })
}

export function useRemoveWatchlistItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      const { response } = await api.DELETE('/me/watchlist-items/{item_id}', {
        params: { path: { item_id: id } },
      })
      if (!response.ok) raiseApiError(queryClient, response.status)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlists'] }),
  })
}
