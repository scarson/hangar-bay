// ABOUTME: The dogma category/group option lists behind the item-level filters,
// ABOUTME: plus the readiness signal that decides whether that surface opens at all.
import { useQuery } from '@tanstack/react-query'
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

/**
 * How long the contract list will wait for a readiness answer before giving up
 * on one. The list is `enabled` on this query having ANY answer, so that it can
 * capture readiness with the rows it fetches (WEB-1) — which means a taxonomy
 * request that neither resolves nor rejects would hold the app's core view on
 * its skeleton indefinitely. An error unblocks it; a hang would not.
 *
 * A readiness probe nobody has answered in five seconds is not worth waiting
 * for: the surface it gates stays closed either way, and the rows do not need
 * it to be correct — only to be described correctly.
 */
const READINESS_TIMEOUT_MS = 5_000

export function useTaxonomy() {
  return useQuery({
    queryKey: ['contracts', 'taxonomy'],
    queryFn: async () => {
      // An explicit controller rather than `AbortSignal.timeout`: the latter
      // runs on a platform timer that test fake-timers cannot drive, which
      // would leave the bound above unverifiable.
      const abort = new AbortController()
      const timer = setTimeout(() => abort.abort(), READINESS_TIMEOUT_MS)
      try {
        const { data, response } = await api.GET('/contracts/taxonomy', { signal: abort.signal })
        if (data === undefined) throw new ApiError(response.status)
        return data
      } finally {
        clearTimeout(timer)
      }
    },
    // The option lists are near-static — they change only when the corpus
    // starts holding a category it did not before — so the poll above is the
    // thing that keeps this current, not a short staleTime.
    staleTime: READINESS_POLL_MS,
    refetchInterval: READINESS_POLL_MS,
    // No retry. A failed readiness probe just means not-ready, the poll above
    // comes round again in five minutes, and the list is waiting on this
    // query's first answer — a retry would double the bound below before the
    // rows could be fetched.
    retry: false,
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
 * Read live ONLY by controls that express what the reader may ask for next —
 * the filter rail. Anything describing the rows on screen reads the value
 * `useContracts` captured with them instead (decision log D13).
 */
export function useItemSurfaceReady(): boolean {
  return useTaxonomy().data?.coverage === 'complete'
}
