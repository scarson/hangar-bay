import { describe, expect, it } from 'vitest'
import { sortableFieldsFor } from './columns'
import {
  CONTRACT_TYPES,
  DEFAULT_DIRECTION,
  DEFAULT_PAGE,
  DEFAULT_SIZE,
  ITEM_BEARING_TYPES,
  ITEM_LESS_TYPES,
  MAX_SIZE,
  MIN_SEARCH_LENGTH,
  SORT_FIELDS,
  activeSegment,
  hasOfferedItemFilters,
  isItemLessSelection,
  parseContractSearch,
  requiresOfferedItem,
  toApiQuery,
} from './filters'

describe('parseContractSearch', () => {
  it('returns defaults for an empty search object', () => {
    expect(parseContractSearch({})).toEqual({
      search: undefined,
      min_price: undefined,
      max_price: undefined,
      region_ids: undefined,
      contract_type: undefined,
      category_id: undefined,
      group_id: undefined,
      min_runs: undefined,
      max_runs: undefined,
      min_me: undefined,
      max_me: undefined,
      min_te: undefined,
      max_te: undefined,
      is_bpc: undefined,
      ships_only: true,
      page: DEFAULT_PAGE,
      size: DEFAULT_SIZE,
      sort_by: 'date_issued',
      sort_direction: 'desc',
    })
  })

  it('defaults to ships-only (F002 Criterion 1.1); only explicit false widens', () => {
    expect(parseContractSearch({}).ships_only).toBe(true)
    expect(parseContractSearch({ ships_only: true }).ships_only).toBe(true)
    expect(parseContractSearch({ ships_only: false }).ships_only).toBe(false)
    // Junk never widens the default view
    expect(parseContractSearch({ ships_only: 'false' }).ships_only).toBe(true)
  })

  it('coerces a lone region id into an array and drops junk entries', () => {
    expect(parseContractSearch({ region_ids: 10000002 }).region_ids).toEqual([10000002])
    expect(parseContractSearch({ region_ids: ['10000002', 'abc', -5] }).region_ids).toEqual([
      10000002,
    ])
    expect(parseContractSearch({ region_ids: 'abc' }).region_ids).toBeUndefined()
  })

  it('mirrors the server enum of contract types and names the item-less ones', () => {
    // The closed enum the backend 422s against. A member missing here silently
    // drops a whole segment out of the UI's reach, so pin the membership.
    expect([...CONTRACT_TYPES]).toEqual([
      'item_exchange',
      'auction',
      'courier',
      'loan',
      'unknown',
    ])
    expect([...ITEM_LESS_TYPES]).toEqual(['courier', 'loan', 'unknown'])
    expect([...ITEM_BEARING_TYPES]).toEqual(['item_exchange', 'auction'])
    // The two lists partition the enum. A type in neither would be counted in
    // no All total; a type in both would be counted twice.
    expect([...ITEM_BEARING_TYPES, ...ITEM_LESS_TYPES].sort()).toEqual([...CONTRACT_TYPES].sort())
  })

  it('keeps only contract types the backend enum accepts', () => {
    expect(parseContractSearch({ contract_type: 'courier' }).contract_type).toEqual(['courier'])
    expect(
      parseContractSearch({ contract_type: ['item_exchange', 'auction'] }).contract_type,
    ).toEqual(['item_exchange', 'auction'])
    // An unknown member would 422 the request, so it never leaves the parser.
    expect(parseContractSearch({ contract_type: ['auction', 'barter'] }).contract_type).toEqual([
      'auction',
    ])
    expect(parseContractSearch({ contract_type: 'barter' }).contract_type).toBeUndefined()
  })

  it('widens the view when every selected type is item-less (the combination matches nothing)', () => {
    // Ships-only classifies contracts by their offered items, and a courier,
    // loan, or unknown contract carries none — so ships-only + an all-item-less
    // selection is a guaranteed-empty request. Normalizing in the parser means a
    // shared URL, a saved search, and in-app navigation all inherit the rule.
    expect(parseContractSearch({ contract_type: 'loan' }).ships_only).toBe(false)
    expect(parseContractSearch({ contract_type: 'courier', ships_only: true }).ships_only).toBe(
      false,
    )
    expect(
      parseContractSearch({ contract_type: ['courier', 'unknown'] }).ships_only,
    ).toBe(false)
  })

  it('keeps every item-level filter on an item-less selection, widening only ships-only', () => {
    // Criterion 1.7 names ONE pair — ships_only and contract_type — and the
    // reason it may be normalized is that Criterion 1.9 defines a restore for
    // it. The item-level filters have no such restore, so dropping them here
    // would destroy state a segment round-trip should return, and would rewrite
    // a stored saved search from "no matches" into "every item-less contract".
    // A combination that cannot match gets an explanation instead (7.2).
    const courier = parseContractSearch({
      contract_type: 'courier',
      category_id: 6,
      group_id: 25,
      min_runs: 1,
      max_runs: 20,
      min_me: 2,
      max_me: 8,
      min_te: 4,
      max_te: 16,
      is_bpc: true,
    })
    expect(courier.ships_only).toBe(false)
    expect(courier.category_id).toEqual([6])
    expect(courier.group_id).toEqual([25])
    expect(courier.min_runs).toBe(1)
    expect(courier.max_runs).toBe(20)
    expect(courier.min_me).toBe(2)
    expect(courier.max_me).toBe(8)
    expect(courier.min_te).toBe(4)
    expect(courier.max_te).toBe(16)
    expect(courier.is_bpc).toBe(true)
  })

  it('keeps is_bpc=false on an item-less selection, which every such contract satisfies', () => {
    // `is_bpc=false` compiles to NOT EXISTS(offered blueprint copy)
    // (contract_service `~has_copy`), and a contract with no items at all
    // satisfies it. Treating it as unsatisfiable would drop a filter that is
    // not merely legal but true of the entire segment.
    expect(parseContractSearch({ contract_type: 'courier', is_bpc: false }).is_bpc).toBe(false)
  })

  it('leaves ships-only alone for a mixed selection and for no selection', () => {
    // An item-bearing member can still match, so the combination is not
    // guaranteed-empty and the user's ships-only choice stands.
    expect(parseContractSearch({ contract_type: ['item_exchange', 'courier'] }).ships_only).toBe(
      true,
    )
    expect(parseContractSearch({ contract_type: 'auction' }).ships_only).toBe(true)
    // Junk that leaves no valid selection must not widen the default view either.
    expect(parseContractSearch({ contract_type: 'barter' }).ships_only).toBe(true)
  })

  it('coerces taxonomy id lists and drops junk entries', () => {
    expect(parseContractSearch({ category_id: 6 }).category_id).toEqual([6])
    expect(parseContractSearch({ group_id: ['25', 'abc', 0] }).group_id).toEqual([25])
    expect(parseContractSearch({ category_id: 'abc' }).category_id).toBeUndefined()
  })

  it('drops sub-zero blueprint bounds the way it drops sub-zero prices', () => {
    // The backend tolerates min_runs=-1 (an ESI sentinel that never occurs on
    // public data), but the UI never produces a negative, so URL junk below zero
    // falls back to undefined exactly like the price bounds.
    for (const key of ['min_runs', 'max_runs', 'min_me', 'max_me', 'min_te', 'max_te'] as const) {
      expect(parseContractSearch({ [key]: -1 })[key]).toBeUndefined()
      expect(parseContractSearch({ [key]: 'abc' })[key]).toBeUndefined()
      expect(parseContractSearch({ [key]: 0 })[key]).toBe(0)
      expect(parseContractSearch({ [key]: '10' })[key]).toBe(10)
    }
  })

  it('accepts the sort fields the widened server enum added', () => {
    expect([...SORT_FIELDS]).toEqual([
      'date_issued',
      'date_expired',
      'price',
      'collateral',
      'ship_name',
      'volume',
      'reward_per_volume',
      'days_to_complete',
      'buyout',
    ])
    // A widened sort is accepted WITH the segment whose columns disclose it,
    // and reconciled to a visible default without one — a sort no header can
    // show or clear is the invisible-ordering defect (codex PR-C finding).
    expect(
      parseContractSearch({ sort_by: 'reward_per_volume', contract_type: 'courier' }).sort_by,
    ).toBe('reward_per_volume')
    expect(parseContractSearch({ sort_by: 'buyout', contract_type: 'auction' }).sort_by).toBe(
      'buyout',
    )
    expect(
      parseContractSearch({ sort_by: 'days_to_complete', contract_type: 'courier' }).sort_by,
    ).toBe('days_to_complete')
    expect(parseContractSearch({ sort_by: 'buyout' }).sort_by).toBe('date_issued')
    expect(parseContractSearch({ sort_by: 'ship_name', contract_type: 'courier' }).sort_by).toBe(
      'date_expired',
    )
  })

  it('falls back to defaults on invalid page/size/sort values instead of throwing', () => {
    const parsed = parseContractSearch({
      page: 'x',
      size: 9999,
      sort_by: 'DROP TABLE',
      sort_direction: 'sideways',
    })
    expect(parsed.page).toBe(DEFAULT_PAGE)
    expect(parsed.size).toBe(DEFAULT_SIZE)
    expect(parsed.sort_by).toBe('date_issued')
    expect(parsed.sort_direction).toBe('desc')
  })

  it('drops negative min_price/max_price (backend schema minimum is 0, would 422)', () => {
    expect(parseContractSearch({ min_price: -5 }).min_price).toBeUndefined()
    expect(parseContractSearch({ max_price: -0.01 }).max_price).toBeUndefined()
    expect(parseContractSearch({ min_price: '-5' }).min_price).toBeUndefined()
    expect(parseContractSearch({ min_price: 0 }).min_price).toBe(0)
    expect(parseContractSearch({ max_price: '2500000' }).max_price).toBe(2_500_000)
  })

  it('keeps valid values', () => {
    const parsed = parseContractSearch({
      search: 'Tristan',
      min_price: '1000000',
      is_bpc: true,
      page: 3,
      size: 25,
      sort_by: 'price',
      sort_direction: 'asc',
    })
    expect(parsed).toMatchObject({
      search: 'Tristan',
      min_price: 1_000_000,
      is_bpc: true,
      page: 3,
      size: 25,
      sort_by: 'price',
      sort_direction: 'asc',
    })
  })

  it('drops non-integer blueprint bounds instead of sending a value the wire rejects', () => {
    // All six bounds are Optional[int] server-side; a decimal would 422 and
    // collapse the list view, so it is junk and falls back like any other junk.
    for (const key of ['min_runs', 'max_runs', 'min_me', 'max_me', 'min_te', 'max_te'] as const) {
      expect(parseContractSearch({ [key]: '2.5' })[key]).toBeUndefined()
      expect(parseContractSearch({ [key]: 2.5 })[key]).toBeUndefined()
      expect(parseContractSearch({ [key]: '0' })[key]).toBe(0)
    }
  })

  it('keeps decimal prices — only the blueprint bounds are integer-typed on the wire', () => {
    const parsed = parseContractSearch({ min_price: '99.5', max_price: '1000000.25' })
    expect(parsed.min_price).toBe(99.5)
    expect(parsed.max_price).toBe(1000000.25)
  })

  it('defaults the sort direction to the default of the reconciled field, not a flat desc', () => {
    // The courier set carries no Issued column, so its sortless fallback is the
    // Time-left field — whose own default direction is expiring-soonest-first,
    // the same direction its header click gives.
    const courier = parseContractSearch({ contract_type: 'courier' })
    expect(courier.sort_by).toBe('date_expired')
    expect(courier.sort_direction).toBe('asc')
    // An explicit direction in the URL still wins.
    const explicit = parseContractSearch({ contract_type: 'courier', sort_direction: 'desc' })
    expect(explicit.sort_direction).toBe('desc')
    // The default view is untouched: date_issued's own default is desc.
    expect(parseContractSearch({}).sort_direction).toBe('desc')
  })

  it('collapses duplicated contract_type values so single-segment identity holds', () => {
    const parsed = parseContractSearch({ contract_type: ['courier', 'courier'] })
    expect(parsed.contract_type).toEqual(['courier'])
    expect(activeSegment(parsed)).toBe('courier')
  })
})

describe('toApiQuery', () => {
  it('sends nothing for a blueprint bound the parser dropped as junk', () => {
    // openapi-fetch omits undefined-valued params at serialization, so
    // undefined here IS "not sent" — the same convention toEqual relies on
    // throughout this file.
    const query = toApiQuery(parseContractSearch({ min_me: '5.5' }))
    expect(query.min_me).toBeUndefined()
  })

  it('gates search below the backend min_length of 3', () => {
    expect(MIN_SEARCH_LENGTH).toBe(3)
    const base = parseContractSearch({})
    expect(toApiQuery({ ...base, search: 'ab' }).search).toBeUndefined()
    expect(toApiQuery({ ...base, search: '  ab  ' }).search).toBeUndefined()
    expect(toApiQuery({ ...base, search: 'abc' }).search).toBe('abc')
  })

  it('passes filters through and keeps pagination/sort always present', () => {
    const query = toApiQuery(parseContractSearch({ region_ids: [10000002], page: 2 }))
    expect(query.region_ids).toEqual([10000002])
    expect(query.page).toBe(2)
    expect(query.size).toBe(DEFAULT_SIZE)
    expect(query.sort_by).toBe('date_issued')
    expect(query.sort_direction).toBe('desc')
  })

  it('maps ships_only to is_ship_contract=true, omitted entirely when widened', () => {
    expect(toApiQuery(parseContractSearch({})).is_ship_contract).toBe(true)
    expect(toApiQuery(parseContractSearch({ ships_only: false })).is_ship_contract).toBeUndefined()
  })

  it('sends no is_ship_contract for an all-item-less type selection', () => {
    // The parser already widened the view; this is the wire-level proof that a
    // shared ?contract_type=courier URL asks for couriers instead of the
    // guaranteed-empty ships-only intersection.
    const query = toApiQuery(parseContractSearch({ contract_type: 'courier' }))
    expect(query.contract_type).toEqual(['courier'])
    expect(query.is_ship_contract).toBeUndefined()
  })

  it('passes the type, taxonomy, and blueprint filters through unrenamed', () => {
    const query = toApiQuery(
      parseContractSearch({
        contract_type: ['auction'],
        category_id: [6, 9],
        group_id: 25,
        min_runs: 5,
        max_runs: 50,
        min_me: 0,
        max_me: 10,
        min_te: 2,
        max_te: 20,
      }),
    )
    expect(query).toMatchObject({
      contract_type: ['auction'],
      category_id: [6, 9],
      group_id: [25],
      min_runs: 5,
      max_runs: 50,
      min_me: 0,
      max_me: 10,
      min_te: 2,
      max_te: 20,
    })
  })
})

describe('DEFAULT_DIRECTION per field', () => {
  // The expected directions are LITERAL here, never read from DEFAULT_DIRECTION:
  // asserting the parser's output against the same constant the parser reads would
  // agree with whatever that constant said, including a wrong value. Task 1.2 exists
  // because these were once a flat desc, and it shipped with 2 of 9 fields pinned.
  it.each([
    { field: 'date_issued', segment: undefined, expected: 'desc' },
    { field: 'date_expired', segment: undefined, expected: 'asc' },
    { field: 'price', segment: undefined, expected: 'asc' },
    { field: 'ship_name', segment: undefined, expected: 'asc' },
    { field: 'buyout', segment: 'auction', expected: 'asc' },
    { field: 'reward_per_volume', segment: 'courier', expected: 'desc' },
    { field: 'days_to_complete', segment: 'courier', expected: 'desc' },
  ])(
    'sort_by=$field on segment $segment starts $expected',
    ({ field, segment, expected }) => {
      const parsed = parseContractSearch(
        segment === undefined
          ? { sort_by: field }
          : { sort_by: field, contract_type: segment },
      )
      // Anti-vacuity: prove the field survived reconciliation, or the direction
      // assertion below would be about whatever field it fell back to instead.
      expect(parsed.sort_by).toBe(field)
      expect(parsed.sort_direction).toBe(expected)
    },
  )

  it.each(['collateral', 'volume'])(
    '%s carries a DEFAULT_DIRECTION entry no segment can reach',
    (field) => {
      // No column set in columns.tsx declares a sortField for these two, so
      // sortableFieldsFor never contains them and reconcileSort drops the request.
      // Their DEFAULT_DIRECTION entries are therefore unreachable through the
      // parser today. Pinned rather than quietly skipped: adding a sortable column
      // for either, or dropping the constant's entry, should be a deliberate change
      // that shows up here.
      expect(SORT_FIELDS).toContain(field)
      // The literal direction, not merely "an entry exists" — otherwise flipping
      // either value passes and this row is counted as covered while asserting
      // nothing about it.
      const expected: Record<string, 'asc' | 'desc'> = { collateral: 'asc', volume: 'desc' }
      expect(DEFAULT_DIRECTION[field as keyof typeof DEFAULT_DIRECTION]).toBe(expected[field])
      expect(sortableFieldsFor(undefined).has(field as never)).toBe(false)

      const parsed = parseContractSearch({ sort_by: field })
      expect(parsed.sort_by).toBe('date_issued')
      expect(parsed.sort_direction).toBe('desc')
    },
  )

  it('reconciles a widened sort away when several types are selected', () => {
    // Several types means no single segment, so the expressible set is the default
    // one; a courier-only field cannot survive it.
    const parsed = parseContractSearch({
      sort_by: 'reward_per_volume',
      contract_type: ['courier', 'auction'],
    })
    expect(activeSegment(parsed)).toBeUndefined()
    expect(parsed.sort_by).toBe('date_issued')
    expect(parsed.sort_direction).toBe('desc')
  })
})

describe('parseContractSearch junk and bounds', () => {
  it.each([
    { label: 'empty string', raw: '' },
    { label: 'a number', raw: 42 },
    { label: 'an array', raw: ['abc'] },
    { label: 'null', raw: null },
  ])('drops a search of $label', ({ raw }) => {
    expect(parseContractSearch({ search: raw }).search).toBeUndefined()
  })

  it('keeps a non-empty string search verbatim, untrimmed', () => {
    // The URL keeps what was typed; trimming is toApiQuery's job, not the parser's.
    expect(parseContractSearch({ search: '  rifter  ' }).search).toBe('  rifter  ')
  })

  it.each([
    { label: 'a string', raw: 'true' },
    { label: 'a number', raw: 1 },
    { label: 'null', raw: null },
  ])('drops an is_bpc of $label', ({ raw }) => {
    expect(parseContractSearch({ is_bpc: raw }).is_bpc).toBeUndefined()
  })

  it.each([true, false])('keeps a genuine boolean is_bpc (%s)', (raw) => {
    expect(parseContractSearch({ is_bpc: raw }).is_bpc).toBe(raw)
  })

  it.each([
    { label: 'zero', raw: 0 },
    { label: 'negative', raw: -3 },
    { label: 'fractional', raw: 1.5 },
    { label: 'junk', raw: 'abc' },
  ])('falls a page of $label back to the default', ({ raw }) => {
    expect(parseContractSearch({ page: raw }).page).toBe(DEFAULT_PAGE)
  })

  it('keeps page 1, the minimum boundary', () => {
    expect(parseContractSearch({ page: 1 }).page).toBe(1)
  })

  it('keeps size at exactly MAX_SIZE and falls back one past it', () => {
    // The cap is the request-cost ceiling; off-by-one here is the whole point.
    expect(parseContractSearch({ size: MAX_SIZE }).size).toBe(MAX_SIZE)
    expect(parseContractSearch({ size: MAX_SIZE + 1 }).size).toBe(DEFAULT_SIZE)
  })

  it.each([
    { label: 'zero', raw: 0 },
    { label: 'negative', raw: -1 },
    { label: 'fractional', raw: 10.5 },
  ])('falls a size of $label back to the default', ({ raw }) => {
    expect(parseContractSearch({ size: raw }).size).toBe(DEFAULT_SIZE)
  })

  it('keeps size 1, the minimum boundary', () => {
    expect(parseContractSearch({ size: 1 }).size).toBe(1)
  })

  it.each(['region_ids', 'category_id', 'group_id', 'contract_type'])(
    'reads an empty %s array as absent, not as an empty filter',
    (key) => {
      // An empty list must mean "no filter". Sending [] would compile to an
      // IN () that matches nothing, turning a cleared control into a blank page.
      expect(parseContractSearch({ [key]: [] })[key as 'region_ids']).toBeUndefined()
    },
  )
})

describe('activeSegment', () => {
  it('is undefined when nothing is selected', () => {
    expect(activeSegment(parseContractSearch({}))).toBeUndefined()
  })

  it('is undefined when several types are selected', () => {
    const parsed = parseContractSearch({ contract_type: ['courier', 'auction'] })
    expect(parsed.contract_type).toHaveLength(2)
    expect(activeSegment(parsed)).toBeUndefined()
  })
})

describe('toApiQuery search gating', () => {
  it('sends the TRIMMED search value, not the raw one', () => {
    // The URL keeps what the reader typed, spaces and all; the wire must carry the
    // trimmed value. Passing s.search through raw satisfies every other assertion in
    // this file, so without this the regression is invisible.
    expect(toApiQuery(parseContractSearch({ search: '  rifter  ' })).search).toBe('rifter')
  })

  it('gates on the TRIMMED length, so padded sub-minimum text is still withheld', () => {
    // '  ab  ' is 6 characters raw and 2 trimmed. Measuring the raw length would send
    // it and earn a 422 from the backend's min_length.
    const padded = ' '.repeat(4) + 'a'.repeat(MIN_SEARCH_LENGTH - 1)
    const parsed = parseContractSearch({ search: padded })
    expect(parsed.search).toBe(padded) // still in the URL: the reader is mid-typing
    expect(toApiQuery(parsed).search).toBeUndefined() // but never on the wire
  })

  it('sends a value that reaches the minimum only after trimming', () => {
    const exact = '  ' + 'a'.repeat(MIN_SEARCH_LENGTH) + '  '
    expect(toApiQuery(parseContractSearch({ search: exact })).search).toBe(
      'a'.repeat(MIN_SEARCH_LENGTH),
    )
  })
})

describe('hasOfferedItemFilters', () => {
  // Not a dead export: FilterRail calls it inside hasActiveFilters to decide whether
  // the rail shows an active-filter state. It had no test of its own, so the whole
  // predicate could be inverted or emptied without anything failing.

  const OFFERED_ITEM_FILTER_CASES: [string, Partial<Record<string, unknown>>][] = [
    ['category_id', { category_id: [6] }],
    ['group_id', { group_id: [25] }],
    ['min_runs', { min_runs: 1 }],
    ['max_runs', { max_runs: 10 }],
    ['min_me', { min_me: 1 }],
    ['max_me', { max_me: 10 }],
    ['min_te', { min_te: 1 }],
    ['max_te', { max_te: 10 }],
    ['is_bpc', { is_bpc: true }],
  ]

  it.each(OFFERED_ITEM_FILTER_CASES)('counts %s as an offered-item filter', (_key, raw) => {
    // Parametrized over the whole set rather than a sampled pair: a member dropped
    // from OFFERED_ITEM_FILTERS is a filter the rail stops reporting as active, and
    // one hand-picked example cannot see which member went.
    expect(hasOfferedItemFilters(parseContractSearch(raw))).toBe(true)
  })

  it.each([
    ['min_runs', { min_runs: 0 }],
    ['max_runs', { max_runs: 0 }],
    ['min_me', { min_me: 0 }],
    ['max_me', { max_me: 0 }],
    ['min_te', { min_te: 0 }],
    ['max_te', { max_te: 0 }],
  ])('counts %s=0 as set, because zero is a real bound here', (_key, raw) => {
    // ME 0 and TE 0 are real blueprints and 0 runs is a real bound, so the predicate
    // has to test PRESENCE, not truthiness. A `.some((key) => Boolean(search[key]))`
    // refactor passes every positive-valued case above while reporting these six as
    // inactive — the rail would stop showing a filter the reader had set.
    expect(hasOfferedItemFilters(parseContractSearch(raw))).toBe(true)
  })

  it('is false for a search carrying none of them', () => {
    // The negative arm, and the reason the positives are not vacuous: a predicate
    // hardcoded to `true` would pass all nine cases above.
    expect(hasOfferedItemFilters(parseContractSearch({ min_price: 1_000_000 }))).toBe(false)
    expect(hasOfferedItemFilters(parseContractSearch({}))).toBe(false)
  })

  it('counts is_bpc=false, which requiresOfferedItem deliberately does not', () => {
    // The two predicates split exactly here and the split is load-bearing.
    // `is_bpc=false` is a filter the user set, so the rail must show it as active —
    // but it compiles to NOT EXISTS(offered copy), which every item-less contract
    // satisfies, so it must NOT make the selection unsatisfiable. Folding the two
    // together in either direction breaks one of them.
    const search = parseContractSearch({ is_bpc: false })
    expect(hasOfferedItemFilters(search)).toBe(true)
    expect(requiresOfferedItem(search)).toBe(false)
  })
})

describe('isItemLessSelection', () => {
  it('is true for an empty selection, because every one of its zero types is item-less', () => {
    // Deliberate and pinned rather than incidental: `[].every()` is vacuously true, so
    // an empty contract_type array reads as an all-item-less selection and stands the
    // item-level controls down. The reachable shape is `undefined` (no selection),
    // which returns false — the guard above `.every()` is what separates them, and
    // removing it would make "no selection at all" hide the item filters site-wide.
    // The empty array is built by overriding a real parse, because the parser itself
    // never produces one — which is exactly why this arm needs stating rather than
    // discovering.
    expect(isItemLessSelection({ ...parseContractSearch({}), contract_type: [] })).toBe(true)
    expect(isItemLessSelection(parseContractSearch({}))).toBe(false)
  })

  it.each(ITEM_BEARING_TYPES)('is false as soon as %s is selected', (bearing) => {
    // Parametrized over the whole item-bearing set rather than naming one: a predicate
    // written as `!selected.includes('item_exchange')` satisfies the courier and
    // courier+item_exchange cases and still misclassifies an auction-only selection as
    // item-less, standing down the item filters on a segment that carries items.
    expect(isItemLessSelection(parseContractSearch({ contract_type: bearing }))).toBe(false)
    expect(
      isItemLessSelection(parseContractSearch({ contract_type: ['courier', bearing] })),
    ).toBe(false)
  })

  it('is true for a selection of only item-less types', () => {
    expect(isItemLessSelection(parseContractSearch({ contract_type: 'courier' }))).toBe(true)
  })
})

describe('price bounds reject junk of every shape', () => {
  it.each([
    ['non-numeric text', 'abc'],
    ['an empty string', ''],
    ['whitespace', '   '],
    ['Infinity', Infinity],
    ['a NaN', NaN],
    ['a partially numeric string', '12abc'],
    ['a lone sign', '-'],
  ])('drops %s rather than binding it', (_label, value) => {
    // The negative-value case is pinned already; these are the OTHER ways a hand-edited
    // URL reaches the parser. Each shape fails toNumber by a different route — Number()
    // returning NaN, the empty-string short circuit, and Number.isFinite rejecting an
    // infinity — so one example cannot stand for the rest (TEST-28: one behaviour,
    // several routes to it).
    expect(parseContractSearch({ min_price: value }).min_price).toBeUndefined()
    expect(parseContractSearch({ max_price: value }).max_price).toBeUndefined()
  })
})

describe('toApiQuery passes is_bpc through unchanged', () => {
  it.each([
    ['true', true],
    ['false', false],
  ])('sends is_bpc=%s to the API', (_label, value) => {
    // false is the case that matters: a truthiness-based mapping would drop it, and the
    // request would silently ask for every contract instead of only those with no
    // offered copy. Asserted as a strict identity so `undefined` cannot pass for false.
    expect(toApiQuery(parseContractSearch({ is_bpc: value })).is_bpc).toBe(value)
  })

  it('leaves is_bpc undefined when the user set no such filter', () => {
    // Named precisely: toApiQuery returns an OWN `is_bpc` property holding undefined.
    // Omission from the wire happens one layer down, in openapi-fetch's serialization,
    // and is covered there — claiming omission here would describe the wrong layer.
    expect(toApiQuery(parseContractSearch({})).is_bpc).toBeUndefined()
  })
})
