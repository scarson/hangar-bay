# Testing Pitfalls

How to verify. Read before writing any test; add entries when a testing gap or anti-pattern
let a real bug through. Each entry: **ID — trap — what to do instead — where it bit us.**

## TEST-1 — Service-layer-only tests miss HTTP binding bugs

Constructing a filter/params model directly in Python (`ContractFilters(region_ids=[1])`)
bypasses FastAPI's request binding entirely. A filter can work perfectly at the service
layer while being unreachable over HTTP. **Do instead:** every API-facing filter gets at
least one HTTP-level test that sends real query params through the test client, plus a
schema-level assertion (`app.openapi()`) that the param appears where clients expect it.
**Bit us:** the four ID-list filters were GET-body-bound and silently ignored over HTTP;
all existing tests passed because they only exercised the service layer.

## TEST-2 — Never weaken assertions to fix flaky tests

If an assertion races, flakes, or fails nondeterministically, the fix is deterministic
synchronization or deterministic fixture data — NOT assertion removal or weakening. If
synchronization cannot make the assertion pass reliably, STOP and raise it; do not ship a
weaker test. Commit subjects touching assertions state what happened to them ("add",
"strengthen", "preserve", or explicitly "weaken" with rationale) — never hide erosion behind
"CI stability fix". Prefer mechanism assertions (state observed) over symptom assertions
(timing bounds) where feasible.

## TEST-3 — Ordering assertions need deterministic fixtures with tiebreakers

Tests that assert result order must build fixture data whose sort keys are strictly ordered
(distinct prices, distinct names) or must account for the service's documented tiebreaker.
Relying on insertion order or identical sort keys produces tests that pass locally and flake
elsewhere. See TEST-2 for what NOT to do when that happens.

## TEST-4 — Pagination tests must cross page boundaries

A pagination bug that short-changes, duplicates, or skips items is invisible to any test
that only fetches page 1 of a single-page result set. **Do instead:** fixtures large enough
for ≥2 pages; assert union-of-pages equals the full expected set, intersection is empty,
each non-final page is exactly `size` items, and `total` matches. **Bit us:** joined-row
pagination (SQLA-1) survived a full test suite that never crossed a page boundary.

## TEST-5 — Frontend hook/component tests stub the network at the fetch seam

Stub `fetch` (via `vi.stubGlobal` or openapi-fetch's injectable `fetch` option) with
recorded response shapes; assert both the rendered outcome AND the request URL when the
contract matters (e.g. repeated array params `region_ids=1&region_ids=2`, gated `search`
under 3 chars never sent). Do not mock the hook itself in component tests — that tests the
mock. `await` RTL's `findBy*`/`waitFor` rather than sleeping.

## TEST-6 — Vitest's default glob swallows Playwright specs

Vitest's default include (`**/*.{test,spec}.*`) matches Playwright's `*.spec.ts` files, so
Playwright suites fail under `vitest run` with "Playwright Test did not expect test.describe()
to be called here" — one failed *file* while all unit tests pass. **Do instead:** keep
Playwright in `e2e/` and exclude it in the vitest config
(`exclude: [...configDefaults.exclude, 'e2e/**']` in `vite.config.ts`), and keep unit tests on
the `*.test.ts(x)` suffix. **Bit us:** the first E2E spec landed as `e2e/default-view.spec.ts`
and broke `npm run test` (2026-07-12).

## TEST-7 — Error-state tests must account for the QueryClient's retry policy

The production QueryClient retries failed queries (retry: 1; `useContract` retries non-404s
once), so an error state only renders after ALL attempts fail. A stub that fails only the
first call auto-recovers on the retry and the error branch never shows — the test hangs or
passes vacuously. **Do instead:** responders/stubs fail as many consecutive calls as the
retry policy will issue (list: calls 0 AND 1), then let an explicit user Retry succeed;
assert the alert appears before and the data after. **Bit us:** states.spec.ts error tests
during the 2026-07-12 E2E build-out (caught by the author agent, never shipped red).
