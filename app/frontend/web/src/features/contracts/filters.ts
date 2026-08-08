import type { components } from '../../lib/api/schema'
// Runtime-safe despite the apparent cycle: columns.tsx imports only TYPES from
// this module, so the erased edge leaves filters → columns acyclic.
import { sortableFieldsFor } from './columns'

export const SORT_FIELDS = [
  'date_issued',
  'date_expired',
  'price',
  'collateral',
  'ship_name',
  'volume',
  'reward_per_volume',
  'days_to_complete',
  'buyout',
] as const
export type SortField = (typeof SORT_FIELDS)[number]

export const SORT_DIRECTIONS = ['asc', 'desc'] as const
export type SortDirection = (typeof SORT_DIRECTIONS)[number]

export type ContractTypeValue = components['schemas']['ContractType']

/**
 * The backend's closed contract-type enum, mirrored so the parser can drop a
 * value that would 422. `satisfies` fails the build if a member here stops
 * being one the server accepts; UnmirroredContractTypes below fails it in the
 * other direction, when the server gains a member this list does not carry.
 */
export const CONTRACT_TYPES = [
  'item_exchange',
  'auction',
  'courier',
  'loan',
  'unknown',
] as const satisfies readonly ContractTypeValue[]

/** Admits only the empty union, so anything left over is a compile error. */
type Exhausted<T extends never> = T

/**
 * The server contract types CONTRACT_TYPES leaves out — none, or the build
 * fails on this line. `satisfies` above cannot stand in for it: it checks that
 * every member listed is one the server accepts, not that the list exhausts
 * the server's enum. The requirement belongs beside the list because a type
 * the mirror omits is one the UI never parses out of a URL, offers no control
 * for, and leaves as an unreachable segment.
 */
export type UnmirroredContractTypes = Exhausted<
  Exclude<ContractTypeValue, (typeof CONTRACT_TYPES)[number]>
>

/**
 * The types that carry no items. Ships-only classifies a contract by its
 * offered items, so none of these can ever satisfy it — selecting only these
 * and keeping ships-only on asks for a guaranteed-empty result.
 */
export const ITEM_LESS_TYPES: readonly ContractTypeValue[] = ['courier', 'loan', 'unknown']

/**
 * The types that carry items, and so the only ones a ships-only view can show.
 * They are what the All segment counts while ships-only is on: the item-less
 * counts served beside them are computed with ships-only lifted, so they
 * describe a view All is not — adding them in would overstate it.
 */
export const ITEM_BEARING_TYPES: readonly ContractTypeValue[] = ['item_exchange', 'auction']

/** Backend ContractFilters.search has min_length=3; shorter values 422. */
export const MIN_SEARCH_LENGTH = 3
export const DEFAULT_PAGE = 1
export const DEFAULT_SIZE = 50
export const MAX_SIZE = 100

export interface ContractSearch {
  search?: string
  min_price?: number
  max_price?: number
  region_ids?: number[]
  contract_type?: ContractTypeValue[]
  category_id?: number[]
  group_id?: number[]
  min_runs?: number
  max_runs?: number
  min_me?: number
  max_me?: number
  min_te?: number
  max_te?: number
  is_bpc?: boolean
  /** F002 Criterion 1.1: the default view is ship contracts only. */
  ships_only: boolean
  page: number
  size: number
  sort_by: SortField
  sort_direction: SortDirection
}

/**
 * The one type in effect, or undefined for no selection — or for several, which
 * only a hand-edited URL produces. It names the view and, through `columnsFor`,
 * selects the columns the rows are described with (spec §8). It lives beside
 * the search it reads rather than beside either consumer: the segment control
 * asks what the URL selects, while the list asks what the rows on screen were
 * fetched under, and those are the same question at two different moments.
 */
export function activeSegment(search: ContractSearch): ContractTypeValue | undefined {
  return search.contract_type?.length === 1 ? search.contract_type[0] : undefined
}

/**
 * The filter params that read the item columns F008 added — taxonomy ids and
 * the three blueprint ranges. They are the only filters a half-enriched corpus
 * answers short, so they are the only ones a readiness warning may be about.
 *
 * `is_bpc` is deliberately absent even though it is an item-level filter:
 * `is_blueprint_copy` has been ingested since M1, so it answers exactly as
 * completely mid-resweep as it does after one.
 */
const ENRICHMENT_DEPENDENT_FILTERS = [
  'category_id',
  'group_id',
  'min_runs',
  'max_runs',
  'min_me',
  'max_me',
  'min_te',
  'max_te',
] as const satisfies readonly (keyof ContractSearch)[]

export function hasEnrichmentDependentFilters(search: ContractSearch): boolean {
  return ENRICHMENT_DEPENDENT_FILTERS.some((key) => search[key] !== undefined)
}

function toNumber(value: unknown): number | undefined {
  const n =
    typeof value === 'number' ? value : typeof value === 'string' && value !== '' ? Number(value) : NaN
  return Number.isFinite(n) ? n : undefined
}

/**
 * Price bounds mirror the backend's `min_price`/`max_price` schema minimum of 0:
 * negative values (typeable past the inputs' `min="0"`, or hand-edited into a
 * shared URL) 422 the request, so they fall back to undefined here — the same
 * junk-tolerance contract toIdArray applies to the ID lists.
 *
 * The blueprint bounds go through here too, one notch stricter than the wire
 * allows: the backend accepts `min_runs=-1` because ESI publishes it as a
 * sentinel, but no control in this UI produces a negative, so a sub-zero value
 * in the URL is junk and falls back rather than filtering on a sentinel.
 */
function toNonNegativeNumber(value: unknown): number | undefined {
  const n = toNumber(value)
  return n !== undefined && n >= 0 ? n : undefined
}

function toBoundedInt(value: unknown, min: number, max: number, fallback: number): number {
  const n = toNumber(value)
  return n !== undefined && Number.isInteger(n) && n >= min && n <= max ? n : fallback
}

function toIdArray(value: unknown): number[] | undefined {
  const raw = Array.isArray(value) ? value : value === undefined ? [] : [value]
  const ids = raw
    .map(toNumber)
    .filter((n): n is number => n !== undefined && Number.isInteger(n) && n > 0)
  return ids.length > 0 ? ids : undefined
}

function toContractTypes(value: unknown): ContractTypeValue[] | undefined {
  const raw = Array.isArray(value) ? value : value === undefined ? [] : [value]
  const types = raw.filter((entry): entry is ContractTypeValue =>
    CONTRACT_TYPES.includes(entry as ContractTypeValue),
  )
  return types.length > 0 ? types : undefined
}

/**
 * validateSearch for the /contracts route. Accepts arbitrary address-bar
 * input and always returns a well-formed ContractSearch — invalid values
 * fall back to defaults rather than throwing.
 */
export function parseContractSearch(raw: Record<string, unknown>): ContractSearch {
  const contractTypes = toContractTypes(raw.contract_type)
  // Ships-only asks for a contract with an offered ship in it, so pairing it
  // with a selection of nothing but item-less types requests a combination that
  // can never match. Widening here rather than in a component means a shared
  // URL, an applied saved search, and in-app navigation all get the same
  // treatment — and the ships-only checkbox visibly unchecks rather than
  // silently contradicting the results.
  const itemLessOnly =
    contractTypes !== undefined && contractTypes.every((type) => ITEM_LESS_TYPES.includes(type))
  return {
    search: typeof raw.search === 'string' && raw.search.length > 0 ? raw.search : undefined,
    min_price: toNonNegativeNumber(raw.min_price),
    max_price: toNonNegativeNumber(raw.max_price),
    region_ids: toIdArray(raw.region_ids),
    contract_type: contractTypes,
    category_id: toIdArray(raw.category_id),
    group_id: toIdArray(raw.group_id),
    min_runs: toNonNegativeNumber(raw.min_runs),
    max_runs: toNonNegativeNumber(raw.max_runs),
    min_me: toNonNegativeNumber(raw.min_me),
    max_me: toNonNegativeNumber(raw.max_me),
    min_te: toNonNegativeNumber(raw.min_te),
    max_te: toNonNegativeNumber(raw.max_te),
    is_bpc: typeof raw.is_bpc === 'boolean' ? raw.is_bpc : undefined,
    // Default ON; only an explicit false in the URL widens to all contracts.
    ships_only: itemLessOnly ? false : raw.ships_only !== false,
    page: toBoundedInt(raw.page, 1, Number.MAX_SAFE_INTEGER, DEFAULT_PAGE),
    size: toBoundedInt(raw.size, 1, MAX_SIZE, DEFAULT_SIZE),
    sort_by: reconcileSort(raw.sort_by, contractTypes),
    sort_direction: SORT_DIRECTIONS.includes(raw.sort_direction as SortDirection)
      ? (raw.sort_direction as SortDirection)
      : 'desc',
  }
}

/**
 * A sort no column of the active segment can disclose would order the list
 * invisibly — no header, no aria-sort, nothing to clear. Reconciled in the
 * parser so deep links, saved-search apply, Clear filters, and every
 * navigation get the identical treatment (the same reasoning as the
 * item-less ships-only widening above). The courier set carries no Issued
 * column, so its fallback is the Time-left field every set shares.
 */
function reconcileSort(
  rawSort: unknown,
  contractTypes: ContractTypeValue[] | undefined,
): SortField {
  const requested = SORT_FIELDS.includes(rawSort as SortField)
    ? (rawSort as SortField)
    : 'date_issued'
  const segment = contractTypes?.length === 1 ? contractTypes[0] : undefined
  const expressible = sortableFieldsFor(segment)
  if (expressible.has(requested)) return requested
  return expressible.has('date_issued') ? 'date_issued' : 'date_expired'
}

/**
 * URL state → API query object. Gates `search` below MIN_SEARCH_LENGTH:
 * a 1–2-char value stays in the URL (the user is mid-typing) but is never
 * sent — the backend would reject it with a 422.
 */
export function toApiQuery(s: ContractSearch) {
  const trimmed = s.search?.trim()
  return {
    search: trimmed !== undefined && trimmed.length >= MIN_SEARCH_LENGTH ? trimmed : undefined,
    min_price: s.min_price,
    max_price: s.max_price,
    region_ids: s.region_ids,
    contract_type: s.contract_type,
    category_id: s.category_id,
    group_id: s.group_id,
    min_runs: s.min_runs,
    max_runs: s.max_runs,
    min_me: s.min_me,
    max_me: s.max_me,
    min_te: s.min_te,
    max_te: s.max_te,
    is_bpc: s.is_bpc,
    is_ship_contract: s.ships_only ? true : undefined,
    page: s.page,
    size: s.size,
    sort_by: s.sort_by,
    sort_direction: s.sort_direction,
  }
}
