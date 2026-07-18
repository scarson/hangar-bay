# Testing Pitfalls

Test scenario checklist for reviewing coverage of any feature. Every item on this list exists because it catches bugs that have occurred in real codebases. Items marked with **🔥 Found in this project** were discovered here specifically. Unmarked items are universal — bugs we haven't made *yet* in this project, but that have bitten other projects hard enough to be worth testing against. Do not deprioritize an unmarked item because it lacks a marker.

> **Relationship to implementation-pitfalls.md:** `implementation-pitfalls.md` specifies *what* to implement and *why*. This document specifies *how to verify* those implementations work correctly. Cross-references between the two are noted inline.

---

## How to Use This Document

**If you're writing tests:** Go to the relevant topic sections below, read the checklist items, and verify your test suite covers each one that applies. Unchecked items are gaps — either add a test or explicitly note why the item doesn't apply to this feature.

**If you're reviewing tests:** Use the checklist to audit coverage gaps. A passing test suite with missing coverage is worse than a failing test suite with complete coverage — you don't know what's actually protected.

**If you're maintaining this document:** When a real bug slips through to production or staging because of a missing test, add the check item to the appropriate section with the 🔥 marker and a one-line note about the observed failure mode. See §How to Add a Testing-Pitfall at the end.

---

## 1. Test Output Pristine

Test output MUST be clean for the suite to pass — no stray errors, warnings, or stack traces. If a test legitimately produces errors (e.g. it's verifying error handling), capture them explicitly and assert on their content. Silent error spam in test output hides real failures.

- [ ] **No unexpected stderr in passing tests.** Any stderr output from a passing test must be explicitly asserted on, or the test is lying about what it verifies.
- [ ] **No unhandled promise rejections / uncaught exceptions.** These often appear as warnings rather than test failures; configure your runner to fail on them.
- [ ] **Deprecation warnings fail the suite or are explicitly tracked.** Silently-warned deprecations become hard breaks on the next runtime upgrade.
- [ ] **Test output doesn't contain debug prints.** Debug statements that escaped into production tests are sometimes the only evidence of a half-finished implementation.

---

## 2. Skipped Tests Are Not Passing Tests

A test that's `skip`ped, `xit`'d, `pending`, or `@Ignore`d is a test that's not running. A CI job that says "100 tests passed, 5 skipped" is NOT the same as "105 tests passed."

- [ ] **No unexplained skips in the suite.** Every skipped test has a comment explaining why it's skipped and under what condition it should be re-enabled.
- [ ] **Skips with a linked issue/ticket.** A skip without follow-up context is forgotten work.
- [ ] **CI distinguishes skipped from passed in its summary.** If the report doesn't separate them, skipped failures hide.
- [ ] **Skip counts are tracked over time.** Growing skip count = eroding coverage.

---

## 3. Error Path Coverage

Silent error swallowing is one of the largest bug categories in any codebase. Every error path must be tested explicitly — not just "the happy path works."

- [ ] **Each error branch has a test that triggers it.** If a function has 5 ways to return an error, there are 5 tests covering each one.
- [ ] **Error messages are asserted, not just error presence.** `expect(err).toBeTruthy()` doesn't catch "wrong error returned"; `expect(err.message).toMatch(/expected pattern/)` does.
- [ ] **Information leakage via error codes checked.** When a handler must return the same status code regardless of whether a resource exists (anti-enumeration), test that ALL error paths return the same status — including DB errors on post-lookup queries that leak existence.
- [ ] **Error-path side effects verified.** If an error path is supposed to roll back state / release a lock / clear a cache, assert that it did.
- [ ] **Error-path resource cleanup verified.** Acquired resources (file handles, DB connections, semaphores) must be released even on error. Test with `defer`-equivalent patterns or explicit cleanup assertions.

---

## 4. Negative Property Testing

Happy-path tests prove "it works" for one input. Negative property tests prove "it doesn't break" under stress, boundaries, and adversarial input. The latter catches the bugs that ship.

- [ ] **Cleanup and eviction.** When code accumulates state (maps, caches, queues), test that stale entries are eventually cleaned up. Don't just test "it works" — test "it doesn't leak."
- [ ] **Bounded growth.** For any in-memory data structure that grows with external input, test that it has a maximum size or eviction policy. Simulate 1000+ entries and verify memory is bounded.
- [ ] **Case sensitivity where identity matters.** When a string key is used for identity (email, username, path), test that case variations are treated consistently. `Admin@Example.com` and `admin@example.com` must be the same identity — or consistently different ones.
- [ ] **Empty / null / zero inputs.** Every parameter that accepts a value should be tested with empty string, null, zero, empty array, empty map. "Did not crash" is not the same as "handled correctly."
- [ ] **Oversized inputs.** Long strings, deeply nested structures, large collections. Where are your truncation / rejection boundaries, and are they enforced?
- [ ] **Unicode / encoding edge cases.** Multi-byte chars, combining sequences, RTL text, emoji, zero-width joiners, NUL bytes. Anywhere strings cross a boundary (storage, display, comparison) needs this.

---

## 5. Concurrency & TOCTOU

If the code can be executed concurrently, test it concurrently. Single-threaded happy-path tests don't catch race conditions.

- [ ] **Multi-step flows under concurrent access.** When a flow reads state then writes state (check-then-act), test two callers racing through the same flow simultaneously. Use a barrier / sync primitive to ensure they hit the critical section at the same time — `WaitGroup` / `Promise.all` alone doesn't guarantee simultaneity.
- [ ] **"Use once" tokens consumed correctly.** Any token that should be single-use (password reset, verification code, invitation) must be tested with two concurrent consumers. Exactly one must succeed.
- [ ] **Rate-limit enforcement under concurrency.** Count-then-insert rate limits can be bypassed by concurrent requests that all read the same count before any insert. Test with burst requests.
- [ ] **Idempotency under retry/concurrency.** If an operation should be idempotent (accepting an invitation twice, retrying a failed payment), test concurrent execution — the second attempt must not produce a 500 from a constraint violation.
- [ ] **Bootstrap / first-time races.** First-user, first-org, or any "only if none exist" flow tested with concurrent attempts. Exactly one must win.

---

## 6. Boundary & Configuration Validation

Configuration errors, bad boundaries, and missing validation are a surprisingly large portion of production incidents. Test the edges.

- [ ] **Default values are tested.** What does the code do when a config value is absent? Crash? Use a default? Silently use zero? All three are possible; the right behavior needs a test.
- [ ] **Invalid config is rejected at load time.** A system that loads invalid config, then crashes on first use of it, surfaces the error too late. Test that config validation runs at load.
- [ ] **Environment-specific behavior.** If code behaves differently in dev vs. prod (feature flags, degraded modes), test both paths. Don't assume dev-tested code works in prod.
- [ ] **Feature flag flip behavior.** Test both flag-on and flag-off paths. A feature behind a flag that's never tested with the flag off can't be safely rolled back.
- [ ] **Timeout and retry boundaries.** If a caller retries 3 times with 5s timeouts, test what happens on the 4th call and on a request that takes 4.9s. The edges matter.

---

## 7. Test Infrastructure Hygiene

The test suite itself is code. It decays if not maintained. Messy test infrastructure produces flaky tests, which produce lost confidence, which produce skipped tests (see §2).

- [ ] **No shared mutable state between tests.** Each test should set up its own state and tear it down. Tests that depend on previous tests' state are order-dependent and flaky.
- [ ] **Setup / teardown covers the failure case.** If setup partially succeeds then teardown fails, the next test starts from a corrupted state. Teardown must be robust to partial-setup states.
- [ ] **Test doubles are minimal and honest.** A mock that returns fixed data is testing the mock, not the code. Use real implementations where feasible; mock only external boundaries.
- [ ] **No hardcoded time-of-day or timezone assumptions.** Tests that pass at 09:00 UTC but fail at 23:00 UTC are flaky by design. Use injected clocks for time-sensitive tests.
- [ ] **No network calls in unit tests.** A unit test that hits a real API is an integration test with a misleading name. Either mock the boundary or move it to the integration suite.

---

## 8. Project-Specific Pitfalls (Hangar Bay)

Disciplines discovered in *this* project's own history. Each is marked **🔥** and keeps its load-bearing `TEST-N` ID (referenced from handoff docs, CLAUDE.md, and session memory). These are richer than one-line checks; read the full entry before relying on it.

- [ ] **🔥 TEST-1 — Service-layer-only tests miss HTTP binding bugs.** Constructing a filter/params model directly in Python (`ContractFilters(region_ids=[1])`) bypasses FastAPI's request binding entirely. A filter can work perfectly at the service layer while being unreachable over HTTP. **Do instead:** every API-facing filter gets at least one HTTP-level test that sends real query params through the test client, plus a schema-level assertion (`app.openapi()`) that the param appears where clients expect it. **Bit us:** the four ID-list filters were GET-body-bound and silently ignored over HTTP; all existing tests passed because they only exercised the service layer. See implementation-pitfalls.md FASTAPI-1.

- [ ] **🔥 TEST-2 — Never weaken assertions to fix flaky tests.** If an assertion races, flakes, or fails nondeterministically, the fix is deterministic synchronization or deterministic fixture data — NOT assertion removal or weakening. If synchronization cannot make the assertion pass reliably, STOP and raise it; do not ship a weaker test. Commit subjects touching assertions state what happened to them ("add", "strengthen", "preserve", or explicitly "weaken" with rationale) — never hide erosion behind "CI stability fix". Prefer mechanism assertions (state observed) over symptom assertions (timing bounds) where feasible.

- [ ] **🔥 TEST-3 — Ordering assertions need deterministic fixtures with tiebreakers.** Tests that assert result order must build fixture data whose sort keys are strictly ordered (distinct prices, distinct names) or must account for the service's documented tiebreaker. Relying on insertion order or identical sort keys produces tests that pass locally and flake elsewhere. See TEST-2 for what NOT to do when that happens.

- [ ] **🔥 TEST-4 — Pagination tests must cross page boundaries.** A pagination bug that short-changes, duplicates, or skips items is invisible to any test that only fetches page 1 of a single-page result set. **Do instead:** fixtures large enough for ≥2 pages; assert union-of-pages equals the full expected set, intersection is empty, each non-final page is exactly `size` items, and `total` matches. **Bit us:** joined-row pagination (implementation-pitfalls.md SQLA-1) survived a full test suite that never crossed a page boundary.

- [ ] **🔥 TEST-5 — Frontend hook/component tests stub the network at the fetch seam.** Stub `fetch` (via `vi.stubGlobal` or openapi-fetch's injectable `fetch` option) with recorded response shapes; assert both the rendered outcome AND the request URL when the contract matters (e.g. repeated array params `region_ids=1&region_ids=2`, gated `search` under 3 chars never sent). Do not mock the hook itself in component tests — that tests the mock. `await` RTL's `findBy*`/`waitFor` rather than sleeping.

- [ ] **🔥 TEST-6 — Vitest's default glob swallows Playwright specs.** Vitest's default include (`**/*.{test,spec}.*`) matches Playwright's `*.spec.ts` files, so Playwright suites fail under `vitest run` with "Playwright Test did not expect test.describe() to be called here" — one failed *file* while all unit tests pass. **Do instead:** keep Playwright in `e2e/` and exclude it in the vitest config (`exclude: [...configDefaults.exclude, 'e2e/**']` in `vite.config.ts`), and keep unit tests on the `*.test.ts(x)` suffix. **Bit us:** the first E2E spec landed as `e2e/default-view.spec.ts` and broke `npm run test` (2026-07-12).

- [ ] **🔥 TEST-7 — Error-state tests must account for the QueryClient's retry policy.** The production QueryClient retries failed queries (retry: 1; `useContract` retries non-404s once), so an error state only renders after ALL attempts fail. A stub that fails only the first call auto-recovers on the retry and the error branch never shows — the test hangs or passes vacuously. **Do instead:** responders/stubs fail as many consecutive calls as the retry policy will issue (list: calls 0 AND 1), then let an explicit user Retry succeed; assert the alert appears before and the data after. **Bit us:** `states.spec.ts` error tests during the 2026-07-12 E2E build-out (caught by the author agent, never shipped red). Relates to §3 Error Path Coverage.

- [ ] **🔥 TEST-8 — Two `role="status"` nodes coexist during list loading.** The loading skeleton (`ContractTable.tsx` `role="status"` named "Loading contracts") and the always-mounted results live region are both `role="status"` while a fetch is in flight, so a `getByRole('status')` assertion polling during load hits a Playwright strict-mode violation (multiple matching nodes). **Do instead:** synchronize on the skeleton unmounting (`waitForDataRendered` / skeleton count 0) before asserting on the results live region; never weaken the assertion to a `.first()`/`.all()` workaround that papers over the ambiguity. **Bit us:** DISC-EXEC-1, Phase 0 of the M2 EVE SSO plan (2026-07-12).

- [ ] **🔥 TEST-9 — Every fixture-lane E2E spec must intercept `GET /me`.** Once the header issues a real `/me` identity request, any fixture-lane spec that does NOT stub `/me` leaks a live request into the mocked lane. **Do instead:** every fixture-lane spec calls `interceptCurrentUser` (401 by default) in every test, even ones that don't otherwise touch auth. **Bit us:** M2 Phase 8 frontend auth-header work (2026-07-12).

- [ ] **🔥 TEST-10 — `ASGITransport` does not run lifespan; wire `app.state` manually in the fixture.** `httpx.ASGITransport` bypasses the app's lifespan startup, so any app-state set up in a `lifespan` handler (`app.state.redis`, `app.state.http_client`) is never populated for tests built on it. **Do instead:** the `auth_client` test fixture sets `app.state.redis` / `app.state.http_client` by hand, and depends on `httpx_mock` structurally so no auth test can reach the network. **Bit us:** M2 Phase 6 auth API route tests (2026-07-12).

- [ ] **🔥 TEST-11 — Writer-side bulk inserts need a test that crosses one chunk boundary.** A bulk insert split into fixed-size chunks (asyncpg caps a statement at 32767 bind params, so the matcher inserts ≤1000 rows/statement) has an off-by-one or last-chunk-dropped bug that is invisible to any test whose match set fits in a single chunk. **Do instead:** arrange a match set strictly larger than one insert chunk (e.g. > `NOTIFICATION_INSERT_CHUNK` rows) and assert every row lands — `created == len(match_set)` and the union of inserted dedup keys equals the expected set. **Bit us:** pre-empted in the M3 watchlist matcher (`services/watchlist_matcher.py`, `NOTIFICATION_INSERT_CHUNK=1000`); pairs with implementation-pitfalls SQLA-2 (the chunked insert is the same statement that carries the partial-index ON CONFLICT). Relates to §4 Bounded growth.

---

## How to Add a Testing-Pitfall

When a bug reaches production (or staging, or late integration testing) because a test was missing:

1. **Identify the topic section** the missing test belongs in. Universal disciplines go in sections 1-7; a discipline discovered in *this* project's history goes in §8 with a `TEST-N` ID and the 🔥 marker. If none of the existing sections fit, add a new numbered topic section.
2. **Write the check item** as a `- [ ]` checkbox. Lead with a bolded imperative ("**X is tested.**"), then one sentence explaining what the check covers and why. Project-specific entries lead with their `TEST-N` ID so it stays greppable.
3. **Mark with the 🔥 marker** if the bug was found in this project's own history: `**🔥 Found in [context]:** one-line note about the observed failure mode`.
4. **Cross-reference implementation-pitfalls.md** if there's a corresponding implementation entry.
5. **Resist the urge to be clever.** "Tests X under condition Y" is better than a novel testing philosophy. These are pass/fail checklist items, not essays.

The test suite is the enforcement mechanism for this document. If you add a check item and don't write the corresponding test, you've documented a gap, not closed one. Close it.
