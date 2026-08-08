// ABOUTME: The contract-type segment control — one toggle per browsable type,
// ABOUTME: each labelled with the count of contracts selecting it would show.
import {
  CONTRACT_TYPES,
  ITEM_BEARING_TYPES,
  ITEM_LESS_TYPES,
  activeSegment,
  isItemLessSelection,
  type ContractSearch,
  type ContractTypeValue,
} from '../filters'
import { columnsFor } from '../columns'

/**
 * The controls the view offers. `loan` and `unknown` are deliberately absent:
 * both stay reachable by URL and counted like every other type, but they are
 * empty or near-empty in The Forge, so they hold no permanent screen space.
 * Promoting one later is additive.
 */
const SEGMENTS: { type?: ContractTypeValue; label: string }[] = [
  { label: 'All' },
  { type: 'item_exchange', label: 'Item exchange' },
  { type: 'auction', label: 'Auction' },
  { type: 'courier', label: 'Courier' },
]

/** What names the view once a single type is in effect — the two without a control included. */
const SEGMENT_TITLES: Record<ContractTypeValue, string> = {
  item_exchange: 'Item Exchange Contracts',
  auction: 'Auction Contracts',
  courier: 'Courier Contracts',
  loan: 'Loan Contracts',
  unknown: 'Unknown Contracts',
}

/**
 * The list heading and document title. A selected segment names the view;
 * without one it falls back to the ships-only pair, which is what the default
 * view still reads.
 */
export function listTitle(search: ContractSearch): string {
  const type = activeSegment(search)
  if (type !== undefined) return SEGMENT_TITLES[type]
  return search.ships_only ? 'Ship Contracts' : 'All Contracts'
}

function sumCounts(counts: Record<string, number>, types: readonly ContractTypeValue[]): number {
  return types.reduce((total, type) => total + (counts[type] ?? 0), 0)
}

/**
 * The navigation a control performs. Both halves of the ships-only rule live
 * here so they travel in one navigation: an item-less segment clears ships-only
 * on the way in — visibly, the checkbox unchecks — and leaving one restores the
 * default by REMOVING the parameter, since the parser reads absence as on and
 * writes "cleared" as an explicit false.
 *
 * The clearing half is a second layer, not the only one: parseContractSearch
 * widens any all-item-less selection on its way through validateSearch, so no
 * test can observe this branch alone (mutation-verified — deleting it changes
 * nothing any lane can see). It stays because Criterion 1.7 is an invariant
 * about a combination that must never exist, and because the restore half
 * below has no such backstop.
 */
function segmentPatch(
  type: ContractTypeValue | undefined,
  leavingItemLess: boolean,
  currentSort: ContractSearch['sort_by'],
): Partial<ContractSearch> {
  const contract_type = type === undefined ? undefined : [type]
  // A sort must not outlive the segment that offered it: a column set with no
  // header for the active sort field would order the list by a criterion the
  // user can neither see nor clear. Removing the keys restores the parser's
  // default, exactly as the ships-only restore below removes rather than sets.
  const sortSurvives = columnsFor(type).some((column) => column.sortField === currentSort)
  const sortReset = sortSurvives ? {} : { sort_by: undefined, sort_direction: undefined }
  if (type !== undefined && ITEM_LESS_TYPES.includes(type)) {
    return { contract_type, ships_only: false, ...sortReset }
  }
  return leavingItemLess
    ? { contract_type, ships_only: undefined, ...sortReset }
    : { contract_type, ...sortReset }
}

export function SegmentTabs({
  search,
  countsSearch,
  counts,
  onSelect,
}: {
  search: ContractSearch
  /**
   * The search `counts` was served under, captured at fetch time (WEB-1).
   * keepPreviousData holds an envelope on screen for the whole of the next
   * request, so numeral interpretation MUST read the captured search — the
   * live one describes counts that have not arrived yet. Clicks and pressed
   * states stay on the live search: they are about where the reader goes,
   * not about what the numbers mean.
   */
  countsSearch: ContractSearch
  /** The envelope's per-type counts, keyed by every type the server enumerates. */
  counts: Record<string, number>
  onSelect: (patch: Partial<ContractSearch>) => void
}) {
  const leavingItemLess = isItemLessSelection(search)
  // The counts' ships-lift state is a property of the request that produced
  // them, not of the URL: while an item-less selection's envelope is on
  // screen, the item-bearing figures in it are ships-lifted.
  const countsFromItemLess = isItemLessSelection(countsSearch)
  const selected = activeSegment(search)
  // What All would land on decides what All may claim: every route into it from
  // an item-less segment restores ships-only, so only a view the reader has
  // already widened counts the item-less types in.
  const allCountsEveryType = !countsFromItemLess && !countsSearch.ships_only

  return (
    <fieldset className="flex flex-wrap items-center gap-1.5">
      <legend className="sr-only">Contract type</legend>
      {SEGMENTS.map((segment) => {
        const active =
          segment.type === undefined ? search.contract_type === undefined : segment.type === selected
        // While an item-less selection's envelope is on screen, its request
        // carried no ships-only filter, so the item-bearing counts in it are
        // lifted — but clicking All OR a typed item-bearing segment RESTORES
        // ships-only, a population those counts cannot describe. No numeral
        // beats a wrong one: All and the typed item-bearing controls all go
        // count-less in that state, and the counts return with the next
        // response after switching. The item-less segment's own numeral is the
        // lifted figure describing the lifted view it serves, so it stays.
        // Per-segment counts otherwise go out exactly as served: every filter
        // but contract_type is applied to them. That stays true of an
        // item-less segment under an item-level filter — the served zero is
        // honest, and the empty state it leads to explains itself.
        const count =
          segment.type === undefined
            ? countsFromItemLess
              ? undefined
              : sumCounts(counts, allCountsEveryType ? CONTRACT_TYPES : ITEM_BEARING_TYPES)
            : countsFromItemLess && ITEM_BEARING_TYPES.includes(segment.type)
              ? undefined
              : (counts[segment.type] ?? 0)
        return (
          <button
            key={segment.type ?? 'all'}
            type="button"
            // aria-pressed on plain buttons rather than a tablist: there are no
            // tab panels here — the toolbar re-filters one region (Criterion 12).
            aria-pressed={active}
            onClick={() => onSelect(segmentPatch(segment.type, leavingItemLess, search.sort_by))}
            className={`inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-md border px-3 text-sm transition-colors duration-150 ${
              active
                ? 'border-brand-dim bg-brand-wash text-brand'
                : 'border-line-strong text-ink-body hover:bg-raised'
            }`}
          >
            {segment.label}
            {count !== undefined ? (
              <>
                {' '}
                <span className="font-mono text-xs">{count.toLocaleString('en-US')}</span>
              </>
            ) : null}
          </button>
        )
      })}
    </fieldset>
  )
}
