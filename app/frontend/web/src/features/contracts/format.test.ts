import { describe, expect, it } from 'vitest'
import type { Contract } from '../../lib/api/client'
import { formatDate, formatIsk, primaryLabel, timeRemaining } from './format'

function contract(items: Partial<Contract['items'][number]>[], title = ''): Contract {
  return {
    contract_id: 900,
    issuer_id: 1,
    issuer_corporation_id: 1,
    start_location_id: 60003760,
    type: 'item_exchange',
    status: 'outstanding',
    title,
    for_corporation: false,
    date_issued: '2026-07-01T00:00:00Z',
    date_expired: '2026-07-08T00:00:00Z',
    price: 1,
    is_ship_contract: true,
    items: items.map((item, index) => ({
      record_id: index + 1,
      type_id: 1,
      quantity: 1,
      is_included: true,
      is_singleton: false,
      ...item,
    })),
  } as Contract
}

describe('primaryLabel', () => {
  it('prefers the included ship over modules listed first (fitted-hull contracts)', () => {
    const fitted = contract([
      { type_name: 'Medium Auxiliary Nano Pump I', category: null },
      { type_name: 'Myrmidon', category: 'ship' },
      { type_name: 'Medium Auxiliary Nano Pump II', category: null },
    ])
    expect(primaryLabel(fitted)).toBe('Myrmidon')
  })

  it('falls back to the first included item when nothing is categorized', () => {
    expect(primaryLabel(contract([{ type_name: 'Tritanium', category: null }]))).toBe('Tritanium')
  })

  it('ignores excluded (asked-for) ships', () => {
    const askedFor = contract([
      { type_name: 'Module', category: null },
      { type_name: 'Dominix', category: 'ship', is_included: false },
    ])
    expect(primaryLabel(askedFor)).toBe('Module')
  })

  it('uses title, then contract id, when items carry no names', () => {
    expect(primaryLabel(contract([{ type_name: null }], 'My Deal'))).toBe('My Deal')
    expect(primaryLabel(contract([{ type_name: null }], ''))).toBe('Contract 900')
  })
})

describe('timeRemaining', () => {
  const now = Date.parse('2026-07-01T00:00:00Z')

  it('formats coarse buckets deterministically', () => {
    expect(timeRemaining('2026-07-04T05:30:00Z', now)).toBe('3d 5h')
    expect(timeRemaining('2026-07-01T06:12:00Z', now)).toBe('6h 12m')
    expect(timeRemaining('2026-07-01T00:20:00Z', now)).toBe('20m')
    expect(timeRemaining('2026-06-30T23:59:00Z', now)).toBe('Expired')
    expect(timeRemaining('garbage', now)).toBe('—')
  })
})

describe('formatIsk', () => {
  it('groups with fixed locale and dashes nulls', () => {
    expect(formatIsk(374_999_999)).toBe('374,999,999')
    expect(formatIsk(null)).toBe('—')
  })
})

describe('formatDate', () => {
  it('renders the UTC calendar day regardless of the viewer timezone', () => {
    // A UTC-midnight timestamp must read "Jul 1", not "Jun 30" (which is what a
    // local-zone formatter yields for any viewer west of UTC). Pins the UTC
    // formatter so the list matches the detail view's UTC datetime.
    expect(formatDate('2026-07-01T00:00:00Z')).toBe('Jul 1')
    expect(formatDate('garbage')).toBe('—')
  })
})
