export const SORT_FIELDS = [
  'date_issued',
  'date_expired',
  'price',
  'collateral',
  'ship_name',
  'volume',
] as const
export type SortField = (typeof SORT_FIELDS)[number]

export const SORT_DIRECTIONS = ['asc', 'desc'] as const
export type SortDirection = (typeof SORT_DIRECTIONS)[number]

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
  is_bpc?: boolean
  page: number
  size: number
  sort_by: SortField
  sort_direction: SortDirection
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

/**
 * validateSearch for the /contracts route. Accepts arbitrary address-bar
 * input and always returns a well-formed ContractSearch — invalid values
 * fall back to defaults rather than throwing.
 */
export function parseContractSearch(raw: Record<string, unknown>): ContractSearch {
  return {
    search: typeof raw.search === 'string' && raw.search.length > 0 ? raw.search : undefined,
    min_price: toNonNegativeNumber(raw.min_price),
    max_price: toNonNegativeNumber(raw.max_price),
    region_ids: toIdArray(raw.region_ids),
    is_bpc: typeof raw.is_bpc === 'boolean' ? raw.is_bpc : undefined,
    page: toBoundedInt(raw.page, 1, Number.MAX_SAFE_INTEGER, DEFAULT_PAGE),
    size: toBoundedInt(raw.size, 1, MAX_SIZE, DEFAULT_SIZE),
    sort_by: SORT_FIELDS.includes(raw.sort_by as SortField)
      ? (raw.sort_by as SortField)
      : 'date_issued',
    sort_direction: SORT_DIRECTIONS.includes(raw.sort_direction as SortDirection)
      ? (raw.sort_direction as SortDirection)
      : 'desc',
  }
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
    is_bpc: s.is_bpc,
    page: s.page,
    size: s.size,
    sort_by: s.sort_by,
    sort_direction: s.sort_direction,
  }
}
