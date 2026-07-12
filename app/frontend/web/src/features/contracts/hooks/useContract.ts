import { useQuery } from '@tanstack/react-query'
import { api, ApiError } from '../../../lib/api/client'

export function useContract(contractId: number) {
  return useQuery({
    queryKey: ['contracts', 'detail', contractId],
    enabled: Number.isInteger(contractId) && contractId > 0,
    retry: (failureCount, error) =>
      !(error instanceof ApiError && error.status === 404) && failureCount < 1,
    queryFn: async () => {
      const { data, response } = await api.GET('/contracts/{contract_id}', {
        params: { path: { contract_id: contractId } },
      })
      if (data === undefined) throw new ApiError(response.status)
      return data
    },
  })
}
