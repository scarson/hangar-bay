import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api, ApiError } from '../../../lib/api/client'
import {
  activeSegment,
  hasEnrichmentDependentFilters,
  isItemLessSelection,
  requiresOfferedItem,
  toApiQuery,
  type ContractSearch,
} from '../filters'
import { useTaxonomy } from './useTaxonomy'

export function useContracts(search: ContractSearch) {
  const query = toApiQuery(search)
  const segment = activeSegment(search)
  const enrichmentFiltered = hasEnrichmentDependentFilters(search)
  // A filter that needs an offered item, asked of a type that has none. Both
  // halves are functions of the request, so the pair travels with the rows.
  const itemFilteredItemLessSegment = isItemLessSelection(search) && requiresOfferedItem(search)

  // Readiness has to be KNOWN before the rows are fetched, and then travel with
  // them (WEB-1). Reading it live cannot be made correct by invalidating on a
  // change: `keepPreviousData` holds the old rows on screen for the whole of
  // the refetch, so the new columns still land on rows fetched under the old
  // answer — and a cold load whose taxonomy resolves while the list is in
  // flight produces the same mismatch with no transition to invalidate on.
  //
  // So the list waits. `isPending` is false once the query has an answer of any
  // kind, an error included, so an unreachable taxonomy endpoint degrades to
  // not-ready rather than blocking the list forever. The cost is one small
  // round trip in front of the first list request; the taxonomy response is
  // then cached for the rest of the session.
  const taxonomy = useTaxonomy()
  const itemSurfaceReady = taxonomy.data?.coverage === 'complete'
  const readinessKnown = !taxonomy.isPending
  return useQuery({
    queryKey: ['contracts', 'list', query],
    queryFn: async () => {
      const { data, response } = await api.GET('/contracts/', { params: { query } })
      if (data === undefined) throw new ApiError(response.status)
      // Everything describing these rows is captured HERE, at fetch time, so it
      // travels with them (WEB-1). `keepPreviousData` below keeps a page on
      // screen while the next one loads, and a view reading any of these from
      // live state instead describes those rows under the incoming request's
      // rules — a sale rendered as a hauling job, an empty result blamed on a
      // region it was never asked about, a half-enriched-corpus warning
      // withdrawn while the rows it was about are still up, or blueprint
      // columns over rows whose terms had not been written yet.
      return {
        ...data,
        segment,
        regionIds: query.region_ids ?? [],
        enrichmentFiltered,
        itemFilteredItemLessSegment,
        itemSurfaceReady,
      }
    },
    // Nothing is fetched until the corpus's readiness is known, so the value
    // captured above is always a real answer rather than a not-yet.
    enabled: readinessKnown,
    placeholderData: keepPreviousData,
  })
}
