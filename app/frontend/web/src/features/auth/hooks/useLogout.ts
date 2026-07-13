// ABOUTME: Logout mutation — POST /api/v1/auth/sso/logout, then invalidate the ['auth','me'] query.
// ABOUTME: No redirect: the header re-renders anonymous once the invalidated /me returns 401.
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '../../../lib/api/client'

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      // openapi-fetch resolves non-2xx as { error, response } rather than throwing, so a
      // failed logout would otherwise look like a completed mutation. Only a confirmed
      // 2xx counts as "logged out" here; both a non-2xx response and a thrown/network
      // failure must leave the mutation in an error state so the header does NOT flip to
      // anonymous while the server-side session may still be live. (The generated schema
      // only declares a 204 response for this operation, so `error`'s type is `never` —
      // check `response.ok` directly rather than the typed `error` field.)
      const { response } = await api.POST('/auth/sso/logout')
      if (!response.ok) throw new ApiError(response.status)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['auth', 'me'] }),
  })
}
