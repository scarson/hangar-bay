import { describe, expect, it } from 'vitest'
import type { Contract } from '../../lib/api/client'
import {
  contractTypeLabel,
  formatBlueprintTerms,
  formatComposition,
  formatDate,
  formatDeadline,
  formatIsk,
  formatRewardPerVolume,
  formatVolume,
  locationLabel,
  regionNames,
  routeLabel,
  timeRemaining,
} from './format'

function contract(): Contract {
  return {
    contract_id: 900,
    issuer_id: 1,
    issuer_corporation_id: 1,
    start_location_id: 60003760,
    collateral: 0,
    type: 'item_exchange',
    title: '',
    for_corporation: false,
    date_issued: '2026-07-01T00:00:00Z',
    date_expired: '2026-07-08T00:00:00Z',
    price: 1,
    is_ship_contract: true,
    is_blueprint_copy_contract: false,
    primary_label: 'Tristan',
  }
}

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


describe('contractTypeLabel', () => {
  it('names every contract type ESI can send', () => {
    // ESI's public-contracts `type` is a closed enum. Everything that was not
    // 'auction' used to render as "Exchange", so a courier — a hauling job, not a
    // sale — was labelled as the one thing it is not.
    expect(contractTypeLabel('courier')).toBe('Courier')
    expect(contractTypeLabel('auction')).toBe('Auction')
    expect(contractTypeLabel('item_exchange')).toBe('Exchange')
    expect(contractTypeLabel('loan')).toBe('Loan')
    expect(contractTypeLabel('unknown')).toBe('Unknown')
  })

  it('labels a type outside the map as Unknown, never as an exchange', () => {
    // The server folds out-of-enum stored types into the unknown segment, so a
    // future ESI type must read as what the segment says it is.
    expect(contractTypeLabel('somenewtype')).toBe('Unknown')
  })
})

describe('formatRewardPerVolume', () => {
  it('keeps the fractional part a hauling rate turns on, and dashes an absent one', () => {
    // Rates are compared between jobs, so the two decimals are the difference
    // between "88.89 and 88.12" and two identical-looking rows. Whole rates
    // still group like every other figure in the table.
    expect(formatRewardPerVolume(2000)).toBe('2,000')
    expect(formatRewardPerVolume(80_000_000 / 899_999)).toBe('88.89')
    // The server serves NULL when volume is 0 or missing (nothing to divide
    // by), so the cell has to say "no rate" rather than print 0 or Infinity.
    expect(formatRewardPerVolume(null)).toBe('—')
    expect(formatRewardPerVolume(undefined)).toBe('—')
  })
})

describe('routeLabel', () => {
  it('reads origin to destination, and names an endpoint nothing could resolve', () => {
    // Player structures need an ACL-scoped token to resolve, so ~5% of courier
    // destinations have no name. The cell must read as unknown rather than go
    // blank or invent a station (spec §8).
    expect(routeLabel(courierBetween('Jita IV - Moon 4', 'Amarr VIII'))).toBe(
      'Jita IV - Moon 4 → Amarr VIII',
    )
    expect(routeLabel(courierBetween('Jita IV - Moon 4', null))).toBe(
      'Jita IV - Moon 4 → Unknown structure',
    )
    // The origin is unresolvable about 3% of the time and gets the same reading.
    expect(routeLabel(courierBetween(null, 'Amarr VIII'))).toBe('Unknown structure → Amarr VIII')
  })

  it('never falls back to the raw id the way the Location column does', () => {
    // locationLabel prints "Location 60003760" for an unnamed start. A route
    // must not: an id in a route reads as a place the reader could look up.
    const anonymous = {
      ...courierBetween(null, null),
      start_location_id: 60003760,
      end_location_id: 1038000000001,
    }
    expect(routeLabel(anonymous)).toBe('Unknown structure → Unknown structure')
    expect(routeLabel(anonymous)).not.toContain('60003760')
    expect(routeLabel(anonymous)).not.toContain('1038000000001')
  })
})

describe('formatDeadline', () => {
  it('renders whole days and distinguishes no deadline from a zero-day one', () => {
    expect(formatDeadline(7)).toBe('7d')
    // ESI absence is not zero (pitfall ESI-3): a contract carrying no
    // days_to_complete has nothing to show, while a stored 0 is a real value.
    expect(formatDeadline(0)).toBe('0d')
    expect(formatDeadline(null)).toBe('—')
    expect(formatDeadline(undefined)).toBe('—')
  })
})

describe('regionNames', () => {
  it('reads a region id list as an English list of names', () => {
    // Coverage arrives as ids (Criterion 7.3 — the client must not embed a
    // region literal), and both sentences it feeds are prose: "originating in
    // The Forge only", "no data for Domain and Delve yet".
    expect(regionNames([10000002])).toBe('The Forge')
    expect(regionNames([10000002, 10000043])).toBe('The Forge and Domain')
    expect(regionNames([10000002, 10000043, 10000060])).toBe('The Forge, Domain, and Delve')
  })

  it('names an id the static map does not carry rather than dropping it', () => {
    // CCP adds regions; regions.ts is regenerated by hand. An id this build has
    // no name for still has to appear, or a sentence about three uncovered
    // regions would silently describe two.
    expect(regionNames([10009999])).toBe('Region 10009999')
    expect(regionNames([10000002, 10009999])).toBe('The Forge and Region 10009999')
  })

  it('says nothing at all for an empty list', () => {
    // Nothing ingested yet is a real state (coverage.ingested_region_ids is
    // empty before the first run), and the callers word that case themselves.
    expect(regionNames([])).toBe('')
  })
})

describe('formatComposition', () => {
  const composition = (
    categories: { category_id: number | null; name: string | null; item_row_count: number }[],
    total_volume: number | null = null,
  ) => ({
    categories,
    total_item_rows: categories.reduce((n, c) => n + c.item_row_count, 0),
    total_volume,
  })

  it('names the two largest categories and buckets the rest as other', () => {
    // Criterion 6.1: the breakdown is what lets a reader judge a mixed lot
    // without opening it, and two names plus a remainder is what fits a cell.
    expect(
      formatComposition(
        composition([
          { category_id: 7, name: 'Module', item_row_count: 3 },
          { category_id: 9, name: 'Blueprint', item_row_count: 1 },
          { category_id: 8, name: 'Charge', item_row_count: 1 },
          { category_id: 4, name: 'Material', item_row_count: 1 },
        ]),
      ),
    ).toBe('3 Modules · 1 Blueprint · 2 other')
  })

  it('pluralizes by name shape, so real dogma categories are not garbled', () => {
    // The dogma namespace includes names that are already plural (Accessories,
    // SKINs) and a consonant-y singular (Commodity); a blanket +s renders
    // "Accessoriess", "SKINss", "Commoditys" in the row summary.
    expect(
      formatComposition(
        composition([
          { category_id: 43, name: 'Commodity', item_row_count: 3 },
          { category_id: 39, name: 'Accessories', item_row_count: 2 },
        ]),
      ),
    ).toBe('3 Commodities · 2 Accessories')
    expect(
      formatComposition(composition([{ category_id: 91, name: 'SKINs', item_row_count: 2 }])),
    ).toBe('2 SKINs')
    // Vowel-y names take a plain s — the -ies rule is consonant-y only.
    expect(
      formatComposition(composition([{ category_id: 99, name: 'Decoy', item_row_count: 2 }])),
    ).toBe('2 Decoys')
    // Count one never pluralizes, whatever the shape.
    expect(
      formatComposition(composition([{ category_id: 43, name: 'Commodity', item_row_count: 1 }])),
    ).toBe('1 Commodity')
  })

  it('counts item rows, never summed quantities', () => {
    // A contract of 100 identical drones in one row reads as "1 Drone", not
    // "100 Drones" — the server sends rows and the client must not invent units.
    expect(
      formatComposition(
        composition([
          { category_id: 18, name: 'Drone', item_row_count: 1 },
          { category_id: 6, name: 'Ship', item_row_count: 1 },
        ]),
      ),
    ).toBe('1 Drone · 1 Ship')
  })

  it('puts an unnamed category in the other bucket rather than inventing a label', () => {
    // Two unnameable shapes: the rows whose category could not be determined
    // (category_id null) and a category the name cache has not resolved yet
    // (name null). Neither can be called anything, and "other" is what they are.
    expect(
      formatComposition(
        composition([
          { category_id: 7, name: 'Module', item_row_count: 2 },
          { category_id: null, name: null, item_row_count: 2 },
          { category_id: 42, name: null, item_row_count: 1 },
        ]),
      ),
    ).toBe('2 Modules · 3 other')
  })

  it('adds the total volume when the server measured one', () => {
    expect(
      formatComposition(
        composition(
          [
            { category_id: 7, name: 'Module', item_row_count: 2 },
            { category_id: 6, name: 'Ship', item_row_count: 1 },
          ],
          120_000,
        ),
      ),
    ).toBe('2 Modules · 1 Ship · 120,000 m³')
  })

  it('keeps a blueprint lot’s sub-1 m³ volume rather than calling it zero', () => {
    // The live dev corpus's own numbers (2026-08-08): two blueprint copies at
    // 0.01 m³ each. Through the whole-ISK formatter this line read
    // "2 Blueprints · 0 m³" — a lot claiming to have no volume — on six of the
    // ten composition-bearing contracts in the sample.
    expect(
      formatComposition(
        composition([{ category_id: 9, name: 'Blueprint', item_row_count: 2 }], 0.02),
      ),
    ).toBe('2 Blueprints · 0.02 m³')
  })

  it('says nothing about volume when there is no measurement', () => {
    // A contract whose volume the corpus does not carry gets no "0 m³", which
    // would be a reading rather than the absence of one.
    expect(
      formatComposition(
        composition([
          { category_id: 7, name: 'Module', item_row_count: 2 },
          { category_id: 6, name: 'Ship', item_row_count: 1 },
        ]),
      ),
    ).toBe('2 Modules · 1 Ship')
  })
})

describe('formatVolume', () => {
  it('keeps a small cargo distinguishable from no cargo at all', () => {
    // Live dev corpus, 2026-08-08: 6 of the 10 composition-bearing contracts
    // measured under 1 m³, because a blueprint copy is 0.01 m³ and blueprint
    // lots are exactly what the composition line most often describes. The ISK
    // formatter rendered every one of them as "0" — a lot that says it has no
    // volume, which is a reading rather than the absence of one.
    expect(formatVolume(0.02)).toBe('0.02')
    expect(formatVolume(0.05)).toBe('0.05')
  })

  it('does not leak the float noise a summed volume arrives with', () => {
    // The server sums per-item volumes, so 3 × 0.02 crosses the wire as
    // 0.060000000000000005.
    expect(formatVolume(0.060000000000000005)).toBe('0.06')
    expect(formatVolume(0.20000000000000004)).toBe('0.2')
  })

  it('drops the decimals once they stop carrying information', () => {
    expect(formatVolume(100)).toBe('100')
    expect(formatVolume(470_000)).toBe('470,000')
    expect(formatVolume(12_345.67)).toBe('12,346')
  })

  it('says a volume is below the shown precision rather than calling it zero', () => {
    expect(formatVolume(0.001)).toBe('<0.01')
    // A measured zero is a real reading and keeps its numeral.
    expect(formatVolume(0)).toBe('0')
  })

  it('dashes an absent measurement, like every other figure', () => {
    expect(formatVolume(null)).toBe('—')
    expect(formatVolume(undefined)).toBe('—')
  })
})

describe('formatBlueprintTerms', () => {
  it('reads the terms of a single offered copy, each figure named', () => {
    expect(
      formatBlueprintTerms({ copy_count: 1, runs: 10, material_efficiency: 4, time_efficiency: 8 }),
    ).toBe('10 runs · ME 4 · TE 8')
  })

  it('omits a term the payload does not carry rather than printing a zero', () => {
    // ESI omits `runs` for a blueprint ORIGINAL rather than sending -1 (ESI-3),
    // and a half-enriched copy can be missing any of the three. "ME 0" is a
    // real, meaningfully different blueprint from one whose ME is unknown.
    expect(
      formatBlueprintTerms({ copy_count: 1, runs: null, material_efficiency: 0, time_efficiency: 8 }),
    ).toBe('ME 0 · TE 8')
    expect(
      formatBlueprintTerms({ copy_count: 1, runs: null, material_efficiency: null, time_efficiency: null }),
    ).toBe('')
  })

  it('reads a single run in the singular', () => {
    expect(
      formatBlueprintTerms({ copy_count: 1, runs: 1, material_efficiency: null, time_efficiency: null }),
    ).toBe('1 run')
  })
})

describe('locationLabel', () => {
  it('prefers the resolved name, falls back to the id, and never prints "null"', () => {
    // start_location_id is optional in ESI's schema, so the id fallback has to
    // cope with its absence rather than interpolating a null into the UI.
    expect(locationLabel(contractAt('Jita IV - Moon 4', 60003760))).toBe('Jita IV - Moon 4')
    expect(locationLabel(contractAt(null, 60003760))).toBe('Location 60003760')
    expect(locationLabel(contractAt(null, null))).toBe('Unknown location')
  })
})

function contractAt(name: string | null, id: number | null): Contract {
  return { ...contract(), start_location_name: name, start_location_id: id }
}

function courierBetween(origin: string | null, destination: string | null): Contract {
  return {
    ...contract(),
    type: 'courier',
    price: 0,
    start_location_name: origin,
    start_location_id: null,
    end_location_name: destination,
    end_location_id: null,
  }
}
