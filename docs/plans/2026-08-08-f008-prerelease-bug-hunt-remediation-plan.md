<!-- ABOUTME: Remediation plan for the confirmed bugs of the 2026-08-08 F008 pre-release bug hunt -->
<!-- ABOUTME: (B1-B7 in the consolidated report). Four PRs; B2's migration PR is held for Sam's review. -->

# F008 Pre-Release Bug-Hunt Remediation Plan (2026-08-08)

**Goal:** Fix the seven confirmed bugs from
[`docs/bug-hunts/2026-08-08-f008-prerelease-consolidated.md`](../bug-hunts/2026-08-08-f008-prerelease-consolidated.md)
before the dev→main release, as four focused PRs. Design decisions D-a–D-k from that report are
documented for Sam and deliberately NOT planned here; out-of-scope findings O1/O2 belong to the
separate test-coverage review task.

**Architecture:** No new components. Three PRs are frontend-contained
(`app/frontend/web/src/features/contracts/`), one is a backend schema change
(`models/contracts.py` + one Alembic migration + `services/contract_service.py`).

**Tech Stack:** existing — React 19 / TanStack, vitest + Playwright; FastAPI / SQLAlchemy 2.0 async /
Alembic, pytest.

## Living Document Contract

This plan is a living document. Every executing agent MUST update it as
execution progresses, not only at completion.

- **On phase claim:** the executor MUST flip the banner to 🚧 IN PROGRESS
  with a claim timestamp (ISO 8601 UTC) and the active branch name. The
  banner MUST NOT include an expected-completion estimate — agents cannot
  reliably estimate their own wall-clock, and a fabricated duration
  becomes a stale anchor that misleads future readers. Followers
  encountering a 🚧 banner determine liveness by observable signals (PR
  existence, recent branch commits), not by arithmetic on expected times.
  See writing-plans-enhanced Step 5's stale-claim reclaim protocol.
- **On phase ship:** the executor MUST update that phase's **Execution
  Status** banner with the shipped commit SHA(s) and date. If a PR is
  open, the PR number and URL MUST appear in the top-of-plan Execution
  Status table.
- **On phase defer:** the executor MUST update the banner with ⏸ status
  AND a prose description of the unblock condition + a link to the
  likely-unblocker artifact (plan page, task, or PR whose own Execution
  Status banner will signal completion). Prose + link is durable across
  paraphrases and scope edits; exact-string coordination between agents
  is not.
- **On PR merge:** the executor MUST record the merge SHA in the banner
  + the top-of-plan Execution Status table.
- **On deviation from the written plan** (scope edits, structural
  refactors, dropped tasks, reordered phases): the executor MUST
  inline-document the deviation in the affected task AND summarize it
  in the top-of-plan Execution Status as a "Deviations" subsection.
  Deviation state MUST NOT live only in PR notes or status reports.
- **On discovery** (pre-existing drift surfaced during execution, new
  bugs found, architectural issues noted): the executor MUST add a
  "Discoveries" subsection at the top of the plan with pointers to the
  files/lines affected. Follow-up dispatches read this subsection to
  avoid duplicate discovery work.

The plan SHOULD reflect reality at the end of every session that touches
it. Anything worth putting in a status report to the user is worth
putting in the plan.

Rationale: `/writing-plans-enhanced` Step 5. Writing at ship time is
cheap; reconstruction by downstream readers is expensive, compounds
across dispatches, and fails silently when state is split across PR
notes and commit messages.

## Execution Status

**Overall:** Not started.

| Phase | Status | Ship SHA(s) | Notes |
|---|---|---|---|
| 1 — parser gaps (B3/B5/B7) | ⬜ Not started | — | — |
| 2 — format fixes (B4/B6) | ⬜ Not started | — | — |
| 3 — segment numerals (B1) | ⬜ Not started | — | — |
| 4 — price nullable (B2) | ⬜ Not started | — | PR to be LEFT OPEN for Sam (`Review — database schema`) |

## Global constraints (every phase)

1. **TDD is mandatory.** BEFORE starting any task: invoke `superpowers:test-driven-development` and
   read `docs/pitfalls/testing-pitfalls.md`. Write the failing test, run it red, implement
   minimally, run it green. BEFORE marking any task complete: review tests against
   testing-pitfalls, verify error paths and edge cases, run the suite green.
2. **Frontend lanes:** `npx eslint .` · `npx tsc -b` · `npm run test` · `npm run test:future-clock` ·
   `npm run e2e` — all green before any frontend PR claims completion. Component tests pass under
   BOTH vitest lanes (fixture dates from `src/test/dates.ts`, never literals — TEST-17).
   `*.test.ts(x)` naming only (TEST-6). This machine: `git checkout --`
   `package-lock.json`/`routeTree.gen.ts` churn before staging (OD6).
3. **Backend runs** serialize on `DATABASE_URL_TESTS=…/hangar_bay_test_f008` with `ESI_USER_AGENT`
   exported; `pdm run lint` before commit; never repo-wide format (ENV-7).
4. **Never weaken an assertion to fix a flake** (TEST-2). If any assertion races or flakes, the fix
   is deterministic synchronization — NOT assertion removal or weakening; if synchronization cannot
   make it reliable, STOP and raise. Commit subjects touching assertions say what happened to them.
5. **Each PR:** Conventional-Commit subjects, `## Merge classification` heading, codex adversarial
   review before merge for Phases 1, 3, 4 (Phase 2 is comment/format-trivial — skip recorded per
   the OD5 precedent); re-run codex on any rework (guardrail: rounds 2-3 historically find defects
   inside fixes). Merge Routine phases on green CI (`gh pr merge --merge --delete-branch`, never
   `--auto`); Phase 4's PR is NOT merged — left open for Sam.
6. **After the group ships:** minimum 3 review rounds from different perspectives (codex rounds
   above count toward this only when they reviewed the final state of each phase).
7. **Phases execute strictly sequentially, in numbered order.** Each phase's branch starts from a
   freshly fetched `origin/dev` AFTER the preceding phase's PR merged (Phases 1 and 3 both may touch
   `pages.test.tsx`; sequential execution is the conflict guard). Phase 4 additionally re-runs its
   migration-freshness protocol (Task 4.1 step 1) immediately before its PR is handed to Sam.

---

## Phase 1 — Parser junk-tolerance gaps (B3, B5, B7) — branch `fix/contract-search-parser-gaps`

**Execution Status:** ⬜ NOT STARTED

**Files:** `app/frontend/web/src/features/contracts/filters.ts`,
`src/features/contracts/components/ContractsPage.tsx`, `src/features/contracts/filters.test.ts`
(and `pages.test.tsx` only if a direction assertion lives there).

### Task 1.1 (B3): integer guard on the six blueprint bounds

- **Current:** `toNonNegativeNumber` (`filters.ts:187-190`) accepts any non-negative number; it
  feeds `min_runs`/`max_runs`/`min_me`/`max_me`/`min_te`/`max_te` (`:248-253`) AND
  `min_price`/`max_price` (`:242-243`). The six bounds are `Optional[int]` server-side
  (`schemas/contracts.py:351-398`); `min_me=5.5` is sent and 422s, collapsing the list view.
- **Desired:** a decimal in any of the six bound params parses to `undefined` (junk falls back,
  nothing sent). `min_price=99.5` MUST keep parsing to `99.5` — prices are legitimately decimal.
- **Approach:** add `toNonNegativeInt` beside `toNonNegativeNumber` (compose: non-negative AND
  `Number.isInteger`); point exactly the six bound fields at it. Do NOT change
  `toNonNegativeNumber` itself (price uses it). Do NOT touch `BlueprintFilter.tsx` — the parser is
  the single enforcement point by design.
- **Failing tests first:** table-driven over ALL SIX bounds (`min_runs`, `max_runs`, `min_me`,
  `max_me`, `min_te`, `max_te` — each is independently wired to the helper, so a missed binding
  must be catchable per-field): decimal → `undefined`; boundary `'0'` → `0`; regression
  `min_price: '99.5'` → `99.5` and `max_price: '99.5'` → `99.5`; and a `toApiQuery` assertion that
  a parsed-out bound sends nothing.

### Task 1.2 (B5): per-field default sort direction, single-sourced

- **Current:** absent `sort_direction` falls back to flat `'desc'` (`filters.ts:260-262`);
  `DEFAULT_DIRECTION` (`ContractsPage.tsx:17-27`) maps `date_expired: 'asc'`. Entering Courier
  sortless reconciles to `date_expired` + `'desc'` — contradicting the direction the same column's
  header click gives.
- **Desired:** absent direction resolves to `DEFAULT_DIRECTION[resolved sort_by]`. Default view
  unchanged by construction (`date_issued` → `'desc'`).
- **Approach:** move `DEFAULT_DIRECTION` (with its comment, verbatim) into `filters.ts` and export
  it; `ContractsPage.tsx` imports it (delete its local copy — it has no other production caller;
  verified by plan review). Rule, stated exactly: a valid explicit `sort_direction` in the URL
  wins; otherwise the direction is `DEFAULT_DIRECTION[reconciled sort_by]` — including when
  `sort_by` itself was explicit. Also update the comment at `e2e/sorting.spec.ts:20`, which names
  `ContractsPage` as `DEFAULT_DIRECTION`'s home (it moves).
- **Failing tests first:** courier + no sort params → `sort_by: 'date_expired'`,
  `sort_direction: 'asc'`; no params at all → `date_issued`/`desc` (regression pin); explicit
  `sort_direction: 'desc'` on courier survives.

### Task 1.3 (B7): dedupe `contract_type`

- **Current (mechanism corrected by plan review):** `?contract_type=courier&contract_type=courier`
  parses to a length-2 array. The ships-only widening and `isItemLessSelection` use `.every()` and
  are NOT affected; what breaks is **single-segment identity** — `activeSegment` (`filters.ts:105`)
  requires exactly one type, so no segment button reads pressed, the list title falls back, and the
  segment-scoped column set is not selected.
- **Desired:** duplicates collapse in the parser; `['courier','courier']` behaves as `['courier']`
  everywhere downstream.
- **Failing test first:** duplicated courier in the raw search parses to `contract_type:
  ['courier']` (and therefore `activeSegment` returns `'courier'`). Do NOT use the ships-only
  widening as the red discriminator — it already passes today via `.every()`.

**After Phase 1:** all five frontend lanes green; codex round; PR
(`fix(web): close the parser's junk-tolerance gaps` — classification Routine); merge on green.

---

## Phase 2 — Format fixes (B4, B6) — branch `fix/composition-format`

**Execution Status:** ⬜ NOT STARTED

**Files:** `src/features/contracts/format.ts`, `src/features/contracts/format.test.ts`.

### Task 2.1 (B4): pluralization that survives the real dogma names

- **Current:** `format.ts:167` appends `s` unconditionally when count ≠ 1 → "Commoditys",
  "Accessoriess", "SKINss".
- **Desired:** count ≠ 1 renders: name ending in `s`/`S` → unchanged ("Accessories", "SKINs");
  name ending in consonant+`y` → `-ies` ("Commodity" → "Commodities"); else `+s`. Count 1 stays
  bare (current behavior).
- **Approach:** a tiny `pluralize(name, count)` local helper. Do NOT add a pluralization library.
- **Failing tests first:** pin against real category names: `Ship`→`Ships`, `Commodity`→
  `Commodities`, `Accessories`→`Accessories`, `SKINs`→`SKINs`, count-1 `Drone`→`Drone`; plus one
  vowel-`y` case (synthetic is fine, e.g. `Decoy`→`Decoys`) so a blanket `endsWith('y')`
  implementation cannot pass — the rule is consonant+`y` only.

### Task 2.2 (B6): fix the provably-false `contractTypeLabel` comment

- **Current:** `format.ts:93-95` comment says unrecognised types keep "Exchange"; the code returns
  `'Unknown'`. Verify by reading the function; if the comment is not actually false, record in
  Deviations and skip (comments may only be removed when provably false — CLAUDE.md).
- **Desired:** comment describes the actual fallback. Comment-only change; no test.

**After Phase 2:** lanes green; PR (`fix(web): pluralize composition categories by name shape` —
Routine; codex skipped as trivial, recorded); merge on green.

---

## Phase 3 — Segment numerals in the item-less state (B1) — branch `fix/segment-count-numerals`

**Execution Status:** ⬜ NOT STARTED

**Files:** `src/features/contracts/components/SegmentTabs.tsx`, its tests (in `pages.test.tsx` or
a colocated file — follow where D11's All-numeral tests live).

### Task 3.1: hide typed item-bearing numerals while `leavingItemLess`

- **Current:** `SegmentTabs.tsx:118-123` — All's numeral is suppressed while `leavingItemLess`
  (D11), but the typed buttons render `counts[segment.type]` raw. Those counts were served
  ships-lifted (`ships_only` cleared per Criterion 1.7), while clicking a typed item-bearing
  button restores ships-only (Criterion 1.9): advertised ~33,800, delivered ~411.
- **Desired:** while `leavingItemLess`, item-bearing typed buttons (`item_exchange`, `auction`)
  show NO numeral — the D11 rule ("no numeral beats a wrong one") applied uniformly. The item-less
  buttons' own numerals (e.g. Courier's) are honest in that state and MUST stay. Numerals return
  with the next response after switching, exactly as All's does.
- **Approach (amended by plan review — the live-flag version contradicts its own claim):**
  interpretation flags MUST come from a **response-captured search**, not the live URL, or the
  numerals "return" immediately on navigation computed from the stale lifted envelope
  (`keepPreviousData` holds the old counts while `leavingItemLess` flips instantly). This is WEB-1
  verbatim and the D13 capture pattern. Implementation: in `ContractsPage`, capture the `search`
  that produced the current `data` (effect keyed on data identity — under `keepPreviousData` the
  effect does not fire during transitions, so the captured search stays the one the held envelope
  was served under); pass it to `SegmentTabs` as the interpretation input for BOTH the existing
  All-numeral logic (`leavingItemLess`/`allCountsEveryType`) and the new typed-numeral
  suppression. Live `search` keeps driving pressed states and click patches. Typed item-bearing
  numerals are suppressed when the CAPTURED search is item-less. Update the comment block at
  `SegmentTabs.tsx:108-117` — its "the number a segment shows is the number selecting it delivers"
  sentence is the one B1 falsifies. Do NOT attempt the mirror-counts envelope change (design
  decision D-b, Sam's call). Do NOT suppress the Courier numeral.
- **Failing tests first:** (1) courier-segment search + lifted envelope: Item exchange and Auction
  buttons carry no numeral, Courier keeps its count; (2) default ships-only search: all numerals
  present (regression pin); (3) the WEB-1 discriminator MUST be **page-level**, not a
  SegmentTabs-prop test (a component test only proves the consumer honors the prop — it passes
  even if ContractsPage captures or passes it wrong): start on Courier, leave the next
  item-bearing request unresolved (the deferred-fetch pattern already established by the WEB-1
  test at `pages.test.tsx:1019`), click the item-bearing segment, assert live pressed state +
  hidden typed numerals, resolve the response, assert numerals return with it.
- **E2E (from plan review):** extend the segments spec (`e2e/segments.spec.ts` — accessible-name
  assertions are established surface there): on the Courier segment, Item exchange/Auction buttons
  expose no count in their accessible names while Courier does.

**After Phase 3:** lanes green; codex round; PR (`fix(web): hide item-bearing segment counts the
click cannot deliver` — Routine; cites D11 precedent); merge on green.

---

## Phase 4 — `price` nullable end-to-end (B2) — branch `fix/price-nullable` — PR LEFT OPEN

**Execution Status:** ⬜ NOT STARTED

**Files (unconditional — round-4 correction):** `app/backend/src/fastapi_app/models/contracts.py`,
new migration under `app/backend/src/alembic/versions/`, `services/contract_service.py`
(NULLABLE_SORTS), `services/watchlist_matcher.py` (Task 4.5), backend tests
(`test_migrations.py` area, `tests/api/test_contract_filters.py`,
`tests/services/test_background_aggregation.py`, `tests/services/test_watchlist_matcher.py`),
frontend `src/features/contracts/components/ContractDetailPage.tsx` + its tests (Task 4.4 — the
detail fix is certain, so ALL FIVE frontend lanes apply to this phase unconditionally), and
regenerated `app/frontend/web/openapi.json` + `src/lib/api/schema.d.ts` (commit only if changed).

### Task 4.1: migration + model

- **Current:** `models/contracts.py:60` `price … nullable=False`; committed ESI snapshot marks
  `[].price` optional; `_build_contract_rows` (`background_aggregation.py:261`) maps
  `c.get("price")` bare. One omitted price → `IntegrityError` → whole-run rollback, repeating
  every run. (Consolidated B2; TEST-22.)
- **Desired:** `price` nullable in model + database; a price-less payload persists with NULL.
  The writer stays `c.get("price")` — absence-≠-zero (ESI-3) is the reason this fix is nullable,
  not a `0.0` default.
- **Approach & sequence (migration protocol amended by plan review — DEPLOY-5):**
  1. BEFORE authoring: on freshly fetched `origin/dev`, `alembic heads` prints exactly one head,
     `685dab7d6df5`. AFTER authoring: exactly one head, the NEW revision. If a sibling migration
     landed meanwhile, create an Alembic merge revision — never re-anchor by hand. Re-run this
     whole check immediately before the PR is handed to Sam.
  2. RED: change the model to `Mapped[Optional[float]] … nullable=True`; run
     `pytest fastapi_app/tests/test_migrations.py::test_migrated_schema_matches_model_metadata`
     → expect FAIL with a schema diff (models ahead of migrations).
  3. Author the migration. It MUST reproduce the current head's lock protocol —
     `685dab7d6df5` opens with `op.execute("SET lock_timeout = '30s'")` because migrations compete
     with the ingestion transaction (implementation-pitfalls DEPLOY-4/DEPLOY-5 territory); copy
     that preamble. Upgrade: `alter_column('contracts', 'price', nullable=True)`. Downgrade: an
     EXPLICIT guard — count NULL-price rows and raise with a message naming them as the reason
     restoring NOT NULL is impossible (an intentional, explained failure, not an incidental
     `NotNullViolation`); then restore NOT NULL. The guard gets a REAL test (round-4 finding: an
     intentional failure branch may not be inspection-only under this plan's own error-path gate):
     a migration test that upgrades to head, inserts a NULL-price row, runs the downgrade, and
     asserts it fails with the specified diagnostic — colocated with `test_migrations.py`'s
     patterns, using its DB lifecycle.
  4. GREEN: equivalence test passes.
- **Do NOT** widen `issuer_id`/`issuer_corporation_id` here (D-g — deliberately excluded to keep
  this migration reviewable).

### Task 4.2: `NULLABLE_SORTS` gains `price`

- **Current:** the comment above `NULLABLE_SORTS` (`contract_service.py:58-65`) names price among
  "non-null columns"; Task 4.1 falsifies that premise.
- **Failing test first (fixture fully specified by plan review — the shared 99999972 fixture is
  unsuitable: all seven rows share `price=1_000_000`, so it cannot discriminate direction):** a NEW
  dedicated fixture in region **99999973** (claimed here per the plan's region protocol), four
  item_exchange contracts in the established `_contract`-local-helper style: 973001 price
  500_000.0, 973002 price 2_000_000.0, 973003 price 9_000_000.0, 973004 with `price=None` (every
  other field per the helper's defaults — no other nullable field left unset beyond what the
  defaults already leave). `test_price_sorts_both_ways_and_leaves_unpriced_contracts_last` in the
  both-ways exact-order shape: asc `[973001, 973002, 973003, 973004]`, desc
  `[973003, 973002, 973001, 973004]`, plus the `ascending[0] != descending[0]` guard. Do NOT touch
  the 99999972 fixture or its tests.
- Then add `SortableContractFields.price` to the frozenset and rewrite the comment (it may no
  longer claim price is non-null).

### Task 4.3 (TEST-22): the spec-minimal ingestion test

- **Failing test first:** in `tests/services/test_background_aggregation.py` — the established
  ingestion seam is around line 974 (plan review located it); follow TEST-14 (module is safe,
  asyncio-only). Feed a payload omitting every field the committed ESI spec snapshot
  (`esi-spec-monitor`'s snapshot of `/v1/contracts/public/{region_id}/`) marks NOT required —
  enumerate them by reading the snapshot's `required` array at execution time and list them in the
  test's docstring. Assert the row builds with `price=None` AND the already-defended defaults hold
  (`collateral=0.0`, `for_corporation=False`, …) so the test is the TEST-22 pattern, not a price
  one-off. Assert the upsert persists the row.
- RED against the pre-4.1 model would be an `IntegrityError`; run order in this plan means it goes
  green immediately after 4.1 — so mutation-verify instead: revert the model's `nullable=True` in
  a scratch copy (cp snapshot, never `git checkout --`), run red, restore, run green (TEST-12).

### Task 4.4: wire + frontend rendering check

- `pdm run export-openapi` then `npm run generate:api`; commit both artifacts ONLY if changed
  (the wire schema is already `Optional[float]`, so likely a no-op — verify, don't assume).
- **Exact acceptance criteria (specified by plan review, red/green split corrected in round 4):**
  a null price renders `—` — with NO unit suffix — on all three surfaces. The list price cell and
  auction starting-bid line already route through `formatIsk` (null → `—`, `format.ts:30`,
  `columns.tsx:115`): those two get already-green **regression pins**, not red tests. The ONE red
  test is the detail page (`ContractDetailPage.tsx:190` appends ` ISK` unconditionally → `— ISK`
  today); fix so a null price renders bare `—`.

### Task 4.5 (plan-review P1): the watchlist matcher must survive a NULL price

- **Current:** `watchlist_matcher.py:173` — a watchlist item with no `max_price` admits a matching
  NULL-priced contract through the `max_price IS NULL` branch; `_render_message`
  (`watchlist_matcher.py:54`) then applies numeric formatting to `None`, and the exception aborts
  the whole matcher run at its job-boundary handler (`:123`).
- **Desired semantics (decision, recorded):** match semantics stay as SQL gives them — a NULL
  price cannot satisfy a numeric `max_price` bound (excluded), and no bound means any price
  including unknown (admitted). Only rendering changes: `_render_message` formats a NULL price as
  `—`, consistent with the list surface. Rationale: a hidden match would silently drop a real
  contract from a user's watchlist over a display concern.
- **Failing tests first:** in `tests/services/test_watchlist_matcher.py` (existing tests assert
  COMPLETE messages, around `:81` — follow that shape and assert the exact full message with `—`
  where the price figure goes, no ` ISK` suffix on the dash, matching Task 4.4's rule): (1) a
  no-price-bound watchlist item + a NULL-priced matching contract → notification created with that
  exact message, run completes; (2) the excluded branch — a numeric `max_price` bound + a
  NULL-priced contract → zero notifications (SQL three-valued logic; this pins the other half of
  the stated semantics).

**After Phase 4:** backend suite green + lint; five frontend lanes green IF frontend files changed;
codex round; PR (`fix(api)!: … ` — NO. The wire contract does not change; subject is
`fix(api): store contracts without a price as NULL, not a crashed run`). **Merge classification:
`Review — database schema` — the PR body says explicitly it awaits Sam and why the alternative
(0.0 default) was rejected (ESI-3). DO NOT MERGE.**

---

## Deferred (recorded per bug-hunt skill)

- **O1 (fixture wire-mirror drift), O2 (type-partition invariant):** deferred to the test-coverage
  review task — see the consolidated report's "Bugs Outside Primary Scope".
- **D-a … D-k:** design decisions requiring Sam; enumerated in the consolidated report. None are
  planned here; D-b is the recorded upgrade path superseding Phase 3's stopgap if taken.
