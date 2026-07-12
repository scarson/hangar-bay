import { describe, expect, it } from 'vitest'
import {
  DEFAULT_PAGE,
  DEFAULT_SIZE,
  MIN_SEARCH_LENGTH,
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
      is_bpc: undefined,
      page: DEFAULT_PAGE,
      size: DEFAULT_SIZE,
      sort_by: 'date_issued',
      sort_direction: 'desc',
    })
  })

  it('coerces a lone region id into an array and drops junk entries', () => {
    expect(parseContractSearch({ region_ids: 10000002 }).region_ids).toEqual([10000002])
    expect(parseContractSearch({ region_ids: ['10000002', 'abc', -5] }).region_ids).toEqual([
      10000002,
    ])
    expect(parseContractSearch({ region_ids: 'abc' }).region_ids).toBeUndefined()
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
})
