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
import { useDebouncedValue } from '../../../lib/useDebouncedValue'
import { useTaxonomy } from './useTaxonomy'

// Long enough to bridge keystrokes, short enough that the pause before results
// reads as responsiveness rather than loss. Only the search text is debounced:
// pagination, sorting, and every other filter fire immediately.
const SEARCH_DEBOUNCE_MS = 300

export function useContracts(search: ContractSearch) {
  // The URL updates per keystroke (the URL is the interface), but the request
  // does not: the search text settles for SEARCH_DEBOUNCE_MS before it may
  // change the query key, so typing a word costs one corpus-scale request
  // instead of one per keystroke past MIN_SEARCH_LENGTH. Everything derived
  // below uses the effective search — the one the request is actually made
  // under — so the fetch-time captures describe the rows they ride with.
  const debouncedSearchText = useDebouncedValue(search.search, SEARCH_DEBOUNCE_MS)
  const effectiveSearch = { ...search, search: debouncedSearchText }
  const query = toApiQuery(effectiveSearch)
  const segment = activeSegment(effectiveSearch)
  const enrichmentFiltered = hasEnrichmentDependentFilters(effectiveSearch)
  // A filter that needs an offered item, asked of a type that has none. Both
  // halves are functions of the request, so the pair travels with the rows.
  const itemFilteredItemLessSegment =
    isItemLessSelection(effectiveSearch) && requiresOfferedItem(effectiveSearch)

  // Readiness has to be KNOWN before the rows are fetched, and then travel with
  // them (WEB-1). Two mechanisms, and both are needed:
  //
  //   - `enabled` holds the list until the answer exists, so what the query
  //     function captures is a real answer rather than a not-yet. `isPending`
  //     is false once the query has an answer of ANY kind, an error included,
  //     so an unreachable taxonomy endpoint degrades to not-ready rather than
  //     blocking the list forever.
  //   - readiness is part of the KEY, so a change starts a genuinely new query
  //     rather than trying to redirect the old one. Invalidation alone was not
  //     enough: for a key with no cached data yet, React Query reuses the
  //     in-flight promise, so a flip mid-request left the response landing with
  //     the value captured before it, and no later change to correct it.
  //
  // Keying on readiness cost a second corpus-scale request per cold load when
  // it was considered on its own — the reason it was rejected the first time.
  // With `enabled` in front of it that cost is gone: nothing is fetched until
  // readiness is known, so the key never moves from unknown to known.
  const taxonomy = useTaxonomy()
  const itemSurfaceReady = taxonomy.data?.coverage === 'complete'
  const readinessKnown = !taxonomy.isPending
  return useQuery({
    queryKey: ['contracts', 'list', query, itemSurfaceReady],
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
        countsSearch: effectiveSearch,
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
