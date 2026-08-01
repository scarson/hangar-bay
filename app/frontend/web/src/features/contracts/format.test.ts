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
  const SECOND = 1_000
  const MINUTE = 60 * SECOND
  const HOUR = 60 * MINUTE
  const DAY = 24 * HOUR
  /** An expiry `ms` after `now`, so offsets read as durations instead of ISO arithmetic. */
  const expiringIn = (ms: number) => new Date(now + ms).toISOString()

  it('formats coarse buckets deterministically', () => {
    expect(timeRemaining('2026-07-04T05:30:00Z', now)).toBe('3d 5h')
    expect(timeRemaining('2026-07-01T06:12:00Z', now)).toBe('6h 12m')
    expect(timeRemaining('2026-07-01T00:20:00Z', now)).toBe('20m')
    expect(timeRemaining('2026-06-30T23:59:00Z', now)).toBe('Expired')
    expect(timeRemaining('garbage', now)).toBe('—')
  })

  it('counts the exact expiry instant as expired', () => {
    // The comparison is `ms <= 0`, not `< 0`: a contract whose expiry equals the
    // current instant is gone, not "0m" left.
    expect(timeRemaining(expiringIn(0), now)).toBe('Expired')
    expect(timeRemaining(expiringIn(-1), now)).toBe('Expired')
    expect(timeRemaining(expiringIn(1), now)).not.toBe('Expired')
  })

  it('clamps a sub-minute remainder up to "1m" instead of showing "0m"', () => {
    // Truncating minutes would render "0m" for the entire last minute of a
    // contract's life, which reads as expired while it is still biddable.
    expect(timeRemaining(expiringIn(1), now)).toBe('1m')
    expect(timeRemaining(expiringIn(30 * SECOND), now)).toBe('1m')
    expect(timeRemaining(expiringIn(59 * SECOND), now)).toBe('1m')
    expect(timeRemaining(expiringIn(MINUTE), now)).toBe('1m')
  })

  it('switches buckets only on the exact boundary, truncating rather than rounding up', () => {
    // One second short of a boundary stays in the lower bucket — the display
    // never promises more time than remains.
    expect(timeRemaining(expiringIn(59 * MINUTE + 59 * SECOND), now)).toBe('59m')
    expect(timeRemaining(expiringIn(HOUR), now)).toBe('1h 0m')
    expect(timeRemaining(expiringIn(DAY - SECOND), now)).toBe('23h 59m')
    expect(timeRemaining(expiringIn(DAY), now)).toBe('1d 0h')
    expect(timeRemaining(expiringIn(2 * DAY - SECOND), now)).toBe('1d 23h')
  })

  it('drops the finer unit once a coarser one is in play', () => {
    // The day bucket shows hours and hides minutes; the hour bucket shows
    // minutes and hides seconds. Both floor.
    expect(timeRemaining(expiringIn(3 * DAY + 5 * HOUR + 59 * MINUTE), now)).toBe('3d 5h')
    expect(timeRemaining(expiringIn(6 * HOUR + 12 * MINUTE + 59 * SECOND), now)).toBe('6h 12m')
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
