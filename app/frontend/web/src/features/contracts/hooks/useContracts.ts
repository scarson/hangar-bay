import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api, ApiError } from '../../../lib/api/client'
import {
  activeSegment,
  hasEnrichmentDependentFilters,
  toApiQuery,
  type ContractSearch,
} from '../filters'

export function useContracts(search: ContractSearch) {
  const query = toApiQuery(search)
  const segment = activeSegment(search)
  const enrichmentFiltered = hasEnrichmentDependentFilters(search)
  return useQuery({
    queryKey: ['contracts', 'list', query],
    queryFn: async () => {
      const { data, response } = await api.GET('/contracts/', { params: { query } })
      if (data === undefined) throw new ApiError(response.status)
      // The segment, the regions, and whether an item-level filter was in play
      // all travel with the rows they selected. `keepPreviousData` below keeps
      // a page on screen while the next one loads, so a view that reads any of
      // them from the live URL instead describes those rows under the incoming
      // request's rules — a sale rendered as a hauling job, an empty result
      // blamed on a region it was never asked about, or a half-enriched-corpus
      // warning withdrawn while the rows it was about are still on screen — for
      // as long as the request takes. Deriving them inside the query function
      // ties them to the cache key, which `query` determines (WEB-1).
      return { ...data, segment, regionIds: query.region_ids ?? [], enrichmentFiltered }
    },
    placeholderData: keepPreviousData,
  })
}
