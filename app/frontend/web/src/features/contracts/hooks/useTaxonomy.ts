// ABOUTME: The dogma category/group option lists behind the item-level filters,
// ABOUTME: plus the readiness signal that decides whether that surface opens at all.
import { useQuery } from '@tanstack/react-query'
import { api, ApiError } from '../../../lib/api/client'

/**
 * The option lists are near-static within a session — they change only when the
 * corpus starts holding a category it did not before — so five minutes of
 * staleness costs nothing and saves a request per navigation.
 */
export function useTaxonomy() {
  return useQuery({
    queryKey: ['contracts', 'taxonomy'],
    queryFn: async () => {
      const { data, response } = await api.GET('/contracts/taxonomy')
      if (data === undefined) throw new ApiError(response.status)
      return data
    },
    staleTime: 5 * 60_000,
  })
}

/**
 * Whether the item-level surface may open. The server reports `complete` only
 * once the live corpus is enriched at the current enrichment version AND every
 * category on its items has a cached name (decision log D1), so this is
 * observed reality rather than a flag anyone has to remember to flip: it
 * degrades on its own during a future resweep and restores on its own after.
 *
 * Everything short of that answer — still indexing, still loading, or an
 * endpoint that could not be reached — reads as not ready. Controls offered
 * over a half-enriched corpus return pages that are missing contracts for
 * reasons the reader cannot see, which is worse than a control that is honestly
 * not there yet.
 */
export function useItemSurfaceReady(): boolean {
  const { data } = useTaxonomy()
  return data?.coverage === 'complete'
}
