// ABOUTME: Logout mutation — POST /api/v1/auth/sso/logout, then invalidate the ['auth','me'] query.
// ABOUTME: No redirect: the header re-renders anonymous once the invalidated /me returns 401.
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../../lib/api/client'

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      await api.POST('/auth/sso/logout')
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['auth', 'me'] }),
  })
}
