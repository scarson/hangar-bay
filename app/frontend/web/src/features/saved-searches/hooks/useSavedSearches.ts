// ABOUTME: TanStack Query hooks for F005 saved searches — list query + create/rename/delete mutations.
// ABOUTME: Every hook routes non-2xx through raiseApiError (invalidates ['auth','me'] on 401); mutations invalidate ['savedSearches'] on 2xx.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, raiseApiError, type SavedSearch } from '../../../lib/api/client'
import type { components } from '../../../lib/api/schema'
import { useCurrentUser } from '../../auth/hooks/useCurrentUser'

type SavedSearchCreate = components['schemas']['SavedSearchCreate']

export function useSavedSearches() {
  const queryClient = useQueryClient()
  // Scope the cache to the authenticated character so a session-cookie swap in another tab can't
  // resolve one identity's saved searches under another's key; gate the fetch on a resolved
  // identity (finding 1). Mutations invalidate the ['savedSearches'] prefix, which still matches.
  const { data: user } = useCurrentUser()
  return useQuery<SavedSearch[]>({
    queryKey: ['savedSearches', 'list', user?.character_id],
    enabled: !!user,
    queryFn: async () => {
      const { data, response } = await api.GET('/me/saved-searches/')
      if (data === undefined) raiseApiError(queryClient, response.status)
      return data
    },
  })
}

export function useCreateSavedSearch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: SavedSearchCreate) => {
      const { data, response } = await api.POST('/me/saved-searches/', { body })
      if (!response.ok) raiseApiError(queryClient, response.status)
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['savedSearches'] }),
  })
}

export function useRenameSavedSearch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, name }: { id: number; name: string }) => {
      const { data, response } = await api.PUT('/me/saved-searches/{search_id}', {
        params: { path: { search_id: id } },
        body: { name },
      })
      if (!response.ok) raiseApiError(queryClient, response.status)
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['savedSearches'] }),
  })
}

export function useDeleteSavedSearch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      const { response } = await api.DELETE('/me/saved-searches/{search_id}', {
        params: { path: { search_id: id } },
      })
      if (!response.ok) raiseApiError(queryClient, response.status)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['savedSearches'] }),
  })
}
