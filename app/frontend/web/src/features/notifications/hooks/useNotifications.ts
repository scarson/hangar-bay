// ABOUTME: TanStack Query hooks for F007 notifications — paginated list, unread-count poll, mark-read/all, settings.
// ABOUTME: unreadCountQueryOptions is a standalone factory (testable without a component); every hook routes non-2xx through raiseApiError (['auth','me'] on 401).
import { QueryClient, queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, raiseApiError, type NotificationSettings, type PaginatedNotifications } from '../../../lib/api/client'
import { useCurrentUser } from '../../auth/hooks/useCurrentUser'

export function useNotifications(params: { page: number; size: number; is_read?: boolean }) {
  const queryClient = useQueryClient()
  return useQuery<PaginatedNotifications>({
    queryKey: ['notifications', 'list', params],
    queryFn: async () => {
      const { data, response } = await api.GET('/me/notifications/', { params: { query: params } })
      if (data === undefined) raiseApiError(queryClient, response.status)
      return data
    },
  })
}

// The unread badge reads `total` off a filtered size=1 page — no dedicated count
// endpoint (design §3.4). Polls every 60s; only enabled when authed. Takes the caller's
// queryClient so a 401 poll invalidates ['auth','me'] like every other /me/* query.
export function unreadCountQueryOptions(queryClient: QueryClient, enabled: boolean) {
  return queryOptions({
    queryKey: ['notifications', 'unreadCount'],
    enabled,
    refetchInterval: 60_000,
    queryFn: async () => {
      const { data, response } = await api.GET('/me/notifications/', {
        params: { query: { is_read: false, size: 1 } },
      })
      if (data === undefined) raiseApiError(queryClient, response.status)
      return data.total
    },
  })
}

export function useUnreadCount() {
  const queryClient = useQueryClient()
  const { data: user } = useCurrentUser()
  return useQuery(unreadCountQueryOptions(queryClient, !!user))
}

export function useMarkRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      const { response } = await api.POST('/me/notifications/{notification_id}/mark-read', {
        params: { path: { notification_id: id } },
      })
      if (!response.ok) raiseApiError(queryClient, response.status)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  })
}

export function useMarkAllRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { response } = await api.POST('/me/notifications/mark-all-read')
      if (!response.ok) raiseApiError(queryClient, response.status)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  })
}

export function useNotificationSettings() {
  const queryClient = useQueryClient()
  return useQuery<NotificationSettings>({
    queryKey: ['notifications', 'settings'],
    queryFn: async () => {
      const { data, response } = await api.GET('/me/notification-settings')
      if (data === undefined) raiseApiError(queryClient, response.status)
      return data
    },
  })
}

export function useUpdateNotificationSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: NotificationSettings) => {
      const { data, response } = await api.PUT('/me/notification-settings', { body })
      if (!response.ok) raiseApiError(queryClient, response.status)
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications', 'settings'] }),
  })
}
