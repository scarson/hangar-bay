import { useState } from 'react'
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

// Field-wise equality over ContractSearch: scalars by Object.is, the id-list
// params elementwise. Generic over the keys so a future param cannot silently
// fall outside the comparison.
//
// Exported for its own test. Example-based tests cannot close this predicate: for
// any finite set of fixtures there is a comparator checking exactly the positions
// those fixtures vary; an example rules out the implementations that differ ON it,
// which is never all of them.
// sameSearch.test.ts drives it with GENERATED input against an independent
// reference instead, bounded by that file's MAX_LIST rather than by which cases
// somebody remembered to write.
export function sameSearch(a: ContractSearch, b: ContractSearch): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]) as Set<keyof ContractSearch>
  for (const key of keys) {
    const left = a[key]
    const right = b[key]
    if (Array.isArray(left) && Array.isArray(right)) {
      if (left.length !== right.length || left.some((value, i) => !Object.is(value, right[i]))) return false
    } else if (!Object.is(left, right)) {
      return false
    }
  }
  return true
}

export function useContracts(search: ContractSearch) {
  // The URL updates per keystroke (the URL is the interface), but the request
  // does not: the search text settles for SEARCH_DEBOUNCE_MS before it may
  // change the query key, so typing a word costs one corpus-scale request
  // instead of one per keystroke past MIN_SEARCH_LENGTH. While the text is
  // mid-edit the WHOLE effective query freezes at the last settled one — the
  // keystroke's own side effects (the page-1 reset the search field
  // navigates with) must not fire a request under the OLD text, and a sort
  // click mid-word folds into the settled request instead of doubling it.
  // Everything derived below uses the effective search — the one the request
  // is actually made under — so the fetch-time captures describe the rows
  // they ride with.
  const debouncedSearchText = useDebouncedValue(search.search, SEARCH_DEBOUNCE_MS)
  const searchTextSettled = search.search === debouncedSearchText
  // Settled renders use the live search directly (so every non-search param
  // stays immediate); unsettled renders read the search as of the last
  // settled moment, recorded via the documented adjust-state-during-render
  // pattern. The comparison is by VALUE, so callers that pass a fresh search
  // object every render converge instead of looping. Accepted residual: a
  // sort/segment/Clear click mid-word updates the page chrome (heading,
  // pressed states, sort indicator) from live state while the rows stay
  // under the frozen query for the rest of the debounce window — the
  // row-describing surfaces themselves read fetch-time captures (WEB-1), and
  // the ordinary keepPreviousData refresh indication takes over the moment
  // the text settles.
  const [lastSettled, setLastSettled] = useState(search)
  if (searchTextSettled && !sameSearch(lastSettled, search)) setLastSettled(search)
  const effectiveSearch = searchTextSettled ? search : lastSettled
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
