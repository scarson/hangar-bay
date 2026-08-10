<!-- ABOUTME: Spec for courier reward-per-jump, asking Sam four decisions and recording what is already settled. -->
<!-- ABOUTME: The jump-count data source is the architectural one; the rest follow from it. -->

# Reward per jump — spec

**Date:** 2026-08-10
**Status:** **Awaiting Sam's decision. Nothing here is implemented.**
**Supersedes nothing.** It consumes two prior artifacts and does not restate them:

- [`2026-08-01-courier-route-jumps-spike.md`](2026-08-01-courier-route-jumps-spike.md) — the bounded
  research spike: measured courier population, cost, the three data-source options, the
  security-preference problem, and an implementation sizing. **Read §3 and §4 before deciding
  Decision 1**; this spec argues against that document's recommendation and the argument only
  makes sense against it.
- **F008 spec §15.2** (`design/features/F008-Type-Aware-Contract-Browsing.md`, "Policy: courier
  contracts") — the decision that couriers are first-class, plus the list of facts the follow-on
  inherits and the display rules it is required to settle explicitly.

---

## 0. What this document is for

Reward per jump is one ratio with one hard question behind it: **what is the denominator?** Every
other choice is downstream of that. This spec asks for four decisions, recommends an answer to
each, and records why — so that whichever way they go, the reasoning survives.

**Decision 1 is architectural and is the reason this is not just a plan.** The spike recommended
buying jump counts from ESI. A survey done *after* the spike (recorded in F008 §15.2) found a
correctness defect in that source which changes the calculus. I think the answer has flipped. Sam
should decide, not me.

## 1. Already settled — do not re-derive

**From the spike and F008 §15.2** (pointers only; those documents are authoritative):

- Cost, population and compression: 115 Forge couriers collapse to 39 distinct system pairs.
- ~9–10% of couriers can never have a jump count, because an endpoint is a player-owned structure
  with no tokenless ESI route. Structural, not fixable.
- The default is **high-security-preferred**, on stated convention rather than inference.
- **Per-row disclosure beats a mode picker** (the Adam4EVE pattern): auto-pick, then have each row
  state which security tier it actually achieved.
- Reward per jump is a **comparison metric, not a quote**; the UI must not imply it is what a
  hauler would charge.
- No surveyed tool ships an ISK-per-jump column at all — an unoccupied niche, and a mild warning
  that the number may be harder to make honest than it looks.

**Already in the code**, so three of the spike's nine work items are done and must not be redone:

| Spike work item | State |
|---|---|
| 2 — `_npc_station_ids` collects **end** locations | ✅ done; it reads both endpoints |
| 3 — resolve both endpoints, stamp `end_location_system_id` | ✅ done; the column exists on `Contract`, carrying a comment saying it is groundwork for exactly this follow-on |
| §9's three free courier columns | ✅ done; `collateral`, `volume`, `reward` and `days_to_complete` all persist, and `reward_per_volume` is already a sortable field |

What is left is the route data itself, the ratio, and the surfaces that read them.

---

## 2. Decision 1 — where jump counts come from **(architectural)**

### The question in one line

Do we buy jump counts from ESI's `/route/` endpoint, or compute them ourselves from a vendored
adjacency graph?

### Why this is open again, having been recommended once

The spike chose ESI (`Option A`) and priced the alternative (`Option B`, vendor an edge list and
run our own search) as expensive. Its stated reason, verbatim in the spike's §3: reproducing CCP's
`secure` / `insecure` semantics "means reimplementing an algorithm we can only observe as a black
box," whose `security_penalty` knob is measurably non-monotonic.

**That pricing is correct, and it is pricing the wrong target.** The follow-up survey then
established (F008 §15.2, "Three correctness traps") that CCP's `secure` is *not* the number we
want:

> ESI's `secure` flag is an *upper bound*, not the shortest high-sec route — Jita → Amarr returns
> 45 jumps when a fully high-sec 34-jump route exists, diverging by up to about a third on long
> routes while agreeing exactly on short ones.

Once "match ESI's semantics" stops being the goal, Option B's dominant cost disappears. The metric
we actually want — *the shortest path using only systems at security ≥ 0.45* — is an unweighted
breadth-first search on a filtered subgraph. That is materially simpler than what the spike priced,
and it is simpler than what ESI does.

### What the defect costs us if we buy from ESI

The error is **not** a uniform offset. It grows with route length and is zero on short routes, so
it does not cancel in a ranking — it systematically inflates the denominator of exactly the
long-haul contracts a reward-per-jump view exists to surface. A 34-jump route billed as 45 reads
~25% cheaper per jump than it is. Reward per jump is a ranking instrument; a length-correlated
denominator error is the one error shape a ranking cannot absorb.

There is a second, sharper problem. F008 §15.2 requires that "does a high-sec route exist?" be
answered *from the returned system list, not the flag*, because `secure` silently returns a
low-sec-crossing route when no high-sec route exists. Under Option A we must therefore fetch the
route, resolve every system on it, and check each one's security — so **both options need
per-system security values**.

**Option A does not need them VENDORED, though, and an earlier draft of this section overstated
that.** Option A only ever needs security for the bounded union of systems appearing on the routes
it fetched — a few hundred, fetchable and cacheable like any other static lookup, using machinery
the repo already has. So this is a point about *data dependency*, not about *distribution*: it
narrows the gap between the options rather than closing it, and it leaves the licensing question
(below) as a cost unique to Option B. That correction weakens the case for B, and it is stated here
rather than buried because it was the strongest supporting argument this spec originally made.

### The two options as they actually stand

| | **A — buy from ESI `/route/`** | **B — vendor adjacency, search ourselves** |
|---|---|---|
| Jump counts | CCP's own, exact for `shortest` | ours; `shortest` verifiable against CCP's |
| High-sec count | **upper bound, up to ~⅓ long** | true shortest high-sec, by construction |
| "No high-sec route exists" | must be derived from the system list | falls out: the search finds no path |
| Disconnected components (Pochven, two Jove pockets) | handled by CCP | must be handled — an unreachable pair is a real answer, not a bug |
| Per-system security data | needed, but **fetchable** for the bounded set on returned routes | needed, and vendored |
| ESI calls, steady state | zero (our own Valkey cache; the POST shape has none of its own) | zero (none at all) |
| ESI-4 exposure | **yes, and already realized** — we send `2026-07-21`, so the legacy GET is already gone and Option A is POST-only (§3) | **none** |
| Refresh burden | none | a vendored file with a staleness story |
| Licensing | none | **a real question — see below** |
| New code | a list-shaped ESI helper, a route cache | a BFS and a data-loading step |

### Recommendation: **B**, with its correctness proved against A

Vendor the adjacency edge list and per-system security, compute both counts ourselves, and
**validate by running our `shortest` against ESI's `shortest` for the live pair set** — roughly 39
pairs in The Forge, ~107 across the sampled regions. Exact agreement on every pair is cheap to
obtain and is what converts "we wrote a BFS" into evidence. Disagreement on any pair stops the
work rather than shipping a number.

That validation is the whole reason to prefer B over A rather than merely tolerate it: it gives a
jump count that is *checkable*, from a source that cannot 404 when the compatibility floor moves.

**Two honest caveats, both of which are Sam's to weigh:**

1. **Licensing is unresolved and is not mine to resolve.** The spike explicitly recorded that
   Fuzzwork has no license page it could find, and that EVE Ref's position on redistributing
   derived data is unverified. The underlying data sits under CCP's developer agreement
   (non-exclusive, non-commercial, use/display/distribute Game Data within an Application).
   Vendoring a third-party CSV into this repository is a distribution decision. **If Sam is not
   comfortable vendoring, that alone selects Option A** and the rest of this spec still stands.
2. **I have not personally fetched or parsed the edge list.** Everything I say about its size and
   row count is the spike's measurement, not mine. The plan's first task is therefore to obtain
   and check it, and the plan is written so that discovering a problem there costs one task rather
   than the wave.

**What would change my mind toward A:** if the validation in the plan's Task 2 shows our BFS
disagreeing with ESI's `shortest` on any live pair for a reason we cannot explain, the graph is
wrong in a way we cannot see, and buying from CCP is better than shipping a number we cannot
justify.

**How the review's corrections moved this, on balance.** Two of them cut in opposite directions and
roughly cancel: the compatibility finding raises Option A's cost (POST-only, no server cache, no
ETag), while the security-data finding lowers it (fetch the bounded set rather than vendor it). The
recommendation stands, but it stands on a narrower margin than the first draft claimed, and the
deciding consideration is now squarely the one only Sam can weigh — **whether vendoring
third-party static data into this repository is acceptable at all.** If it is not, Option A is a
perfectly serviceable answer that costs a systematically inflated denominator on long routes.

---

## 3. Decision 2 — the ESI-4 compatibility interaction **(the fork has already closed)**

**This decision exists only under Option A.** Under Option B there is no `/route/` call and
nothing to migrate.

**Correction, and it invalidates how both prior documents frame this — including this spec's own
first draft.** The spike (§6) and F008 §15.2 both reason from Hangar Bay sending **no**
`X-Compatibility-Date`, therefore sitting on ESI's 2020-01-01 floor, where
`GET /route/{o}/{d}?flag=` still works. That is no longer true, and I restated it without checking.
Verified in source on 2026-08-10: `core/config.py` defines `ESI_COMPATIBILITY_DATE` with a default
of **`2026-07-21`**, `core/esi_client_class.py` sends it on **every** ESI request, and a test pins
it against the drift monitor's snapshot so the two cannot silently diverge.

**This was already written down.** Pitfall **ESI-4** in
[`docs/pitfalls/implementation-pitfalls.md`](../../pitfalls/implementation-pitfalls.md) is marked
Resolved and its "Where It Stands" paragraph records the pin, the cutover, and the instruction
*"Any future work that calls `/route/` must use the POST form."* Nothing here is new information
about the system; it is new information about which documents I read. See the appendix.

`2026-07-21` is above the `2025-09-30` cutover. Three consequences:

- **`GET /route/` is already a 404 for this application.** The legacy shape is not available to us
  today, and the spike's "it works today, unchanged, at the current floor" is stale.
- **"Pin below 2025-09-30" must be struck from the fork.** It is not this feature's header to set.
  It is the application's single ESI contract, and lowering it would change the shape of every ESI
  response the app consumes — rolling back work that has nothing to do with couriers.
- **Option A means the POST shape from day one**:
  `POST /route/{origin_system_id}/{destination_system_id}` with a JSON body
  (`preference: Shorter | Safer | LessSecure`) returning `{"route": [...]}`. That shape is
  documented `not-cached` with no ETag, so every uncached lookup is a real round trip, and it is
  the shape carrying the non-monotonic `security_penalty` knob.

**Recommendation: there is nothing left to decide here.** Option A implements POST; Option B is
untouched. What the correction actually does is **raise Option A's cost** — it loses the
server-side 24h cache and the ETag that made the spike's caching argument work — which is a point
in Option B's favour that neither prior document was in a position to weigh.

**Still non-optional under Option A:** adding the route endpoint to the ESI drift-monitor manifest
(`tools/esi_spec_monitor/manifest.py`), per F008 §15.2. An endpoint outside the manifest is outside
the monitor's lens (ESI-4).

---

## 4. Decision 3 — which security preferences we compute and store

The spike recommended computing all three (`shortest` / `secure` / `insecure`) on the grounds that
3× a trivial number is still trivial, and it removes the need to guess right.

**Recommendation: store two, not three — `shortest` and `high_sec_only`.** `insecure` ("prefer
low-sec") answers a question no surface asks: the default is high-security-preferred, and the
disclosure pattern discloses what a route *achieved*, not what a third preference would have
produced. Storing a third number nothing reads is a column that will drift out of meaning.

Two numbers is also exactly what the disclosure needs: `shortest` is the denominator floor,
`high_sec_only` is the honest one, and **their gap is the risk signal** the spike's §4 recommended
surfacing. A pair supports that; a triple does not improve it.

Under Option B, "high_sec_only" is a real all-high-sec path or *no path at all* — which is strictly
more informative than ESI's `secure`.

**It does NOT give three tiers, and an earlier draft of this section claimed it did.** Two jump
COUNTS answer "did this route leave high-sec"; they cannot separate "crosses low-sec" from
"crosses null-sec", because that distinction is a property of the systems ON the chosen path, not
of its length. Adam4EVE's three-tier display (F008 §15.2) would require retaining the path and
inspecting each system's security — cheap under Option B, since the search already walks it, but a
deliberate extra rather than a free consequence. **The disclosure is therefore two-tier in v1**,
and the implementation plan pins exactly those two values.

---

## 5. Decision 4 — the two display rules F008 §15.2 requires to be explicit

F008 §15.2 flags these because "visibly distinct" admits opposite implementations.

**(a) Where do unknown-jump rows sort, in both directions?**

Recommendation: **unknown always sorts last, under ascending and descending alike** — it is not a
value at either end of the scale. This deliberately breaks sort symmetry, and that is the point:
the alternative (NULLs at one end) puts ~10% of couriers in the "best value" position under one
of the two directions, which is precisely the ESI-3 failure shape this repo has already paid for.
The backend's existing nullable-sort machinery pins NULL placement per direction, so this is a
choice it can already express.

**(b) What does the jumps cell read when the count is unknown, versus genuinely zero?**

Recommendation: unknown reads **"—"**; genuinely zero reads **"0"**.

**The tooltip must not name the player-structure cause, which an earlier draft had it do.** Two
different situations produce an unknown count: an endpoint that could not be resolved to a system
(the player-owned-structure case, ~9–10% of couriers), and a resolved pair with no route between
them — EVE's map has four disconnected components, so Pochven and the two Jove pockets are
genuinely unreachable by gate. Naming the first cause would be a confident falsehood for the
second. Either carry a reason alongside the NULL, or keep the copy generic ("no route available").
The plan takes the generic copy in v1 and records the reason field as deferred. Same-system couriers are
0 jumps, which is a measurement, and the codebase already draws this exact distinction for volume
(`formatVolume(0)` is `'0'` while absent is `'—'`). Reward per jump for a zero-jump contract is
**not** infinity and must not be rendered as one — it is undefined, and displays as "—" with the
jumps cell still reading 0.

---

## 6. What follows from the decisions (not itself a decision)

Recorded so the plan has something to build against; all of it is mechanical once §2–§5 are
answered.

- **Storage.** Denormalized `jumps` / `reward_per_jump` / `route_security_tier` on `Contract` so
  the list can sort without a join, mirroring what the codebase already does for
  `start_location_system_id`. **A durable `system_route_jumps` table is specific to Option A** —
  it exists to stop paying for a network round trip, which is the same durable-cache trick
  `_select_known_station_systems` plays for stations. Option B recomputes deterministically from a
  local graph, so it needs only per-run memoization; an earlier draft presented the table as
  unconditional.
- **Ratio.** `reward / jumps`, guarded at zero, computed on the high-security-preferred count.
- **API.** `jumps` and `reward_per_jump` on the contract schema; both added to
  `SortableContractFields` beside the existing `reward_per_volume`; a per-row security-tier field
  feeding the disclosure.
- **Frontend.** A jumps column and an ISK/jump sort on the courier tab, with per-row tier
  disclosure. No preference picker in v1 (§1: disclosure beats a picker).

## 7. What this explicitly does not do

- **"Jumps from my location."** Out of scope permanently in this line of work per F008 §15.2 §4.2.
  Note that Option B would make it *possible* — that is a consequence to be aware of, not a reason
  to choose B, and it stays out of scope either way.
- **A user-facing route-preference picker.** Demoted to optional refinement by the survey.
- **`security_penalty`.** Measurably non-monotonic; pinned to default and never exposed. Moot
  under Option B.

---

## Appendix — reasoning, alternatives, and what I am unsure of

### How I got to a recommendation that contradicts the spike

I did not set out to overturn it. Reading the spike and F008 §15.2 together, the ordering is what
matters: the spike priced Option B *before* the survey established that ESI's `secure` is an upper
bound. The spike's §3 verdict and the survey's correctness trap have never been read against each
other, because the survey landed as an update to §8's open questions rather than as a revision of
§3's verdict. F008 §15.2 faithfully records both — adjacent, unreconciled.

The single load-bearing observation is that **"shortest path through high-sec only" and "CCP's
`secure` preference" are different functions**, and only the first is the metric a hauler wants.
The spike's cost estimate for B is an estimate for reproducing the second.

### Alternatives considered and rejected

- **Hybrid: ESI for `shortest`, our graph for the high-sec count.** Rejected — once the graph
  exists, using ESI for a number the graph already answers adds a dependency and a second source
  of truth for no gain. It survives only as a validation step, which is what the plan makes it.
- **Ship `shortest` only, defer the high-sec count.** Rejected: F008 §15.2 settles the default as
  high-security-preferred on stated convention, so shipping only `shortest` ships the number the
  convention says is wrong, and the per-row disclosure would have nothing to disclose.
- **Compute the ratio at read time from a join rather than denormalizing.** Deferred rather than
  rejected — it is a sort-performance question, and the perf audit history here favours
  denormalizing what the list sorts on. Named so the plan does not silently assume.
- **Store all three preferences (the spike's recommendation).** Rejected in §4; `insecure` answers
  a question no surface asks.

### What I am still uncertain about

- **Licensing.** The strongest reason to pick A, and I cannot resolve it. Flagged as Sam's.
- **Whether the vendored edge list is actually as clean as the spike measured.** I have not
  fetched it. The plan front-loads this.
- **Whether the ~⅓ divergence matters enough to a hauler to justify vendoring.** I have argued it
  does because the error is length-correlated and the metric is a ranking. That is an argument,
  not a measurement — the measurable version would be to compute the ranking both ways over the
  live courier population and count inversions. **The plan includes that as an early task**, and
  it is the cheapest way to falsify my recommendation before any of it is built.
- **Whether ≥ 0.45 is the right high-sec cutoff.** It matches how EVE displays security (0.421
  displays as 0.4 and is low-sec), and the spike used it. It should be a named constant, not a
  literal.

### What I would add with more time

A count of ranking inversions between the two denominators over the live corpus — see above; it is
in the plan instead. And a check of whether any *other* Hangar Bay surface would want the graph,
which would change B's cost allocation.

### Things I almost missed

That **Option A needs per-system security data anyway.** I initially wrote the comparison table
with "vendors universe data" as a cost unique to B. It is not: F008 §15.2's requirement to answer
"does a high-sec route exist?" from the system list rather than the flag forces per-system
security into either option.

### What an adversarial review then corrected, and the lesson under it

An independent cross-model review of this spec and its plan (2026-08-10) found five factual errors
in the reasoning above. Four are fixed in place, marked where they occur. They are recorded here
rather than quietly edited away, because the pattern behind them is the point:

1. **The compatibility-date premise was false** (§3). I wrote that Hangar Bay sends no
   `X-Compatibility-Date` and sits on the 2020-01-01 floor. It sends `2026-07-21` on every request.
   This changes Decision 2 from a fork into a closed question and raises Option A's cost.
2. **Two jump counts do not yield three security tiers** (§4). Length cannot distinguish low-sec
   from null-sec; only the path's systems can.
3. **`system_route_jumps` is Option A's, not unconditional** (§6).
4. **"Unknown jumps" has two causes, not one** (§5), so the tooltip could not name the
   player-structure one.
5. **Option A needs security VALUES but not vendored ones** — the correction immediately above was
   itself an overstatement, and fixing it weakens my own recommendation.

**The lesson is sharper than "the spike was stale," and worse.** My first instinct on being
corrected was that the spike (2026-08-01) and F008 §15.2 had aged out from under me. That is true
but not the point. `docs/pitfalls/implementation-pitfalls.md` **ESI-4** is marked **Resolved**, and
its "Where It Stands" paragraph already recorded the pin at `2026-07-21`, the `2025-09-30` route
cutover, and the instruction verbatim: *"Any future work that calls `/route/` must use the POST
form."* The answer was written down, in the file this project treats as the read-before-you-code
layer, before I started.

So the three-layer memory pattern worked and I did not read the layer that had the answer. Two
things made that easy, and both are worth naming because they will recur:

- **I read the documents that were ABOUT my topic** (a courier spike, a courier spec section) and
  not the one that was about the *mechanism* my topic depends on. Topic-shaped reading misses
  cross-cutting entries by construction.
- **ESI-4's opening paragraph still describes the historical flaw** ("Hangar Bay sends no such
  header") because that is what the entry is *about*; its current state lives in "Where It Stands"
  at the bottom. Reading the top of a pitfall entry and stopping can therefore return the exact
  opposite of the current state. The plan now tells executors to read that paragraph specifically.

Note also that finding 5 makes my recommendation weaker, not stronger, which is the sort of
correction a review is least likely to produce by accident and most worth keeping.
