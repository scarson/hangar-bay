import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api, ApiError } from '../../../lib/api/client'
import { activeSegment, toApiQuery, type ContractSearch } from '../filters'

export function useContracts(search: ContractSearch) {
  const query = toApiQuery(search)
  const segment = activeSegment(search)
  return useQuery({
    queryKey: ['contracts', 'list', query],
    queryFn: async () => {
      const { data, response } = await api.GET('/contracts/', { params: { query } })
      if (data === undefined) throw new ApiError(response.status)
      // The segment travels with the rows it selected. `keepPreviousData` below
      // keeps a page on screen while the next one loads, so a view that reads
      // the segment from the live URL instead describes those rows under the
      // incoming segment's rules — a sale rendered as a hauling job for as long
      // as the request takes. Deriving it inside the query function ties it to
      // the cache key, which `query` already determines.
      return { ...data, segment }
    },
    placeholderData: keepPreviousData,
  })
}
