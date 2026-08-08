// ABOUTME: Column-set invariants that no rendered assertion states directly —
// ABOUTME: what the readiness gate may add, and what it may never change.
import { describe, expect, it } from 'vitest'
import { CONTRACT_TYPES, type ContractTypeValue } from './filters'
import { columnsFor, sortableFieldsFor } from './columns'

/** Every segment a column set can be asked for, including "no selection". */
const SEGMENTS: (ContractTypeValue | undefined)[] = [undefined, ...CONTRACT_TYPES]

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

  it('adds exactly one column when the corpus is enriched, and never to couriers', () => {
    for (const segment of SEGMENTS) {
      const closed = columnsFor(segment, false).map((c) => c.key)
      const open = columnsFor(segment, true).map((c) => c.key)
      // Couriers carry no items, so nothing item-derived can describe them.
      if (segment === 'courier') expect(open).toEqual(closed)
      else expect(open).toEqual([...closed.slice(0, closed.indexOf('location')), 'blueprint', ...closed.slice(closed.indexOf('location'))])
    }
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
