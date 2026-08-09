// ABOUTME: Exhaustive check of sameSearch against a reference deep-equal over a closed domain.
// ABOUTME: Example fixtures cannot close this predicate; every finite set admits a wrong comparator.
import { describe, expect, it } from 'vitest'
import type { ContractSearch } from '../filters'
import { parseContractSearch } from '../filters'
import { sameSearch } from './useContracts'

/**
 * Why exhaustive rather than example-based.
 *
 * Adversarial review named a new passing-but-wrong comparator on each of four
 * rounds — `length+sum`, then `length+first`, then `length+first+last` — because
 * an example only rules out implementations that differ on THAT example. The
 * regress does not terminate: a fixture set varying k positions is satisfied by a
 * comparator checking those k positions.
 *
 * So this enumerates every id list over a 3-symbol alphabet up to length 3 (41
 * lists, 1681 ordered pairs) and requires sameSearch to agree with a reference
 * deep-equal on every one. Any implementation that survives is correct on the whole
 * domain, which is what "closed" has to mean here — no comparator checking a fixed
 * set of positions can pass, and neither can a digest (count, sum, hash), because
 * each admits a counterexample INSIDE the domain.
 */
const ALPHABET = [10000002, 10000043, 10000030]

function everyList(maxLength: number): (number[] | undefined)[] {
  const lists: (number[] | undefined)[] = [undefined, []]
  let frontier: number[][] = [[]]
  for (let length = 0; length < maxLength; length++) {
    frontier = frontier.flatMap((prefix) => ALPHABET.map((id) => [...prefix, id]))
    lists.push(...frontier)
  }
  return lists
}

/** The intended semantics, written independently of the implementation. */
function referenceEqual(a: unknown, b: unknown): boolean {
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((value, i) => Object.is(value, b[i]))
  }
  return Object.is(a, b)
}

const base = parseContractSearch({})

describe('sameSearch (exhaustive)', () => {
  it('agrees with a reference deep-equal on every region_ids pair in the domain', () => {
    const lists = everyList(4)
    // undefined + [] + 3 + 9 + 27 + 81. Pinned so the enumeration cannot silently
    // shrink and leave the sweep passing over a domain too small to discriminate.
    // Length 4 specifically: at length 3 a comparator checking first/second/last
    // covers every position and is CORRECT on the domain, so the domain has to be
    // deeper than the widest positional comparator it is meant to exclude.
    expect(lists.length).toBe(122)

    const disagreements: string[] = []
    for (const left of lists) {
      for (const right of lists) {
        const a: ContractSearch = { ...base, region_ids: left }
        const b: ContractSearch = { ...base, region_ids: right }
        const expected = referenceEqual(left, right)
        if (sameSearch(a, b) !== expected) {
          disagreements.push(`${JSON.stringify(left)} vs ${JSON.stringify(right)}`)
        }
      }
    }
    expect(disagreements).toEqual([])
  })

  it('is reflexive over fresh object instances, which is what stops the render loop', () => {
    for (const list of everyList(4)) {
      expect(sameSearch({ ...base, region_ids: list }, { ...base, region_ids: list && [...list] })).toBe(true)
    }
  })

  it('reports a differing scalar as different, for every scalar field', () => {
    // The array clause is exhaustive above; this covers the other branch's reach
    // across the whole key set rather than one representative field.
    const probes: Partial<ContractSearch>[] = [
      { search: 'rifter' }, { min_price: 1 }, { max_price: 2 }, { is_bpc: true },
      { ships_only: false }, { page: 2 }, { size: 25 }, { sort_by: 'price' },
      // 'asc' because base is 'desc': a probe equal to base would prove nothing.
      { sort_direction: 'asc' },
      { min_runs: 1 }, { max_runs: 2 },
      { min_me: 1 }, { max_me: 2 }, { min_te: 1 }, { max_te: 2 },
    ]
    // Guards the list against silent shrinkage — an earlier revision put a trailing
    // comment on this line and commented two probes out of existence.
    expect(probes.length).toBe(15)
    for (const probe of probes) {
      expect(sameSearch(base, { ...base, ...probe })).toBe(false)
    }
  })
})
