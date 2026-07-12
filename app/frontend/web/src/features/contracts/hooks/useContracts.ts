import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api, ApiError } from '../../../lib/api/client'
import { toApiQuery, type ContractSearch } from '../filters'

export function useContracts(search: ContractSearch) {
  const query = toApiQuery(search)
  return useQuery({
    queryKey: ['contracts', 'list', query],
    queryFn: async () => {
      const { data, response } = await api.GET('/contracts/', { params: { query } })
      if (data === undefined) throw new ApiError(response.status)
      return data
    },
    placeholderData: keepPreviousData,
  })
}
