// ABOUTME: TanStack Query hooks for F006 watchlists — list query + add/update/remove mutations.
// ABOUTME: update forwards the body verbatim so an explicit {max_price: null} clears (JSON null); every hook routes non-2xx through raiseApiError (['watchlists'] on 2xx, ['auth','me'] on 401).
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, raiseApiError, type WatchlistItem } from '../../../lib/api/client'
import type { components } from '../../../lib/api/schema'

type WatchlistItemCreate = components['schemas']['WatchlistItemCreate']
type WatchlistItemUpdate = components['schemas']['WatchlistItemUpdate']

export function useWatchlist() {
  const queryClient = useQueryClient()
  return useQuery<WatchlistItem[]>({
    queryKey: ['watchlists', 'list'],
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
      const { data, response } = await api.POST('/me/watchlist-items/', { body })
      if (!response.ok) raiseApiError(queryClient, response.status)
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
