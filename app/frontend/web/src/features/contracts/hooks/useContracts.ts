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
      // The segment and the regions travel with the rows they selected.
      // `keepPreviousData` below keeps a page on screen while the next one
      // loads, so a view that reads either from the live URL instead describes
      // those rows under the incoming request's rules — a sale rendered as a
      // hauling job, or an empty result blamed on a region it was never asked
      // about — for as long as the request takes. Deriving both inside the
      // query function ties them to the cache key, which `query` determines.
      return { ...data, segment, regionIds: query.region_ids ?? [] }
    },
    placeholderData: keepPreviousData,
  })
}
