// ABOUTME: Property-based check of sameSearch against an independent reference deep-equal.
// ABOUTME: Generated inputs up to MAX_LIST elements; example fixtures cannot close this predicate.
import fc from 'fast-check'
import { describe, expect, it } from 'vitest'
import type { ContractSearch } from '../filters'
import { parseContractSearch } from '../filters'
import { sameSearch } from './useContracts'

/**
 * Why generated inputs rather than examples.
 *
 * Adversarial review named a different passing-but-wrong comparator on four separate
 * rounds — `length+sum`, `length+first`, `length+first+last`, `length+slice(0,4)` —
 * and every one of them was correct. That is not a run of bad luck, it is structural:
 * an example fixture only rules out implementations that differ ON that example, so
 * any finite set of examples is satisfied by a comparator checking exactly the
 * positions those examples happen to vary. Adding one more example moves the boundary
 * by one and invites the next counterexample. The regress does not terminate.
 *
 * A bounded exhaustive sweep does not terminate it either: for a domain of maximum
 * length N there is always a `slice(0, N)` implementation correct on the whole domain.
 *
 * Generated input does not escape that bound either, and finite sampling is weaker still.
 * Precisely what this establishes:
 *   - it mutation-kills the named plausible edits (reference equality, either clause of
 *     the compound predicate deleted, order-blind set comparison);
 *   - it kills fixed-prefix comparators through index 23, the deepest-index property
 *     being deterministic rather than sampled;
 *   - it SAMPLES the broader space of pairs up to `MAX_LIST` elements — sampling, so it
 *     does not rule out every implementation with a defect somewhere inside that range;
 *   - a comparator inspecting `MAX_LIST` positions or more passes, and widening that
 *     cutoff is a one-constant change.
 *
 * What changes is the shape of the cost. With examples, each additional position of
 * guarantee is another hand-authored fixture, which is why six review rounds produced six
 * counterexamples. Here the guarantee is one constant: raising `MAX_LIST` widens it for
 * every property at once, and the generator explores the space between rather than only
 * the points someone thought to write down. That is what makes the regress terminate; it
 * is not a proof and is not offered as one.
 *
 * `sameSearch` is exported for this. That is justified here and would not be for a
 * weaker test: the predicate is high blast radius (a wrong answer either freezes the
 * rows against a stale filter, silently, or drives React into "Too many re-renders" and
 * takes the app's main view down) and it is module-private, so there is no other way to
 * put generated input through it.
 */

/** The intended semantics, written from the contract rather than from the implementation. */
function referenceEqual(a: unknown, b: unknown): boolean {
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((value, i) => Object.is(value, b[i]))
  }
  return Object.is(a, b)
}

const base = parseContractSearch({})


// The one number that bounds what these properties prove. A comparator inspecting
// MORE than this many positions would still survive — that residual is inherent to
// testing a predicate over unbounded input and is stated rather than hidden. Note the
// shape of the tradeoff though: widening the guarantee is editing this constant, not
// authoring another fixture, which is the whole reason generated input replaced the
// example-by-example regress.
const MAX_LIST = 24

/**
 * Id lists as the parser can produce them, plus the absent case. Bounded by MAX_LIST
 * like every other generator here, so the file really does have ONE cutoff to raise.
 *
 * The value pool is small so near-equal lists are drawn often enough to be interesting.
 * It is not relied on for the equality side: two independently generated lists of any
 * length rarely collide, so equality is covered deterministically by the reflexivity
 * property, which constructs its pair.
 */
const idList = fc.oneof(
  fc.constant(undefined),
  fc.array(fc.integer({ min: 1, max: 4 }), { maxLength: MAX_LIST }),
)

const withIds = (region_ids: number[] | undefined): ContractSearch => ({ ...base, region_ids })

describe('sameSearch (property-based)', () => {
  it('sees a single-element change at a sampled index', () => {
    // The discriminating property, and it needs a WITNESS rather than luck: two
    // independently generated arrays almost never agree on a long prefix, so a
    // comparator checking only the first k positions is never challenged by random
    // pairs — that is exactly how a fixed-depth implementation survived the first
    // draft of this file. So the pair is CONSTRUCTED: take a list, change one element
    // at a SAMPLED index (`fc.nat() % length` is modulo-biased toward the front, not
    // uniform), and require the predicate to notice. This one samples; the deterministic
    // depth guarantee is the deepest-index property below.
    fc.assert(
      fc.property(
        fc.array(fc.integer({ min: 1, max: 4 }), { minLength: 1, maxLength: MAX_LIST }),
        fc.nat(),
        fc.integer({ min: 1, max: 4 }),
        (xs, rawIndex, replacement) => {
          const index = rawIndex % xs.length
          fc.pre(xs[index] !== replacement)
          const ys = [...xs]
          ys[index] = replacement
          expect(sameSearch(withIds(xs), withIds(ys))).toBe(false)
        },
      ),
      { numRuns: 2000 },
    )
  })

  it('sees a change at index MAX_LIST - 1, deterministically', () => {
    // The sampled-index property above reaches deep positions only by luck, and its
    // index draw is biased toward the front, so a comparator inspecting the first k
    // positions survives unless a long list happens to draw a late index. This
    // pins the length and targets its last index, so on EVERY run it is a counterexample
    // to any fixed-prefix comparator of depth 23 or less. Depth MAX_LIST or more passes;
    // that is the stated cutoff.
    fc.assert(
      fc.property(
        // Pinned to FULL length, not merely bounded by it: fast-check biases array
        // generation toward small sizes, so `maxLength` alone draws long lists so
        // rarely that a depth-20 comparator survived a 1000-run pass. Fixing the
        // length makes the deepest index reachable on every single run.
        fc.array(fc.integer({ min: 1, max: 4 }), { minLength: MAX_LIST, maxLength: MAX_LIST }),
        fc.integer({ min: 1, max: 4 }),
        (xs, replacement) => {
          const last = xs.length - 1
          fc.pre(xs[last] !== replacement)
          const ys = [...xs]
          ys[last] = replacement
          expect(sameSearch(withIds(xs), withIds(ys))).toBe(false)
        },
      ),
      { numRuns: 1000 },
    )
  })

  it('sees a change in LENGTH, at either end', () => {
    fc.assert(
      fc.property(
        fc.array(fc.integer({ min: 1, max: 4 }), { maxLength: MAX_LIST }),
        fc.integer({ min: 1, max: 4 }),
        fc.boolean(),
        (xs, extra, atFront) => {
          const ys = atFront ? [extra, ...xs] : [...xs, extra]
          expect(sameSearch(withIds(xs), withIds(ys))).toBe(false)
        },
      ),
      { numRuns: 500 },
    )
  })

  it('agrees with a reference deep-equal on independently generated pairs', () => {
    // Broad sweep over the whole input space, including the absent/empty cases the
    // constructed properties above do not reach.
    fc.assert(
      fc.property(idList, idList, (left, right) => {
        expect(sameSearch(withIds(left), withIds(right))).toBe(referenceEqual(left, right))
      }),
      { numRuns: 2000 },
    )
  })

  it('is reflexive across fresh array instances, which is what stops the render loop', () => {
    // The production caller rebuilds ContractSearch every render (validateSearch), so
    // equal-by-value lists arrive as distinct objects. Reference comparison here is
    // what React reports as "Too many re-renders".
    fc.assert(
      fc.property(idList, (list) => {
        expect(sameSearch(withIds(list), withIds(list && [...list]))).toBe(true)
      }),
      { numRuns: 500 },
    )
  })

  it('reports a differing scalar as different, for every scalar field', () => {
    // The array clause is covered above; this walks the other branch across the whole
    // key set rather than one representative field, so a key falling outside the
    // comparison cannot hide.
    const probes: Partial<ContractSearch>[] = [
      { search: 'rifter' },
      { min_price: 1 },
      { max_price: 2 },
      { is_bpc: true },
      { ships_only: false },
      { page: 2 },
      { size: 25 },
      { sort_by: 'price' },
      // 'asc' because base is 'desc': a probe equal to base would prove nothing.
      { sort_direction: 'asc' },
      { min_runs: 1 },
      { max_runs: 2 },
      { min_me: 1 },
      { max_me: 2 },
      { min_te: 1 },
      { max_te: 2 },
    ]
    // Guards the list against silent shrinkage — an earlier revision put a trailing
    // comment on one of these lines and commented two probes out of existence.
    expect(probes.length).toBe(15)
    for (const probe of probes) {
      expect(sameSearch(base, { ...base, ...probe })).toBe(false)
    }
  })
})
