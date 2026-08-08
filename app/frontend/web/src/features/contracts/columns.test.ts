// ABOUTME: Column-set invariants that no rendered assertion states directly —
// ABOUTME: what the readiness gate may add, and what it may never change.
import { describe, expect, it } from 'vitest'
import { CONTRACT_TYPES, ITEM_LESS_TYPES, type ContractTypeValue } from './filters'
import { columnsFor, sortableFieldsFor } from './columns'

/** Every segment a column set can be asked for, including "no selection". */
const SEGMENTS: (ContractTypeValue | undefined)[] = [undefined, ...CONTRACT_TYPES]

const BLUEPRINT_KEYS = ['runs', 'me', 'te']

/** Criterion 1.2: ingestion fetches items for none of these three. */
const carriesItems = (segment: ContractTypeValue | undefined) =>
  segment === undefined || !ITEM_LESS_TYPES.includes(segment)

describe('columnsFor', () => {
  it('adds no sortable field with the item-level columns', () => {
    // `sortableFieldsFor` is what `parseContractSearch` reconciles a sort
    // against, and it reads the widest set on purpose — so a readiness flip can
    // never silently reset a sort the reader chose. That is only safe while the
    // gated columns disclose no sort of their own; the moment one does, the
    // parser has to take readiness as an argument and this test says so.
    for (const segment of SEGMENTS) {
      const closed = columnsFor(segment, false).flatMap((c) => (c.sortField ? [c.sortField] : []))
      expect([...sortableFieldsFor(segment)].sort()).toEqual([...new Set(closed)].sort())
    }
  })

  it('adds the three blueprint columns only where the segment can hold items', () => {
    // Criterion 1.2 puts loan and unknown on the item-less side beside courier:
    // ingestion fetches items for none of the three, so a blueprint column on
    // those segments would be blank down its whole length forever — not merely
    // until the next resweep, which is what the readiness gate is for.
    for (const segment of SEGMENTS) {
      const closed = columnsFor(segment, false).map((c) => c.key)
      const open = columnsFor(segment, true).map((c) => c.key)
      if (!carriesItems(segment)) {
        expect(open).toEqual(closed)
        continue
      }
      const at = closed.indexOf('location')
      expect(open).toEqual([...closed.slice(0, at), ...BLUEPRINT_KEYS, ...closed.slice(at)])
    }
  })

  it('never hides a blueprint column at a breakpoint', () => {
    // Criterion 2.2 states the display with no breakpoint exemption, and unlike
    // Collateral or Volume these three are the reason to look at the row.
    const blueprint = columnsFor('item_exchange', true).filter((c) => BLUEPRINT_KEYS.includes(c.key))
    expect(blueprint).toHaveLength(BLUEPRINT_KEYS.length)
    for (const column of blueprint) expect(column.hiddenClass).toBeUndefined()
  })

  it('leaves every column key unique in every set it can produce', () => {
    // The table keys both its <th> and its <td> on column.key; a duplicate
    // renders two React children under one key and drops one of them.
    for (const segment of SEGMENTS) {
      for (const ready of [false, true]) {
        const keys = columnsFor(segment, ready).map((c) => c.key)
        expect(new Set(keys).size).toBe(keys.length)
      }
    }
  })
})
