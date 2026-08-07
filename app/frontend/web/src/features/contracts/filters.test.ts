import { describe, expect, it } from 'vitest'
import {
  CONTRACT_TYPES,
  DEFAULT_PAGE,
  DEFAULT_SIZE,
  ITEM_BEARING_TYPES,
  ITEM_LESS_TYPES,
  MIN_SEARCH_LENGTH,
  SORT_FIELDS,
  parseContractSearch,
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
})

describe('toApiQuery', () => {
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
