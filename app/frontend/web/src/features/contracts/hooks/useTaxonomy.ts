// ABOUTME: The dogma category/group option lists behind the item-level filters,
// ABOUTME: plus the readiness signal that decides whether that surface opens at all.
import { useEffect, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '../../../lib/api/client'

/**
 * How often to re-ask whether the corpus is enriched. `staleTime` alone would
 * NOT do it: it marks data stale without scheduling anything, so a cached
 * answer survives until something else triggers a refetch (a remount, a window
 * refocus) — and a tab left open and focused across an `ENRICHMENT_VERSION`
 * resweep would keep reporting `complete` for the whole ~80 minutes it is
 * false. Decision D1's "degrades on its own" is a claim about this interval.
 *
 * `refetchInterval` does not fire on a backgrounded tab (that is React Query's
 * default and we want it), so this costs one small request per five minutes of
 * actual use.
 */
const READINESS_POLL_MS = 5 * 60_000

export function useTaxonomy() {
  return useQuery({
    queryKey: ['contracts', 'taxonomy'],
    queryFn: async () => {
      const { data, response } = await api.GET('/contracts/taxonomy')
      if (data === undefined) throw new ApiError(response.status)
      return data
    },
    // The option lists are near-static — they change only when the corpus
    // starts holding a category it did not before — so the poll above is the
    // thing that keeps this current, not a short staleTime.
    staleTime: READINESS_POLL_MS,
    refetchInterval: READINESS_POLL_MS,
  })
}

/**
 * Whether the item-level surface may open. The server reports `complete` only
 * once the live corpus is enriched at the current enrichment version AND every
 * category on its items has a cached name (decision log D1), so this is
 * observed reality rather than a flag anyone has to remember to flip.
 *
 * Everything short of that answer — still indexing, still loading, or an
 * endpoint that could not be reached — reads as not ready. Controls offered
 * over a half-enriched corpus return pages that are missing contracts for
 * reasons the reader cannot see, which is worse than a control that is honestly
 * not there yet.
 *
 * This value describes the CORPUS, not the rows — which is why it may be read
 * live rather than carried on the query result (decision log D13). What makes
 * that safe is `useItemSurfaceRefresh` below, not the read itself.
 */
export function useItemSurfaceReady(): boolean {
  return useTaxonomy().data?.coverage === 'complete'
}

/**
 * Drops the list cache when the corpus's readiness changes under it.
 *
 * Without this the two halves drift: the rows on screen were fetched from an
 * earlier state of the corpus, and nothing makes them refetch when readiness
 * flips. A contract known to hold a blueprint copy would then show its BPC
 * badge beside empty Runs/ME/TE cells — its terms had not been written when
 * that page was fetched — and the composition line would name categories from
 * a cache that has since filled in. Invalidating brings the rows forward to the
 * state the columns are already describing.
 *
 * Only a change BETWEEN KNOWN answers invalidates. The first answer of a
 * session resolves from `undefined`, and treating that as a transition would
 * cost a second corpus-scale list request on every cold load — the exact
 * expense D13 weighed and refused.
 *
 * Called once, by the page that owns the list query.
 */
export function useItemSurfaceRefresh(): void {
  const coverage = useTaxonomy().data?.coverage
  const queryClient = useQueryClient()
  const previousCoverage = useRef(coverage)

  useEffect(() => {
    const previous = previousCoverage.current
    previousCoverage.current = coverage
    if (previous === undefined || coverage === undefined || previous === coverage) return
    queryClient.invalidateQueries({ queryKey: ['contracts', 'list'] })
  }, [coverage, queryClient])
}
