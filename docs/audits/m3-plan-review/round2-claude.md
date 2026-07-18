<!-- ABOUTME: Round-2 independent adversarial review of the M3 implementation plan (2026-07-17-m3-account-features.md). -->
<!-- ABOUTME: Cold-reader audit across ambiguity, context gaps, latitude, cross-task deps, testing pitfalls, implementation pitfalls; all load-bearing code facts verified against source. -->

# M3 Plan — Round 2 Adversarial Review (independent cold reader)

**Plan under review:** `docs/superpowers/plans/2026-07-17-m3-account-features.md` (6,354 lines, read end to end)
**Design authority:** `docs/superpowers/specs/2026-07-17-m3-account-features-design.md` (read in full)
**Codebase:** worktree at `origin/dev` tip `a7b0f26` state; every load-bearing symbol/signature claim in the plan was checked against actual source (files listed in §Verification below).
**Reviewer stance:** findings were refuted-first; only survivors are reported. Refuted candidates are listed at the end so the next round doesn't re-litigate them.

---

## Verdict

**Sound with fixes.** The plan is unusually concrete (complete files, verified line references, explicit do-NOT boundaries, binding naming contract) and the overwhelming majority of its source-level claims check out exactly. Three findings are **major** — one is a verbatim-code bug that will fail the plan's own tests inside Task 3.2, one is a test-output-pristine violation replicated across five new test files, one is a silently dropped binding design requirement. Five are minor, three are nits. Nothing rises to blocker (no finding leaves an executor unable to recover with local information), but the majors will each burn real debugging/rework time or ship a quality gap if not fixed before execution.

---

## Findings

### MAJOR-1 — Task 3.2: `update_watchlist_item` serializes an expired server-onupdate column → MissingGreenlet 500; the task's own PUT tests fail

**Location:** Task 3.2 Step 5, `services/watchlist_service.py` (plan lines ~2028–2047), consumed by Step 6's router `PUT /me/watchlist-items/{item_id}` which does `WatchlistItemSchema.model_validate(item)`; contradicted by the plan's own Section A convention (plan lines ~95).

**Issue:** `WatchlistItem.updated_at` has `onupdate=func.now()` (server-evaluated SQL expression, Task 1.1 model). After `await db.flush()` on the update path, SQLAlchemy expires that attribute. The installed SQLAlchemy 2.0.41's `Mapper.eager_defaults="auto"` fetches server defaults via RETURNING **for INSERT only** — verified in `.venv/.../sqlalchemy/orm/mapper.py:358-383`: for UPDATE, values are "left as expired to be fetched on next access". The route then reads `item.updated_at` during Pydantic `from_attributes` serialization → implicit lazy IO outside a greenlet context → `MissingGreenlet` → the app's generic handler returns 500. `test_put_omitted_field_preserves` and `test_put_explicit_null_clears` (plan lines ~1830–1847) assert 200 and will fail red with a confusing 500, mid-task, after the "confirm green" step promised success.

Section A explicitly documents this exact trap and mandates `await db.refresh(row)` — and the F005 service (Task 2.2) complies on create AND rename. The F006 service omits it on `update_watchlist_item`. (The F006 **add** path is safe: INSERT + `eager_defaults="auto"` + asyncpg RETURNING loads `created_at`/`updated_at` inline — but that safety is an undocumented reliance; a one-line refresh makes both paths uniform.)

**Fix:** in `update_watchlist_item`, after `await db.flush()`, add `await db.refresh(item)` before `return item`. Optionally add the same after the nested flush in `add_watchlist_item` for symmetry with the F005 service (or add a comment stating the INSERT-RETURNING reliance). No other M3 route is exposed: notifications settings PUT serializes only the in-memory bool; mark-read/mark-all-read use Core updates with no ORM serialization; F005 create/rename already refresh.

### MAJOR-2 — Five new test files put sync tests under module-level `pytestmark = pytest.mark.asyncio` → PytestWarning spam, violating the pristine-output gate

**Location:**
- Task 1.1 `test_account_models.py` — sync `test_account_tables_registered`, `test_user_has_watchlist_alerts_enabled_not_null` (plan lines ~206–212)
- Task 2.2 `test_saved_searches.py` — sync `test_saved_searches_schema_bare_and_declares_errors` (~1129)
- Task 3.2 `test_watchlist.py` — sync `test_openapi_watchlist_paths_bare_and_declared` (~1901)
- Task 4.1 `test_notifications.py` — sync `test_openapi_notification_paths_bare` (~2359)
- Task 4.3 `test_scheduled_jobs_watchlist.py` — sync `test_add_watchlist_matcher_job_registers_expected_id`, `test_matcher_service_is_picklable` (~3154, ~3168)

**Issue:** the installed pytest-asyncio is **1.0.0** (`pdm.lock`), and its plugin emits a `PytestWarning` for every non-async test carrying the asyncio marker (verified at `.venv/.../pytest_asyncio/plugin.py:740-748`: "The test … is marked with '@pytest.mark.asyncio' but it is not an async function. Please remove the asyncio mark. If the test is not marked explicitly, check for global marks applied via 'pytestmark'."). Module-level `pytestmark` marks the sync tests too → 7 warnings across 5 files in every run. Testing-pitfalls §1 ("Test output MUST be clean — no stray errors, warnings") and the plan's own "output pristine" claims (e.g. Task 3.1 Step 4, Task 4.2 Step 6) are violated. No existing test file in the repo mixes sync tests under a module-level asyncio pytestmark (verified: every `pytestmark`'d file — test_esi_client, test_observability, test_main_endpoints, test_contract_filters, test_contract_service, test_background_aggregation — has zero sync `def test_`; sync schema tests like `test_me_schema.py` live in unmarked modules). The predictable executor failure mode is "fix" via a warnings filter — which the pitfalls doc forbids.

**Fix (pick one, apply consistently):** (a) drop the module-level `pytestmark` in the mixed files and decorate each async test with `@pytest.mark.asyncio`; or (b) keep module `pytestmark` and move the sync `app.openapi()`/metadata tests into a separate unmarked module per feature (mirroring `test_me_schema.py`). Either preserves the strict-mode discipline stated in Section A.

### MAJOR-3 — The design's binding §6 mandates vitest-axe a11y tests for the three new pages; the plan builds none and records no deviation

**Location:** design §6 "Frontend (vitest): … a11y via `vitest-axe` for the three new pages" — vs plan Tasks 6.4, 7.3, 8.3 (page test files contain no axe assertions; no task references `vitest-axe`; no deviation recorded in any task or the PR-body deviations list, Task 10.3).

**Issue:** the plan's own header declares design "§6 test strategy" **binding**. The house pattern exists (`src/features/contracts/components/a11y.test.tsx` uses `vitest-axe` + matchers), so the omission is not a tooling gap. The new pages carry exactly the structures axe catches regressions in (forms with programmatic labels, live regions, link-vs-button rows, sr-only text). A fresh executor following the plan verbatim will ship M3 with a silent test-strategy hole, and Task 10.3's PR body will claim §6 compliance it doesn't have.

**Fix:** add an axe pass per new page (either a small `a11y.test.tsx` per feature folder mirroring the contracts one, or one axe `it` inside each page test file: render authed + loaded state, `expect(await axe(container)).toHaveNoViolations()`), or explicitly record the deviation in §8-style notes + the PR body for Sam's sign-off.

---

### MINOR-4 — Wrong `routeTree.gen.ts` path in three commit steps

**Location:** Task 6.4 Step 6, Task 7.3 Step 6, Task 8.3 Step 11 — `git add app/frontend/web/src/routes/routeTree.gen.ts`.

**Issue:** the generated file lives at `app/frontend/web/src/routeTree.gen.ts` (verified on disk; the Vite plugin uses the default `generatedRouteTree` location, and Phase 10 Step 6 uses the correct path). The `git add` in three commit steps will fail with "pathspec … did not match any files", stalling each commit until the executor diagnoses the mismatch — and inviting a wrong "fix" (moving the file or reconfiguring the plugin).

**Fix:** change the three occurrences to `app/frontend/web/src/routeTree.gen.ts`.

### MINOR-5 — Task 6.4 `summarizeSearch` dereferences optional generated fields → `npx tsc -b` fails on the verbatim COMPLETE file

**Location:** Task 6.4 Step 4, `SavedSearchesPage.tsx`: `parts.push(\`sorted by ${p.sort_by.replace(/_/g, ' ')} ${p.sort_direction}\`)` (plan line ~4138).

**Issue:** in the generated client types, `SavedSearchParameters` properties with server-side defaults (`ships_only`, `size`, `sort_by`, `sort_direction`) are **not** in the OpenAPI `required` array (Pydantic fields with defaults never are), so openapi-typescript emits them as optional. `p.sort_by.replace(…)` is a possibly-undefined access → TS18048 under the project's strict config; the task's own Step 5 gate (`npx tsc -b` green) fails on the file as written. Runtime is actually safe (the backend always materializes defaults into the stored blob), but the type doesn't know that.

**Fix:** narrow or default in `summarizeSearch`, e.g. `const sortBy = p.sort_by ?? 'date_issued'; const dir = p.sort_direction ?? 'desc'` (and treat `p.ships_only ?? true` for the label if strictness complains). Do not "fix" by hand-editing `schema.d.ts`.

### MINOR-6 — Section A commit commands omit the mandated `Co-Authored-By` trailer

**Location:** Task 1.1 Step 7, 1.2 Step 5, 1.3 Step 5, 1.4 Step 5, 2.1 Step 5, 2.2 Step 9 — all use one-line `git commit -m "<subject>"`.

**Issue:** CLAUDE.md mandates every commit message end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`. Sections B and C show the trailer in their commit blocks; Section A does not. An executor following Section A verbatim produces six non-conforming commits on a no-squash branch where each commit message is permanent.

**Fix:** normalize the six Section A commit steps to the Section B format (multi-line message with the trailer).

### MINOR-7 — Design §9.2 ride-along (`test_auth_flow` sessions get real user rows) silently dropped

**Location:** design §9 item 2 vs the plan: no task touches `tests/api/test_auth_flow.py`, and no deviation is recorded.

**Issue:** the design scoped it conservatively ("only where it reduces duplication; no wholesale rewrite"), so dropping it may be the right call — but the plan neither does it nor records the drop, so the design and plan disagree with no audit trail. A future reader of the design will expect the migration happened.

**Fix:** either add a small step to Task 1.2 (convert the `test_auth_flow` sessions where `login_as` is a strict simplification) or add one line to the plan (and the PR-body deviations) recording the deferral.

### MINOR-8 — Task 4.3's parenthetical note references a nonexistent test and contradicts the actual one

**Location:** Task 4.3, note after Step 2 (plan lines ~3185–3187): "Note: `test_matcher_service_with_default_now_fn_is_picklable` pickles only `now_fn` — the full service carries a `MagicMock` settings here which is not picklable…".

**Issue:** no test by that name exists in the file; the actual `test_matcher_service_is_picklable` pickles the **full service** using the **real settings singleton** (which is picklable), exactly the opposite of what the note describes. A cold executor reconciling note-vs-code will burn time deciding which is authoritative, or "fix" the good test to match the stale note.

**Fix:** delete the note, or rewrite it to describe the real test ("uses the real settings singleton because a MagicMock settings would not pickle; the point is that the default `now_fn` is `None`, not a lambda").

---

### NIT-9 — After Task 8.2, sibling authed page tests answer the bell's unread-count query with `[]`, producing silent errored queries

The bell (in `HeaderIdentity`, rendered by every `renderApp` test) fires `GET /me/notifications/?is_read=false&size=1` whenever `/me` is authed. The SavedSearchesPage and WatchlistPage test stubs (Tasks 6.4/7.3) fall through to `jsonResponse([])` for that URL; the count queryFn returns `[].total === undefined`, which TanStack v5 converts to an errored query ("query data cannot be undefined"). Currently invisible (badge hidden, no console output, `retry: false`) — tests pass — but it's a latent noise source if TanStack ever logs it or if an assertion later touches the bell. Cheap hardening: make those stubs' fallback (or an explicit `/me/notifications/` branch) return `{ total: 0, page: 1, size: 1, items: [] }`, as SaveSearchControl's `EMPTY_PAGE` fallback and `HeaderIdentity.test.tsx` already do.

### NIT-10 — Two different M3 config comment blocks

Task 2.2 Step 3 adds `MAX_SAVED_SEARCHES_PER_USER` under `# M3 account features — per-user soft caps …`; Tasks 3.2/4.3 build a separate `# Account features (M3)` block. Followed verbatim, `core/config.py` ends with two adjacent M3 blocks. Cosmetic; consolidate into one block name.

### NIT-11 — Task 10.1 file line uses an odd relative path

"Modify: `app/backend/../docs/pitfalls/implementation-pitfalls.md`" — self-corrected by the parenthetical repo path, but the `app/backend/..` form is noise; use `docs/pitfalls/implementation-pitfalls.md`.

---

## Dimension-by-dimension summary

**1. Ambiguity — no substantive findings.** The plan provides COMPLETE files for essentially every artifact, exact commands, expected failure messages for every red step, and expected pass conditions. The few "adapt to reality" clauses (Task 10.2 doc shapes; Task 6.4/7.3 route-tree regen; Task 8.2's Phase-9 fallback) are explicitly bounded with the sanctioned adaptation named. No "handle correctly"/"as needed" latitude found.

**2. Context gaps — all load-bearing claims verified against source; three code-level errors found (MAJOR-1, MINOR-4, MINOR-5, reported above).** Verified true, among others:
- `tests/conftest.py`: `db_session` begin-once at lines 46-82; `auth_client` sets `app.state.redis`/`http_client` (base `http://sso.test`, line 183), overrides `get_db`, exposes `client.fake_redis`, depends structurally on `httpx_mock`; `configured_sso` is last fixture; `pytest_asyncio` imported. `tests/` and `tests/api|core|models` are packages (`__init__.py`), so `from fastapi_app.tests.conftest import login_as` resolves; `tests/services/` has no `__init__.py` but nothing imports it as a package.
- `core/session.py` exports `create_session(redis, *, user_id, character_id, character_name)`, `read_session`, `destroy_session`, `get_current_session`; key shape `session:{sid}`; payload carries `user_id`/`character_id` — Task 1.3's direct-call tests are well-formed (SimpleNamespace `.cookies.get` works).
- `core/exceptions.py`: `ESIRequestFailedError(status_code: int = 0, message: str = "")` — network errors carry `status_code=0`, so `_map_esi_failure`'s `400 <= status < 500` check correctly yields 502 for them.
- `core/esi_client_class.py`: `__init__(settings, http_client=None, redis_client=None)` (Task 3.1's redis-less construction is valid); `_get_esi_object` at 192-253 breaks on <500 and falls through to `raise_for_status()` — the plan's Verified-source note #1 (4xx ⇒ `httpx.HTTPStatusError`, 5xx/network ⇒ `ESIRequestFailedError`) is exactly right, and catching both in the service is necessary; `resolve_ids_to_names` ends at line 287 (insertion point correct); `get_universe_type`/`get_universe_group` paths version-pinned as claimed. The plan's network-catch tuple `(httpx.ReadTimeout, httpx.ConnectError)` matches the existing house convention.
- `core/config.py`: `settings` singleton + `get_settings()` returns the same object — the monkeypatch-based cap tests work for both the `get_settings()`-style (F005) and module-`settings`-style (F006) services.
- `core/dependencies.py`: `get_cache`, `get_esi_client` (lines 39-50) inject `app.state.http_client` + `app.state.redis` — the pytest-httpx seam claim holds.
- Models: `models/__init__.py` current body matches the plan's replacement base; `User` import line and column order match Task 1.1's edit instructions; `Contract`/`ContractItem` non-nullable columns are all covered by the matcher tests' `_contract`/`_item` helpers.
- Schemas: `ErrorDetail` (`schemas/auth.py`), `PaginatedResponse[T]` (`schemas/common.py`), `SortableContractFields`/`SortDirection` members match the frontend `SORT_FIELDS`/`SORT_DIRECTIONS` exactly (all six fields — a saved `sort_by: 'ship_name'` round-trips).
- `main.py`: router imports at 25-26, mounts at 192-194, `add_aggregation_job` at line 56 — all line refs accurate. `from .models import contracts` at line 27 runs the package `__init__`, so registration-by-`__init__` works for `create_all`.
- `core/scheduler.py` / `services/scheduled_jobs.py`: shapes match the mirrors the plan builds (`from datetime import datetime` present to extend; `add_job` kwarg shape identical).
- `test_background_aggregation.py`: `_FakeLockRedis` at exactly 275-295 (byte-identical to the promoted `lock_double.py`), the two lock tests at 298-321, `bg_agg.aioredis` patch pattern mirrored correctly.
- `auth_service.py`: `upsert_user` body+TODO at ~16-49; `mark_for_reauth` note at 52-54; `refresh_user_tokens` TODO at 88-94; imports match Task 1.4's replacement plan; `test_auth_service.py` already imports `VerifiedIdentity`, `auth_service`, `select`, `User`, `pytest` — the appended test compiles.
- `/me` returns exactly `{"character_id", "character_name"}` (`CurrentUserSchema`) — Task 1.2's exact-equality assertion is valid.
- `core/logging.py`: `get_logger`, `log_key_event(logger, event, success, duration_ms, error_message=None, **kwargs)` — matcher usage valid.
- `tests/fake_redis.py`: `FakeRedis` supports `get/set(ex,nx)/exists/delete` — all Task 1.3 assertions supported.
- `export_openapi.py` `_ENV_DEFAULTS` at lines 16-23; all five M3 config fields have defaults — no change needed, as claimed.
- Frontend: `client.ts` `CurrentUser` alias at line 7; `ApiError(status)`; `PaginatedResponse_ContractSchema_` naming precedent confirms `PaginatedResponse_NotificationSchema_`; `renderApp` returns `{ router }` with `retry: false`; `anonymousMe(handler)` signature composes with the plan's local stubs; `useCurrentUser` resolves `null` (anonymous-as-data); `useLogout` is the mutation template claimed; `buttonClasses`/`Button`/`Input`/`CheckboxField(label, checked, onChange(checked))` all exist with the used signatures; `filters.ts` exports `MIN_SEARCH_LENGTH`/`ContractSearch`/`parseContractSearch`, and `ContractSearch` minus `page` maps 1:1 onto `SavedSearchParameters` (no stray keys can 422 the `extra="forbid"` model — nulls in stored blobs are also handled by `parseContractSearch`'s junk tolerance); `formatIsk` exists; `ContractsPage` receives `search` as a prop and its results-header div is at lines 107-116; `ContractDetailPage` item `<li>` at 179-194 with `category === 'ship'` gating available; `HeaderIdentity` authed branch at 32-46; `HeaderIdentity.test.tsx` fallbacks return `{total: 0, …}` (the claim in Task 8.2 is true); `contracts.index.tsx`'s `SearchSchemaInput` marker makes `navigate({ to: '/contracts' })` type-check as the plan assumes; `contracts.$contractId` param name matches `params: { contractId }`.
- E2E: `interceptCurrentUser(page, {status:401}|user)`, `interceptContractList`, `interceptLogout`, `failUnexpectedApiCalls`, `stubPortraits` glob `**://images.evetech.net/**` (already covers `/types/{id}/render` — the plan's JSDoc-only change is correct); `makeCurrentUser`, `SEVEN_SHIPS`, `pageOf` exist; Playwright projects `desktop`/`mobile`/`live-smoke`, `retries: 0`; the two authed `auth.spec.ts` tests named in Task 8.2 exist; vitest `exclude: e2e/**` present.

**3. Interpretation latitude — no substantive findings.** Do-NOT boundaries are explicit where they matter (never hand-edit generated files; never add `/api/v1`; never weaken assertions; never revert a sibling's `main.py` line; the sanctioned adaptation for path-literal mismatches is "copy the generated key verbatim"). The assertion-rigor block is repeated on every timing-sensitive task.

**4. Cross-task dependencies — no unresolved conflicts.** `main.py` (4 writers), `schemas/account.py` (3 writers), `core/config.py` (3 writers), `conftest.py` (1 writer, many readers) are all explicitly sequenced with shared-file notes and a consolidator section; config-field ownership has a fallback clause; Task 8.2's dependency on Phase 9's `interceptNotifications` is handled with a concrete inline fallback. Path-param literals are consistent end-to-end (`{search_id}`/`{item_id}`/`{notification_id}` in backend routes, schema tests, and frontend hooks). Query keys consistent: `['savedSearches','list']` invalidated by prefix `['savedSearches']`; `['watchlists','list']` by `['watchlists']`; `['notifications','list',params]`/`['notifications','unreadCount']` by `['notifications']`; settings by `['notifications','settings']`; auth-coherence via `['auth','me']` — hooks and tests agree.

**5. Testing pitfalls — MAJOR-2 and MAJOR-3 above; otherwise compliant.** TEST-1 (HTTP-level + `app.openapi()` everywhere), TEST-3 (deterministic tiebreakers: distinct names; same-name/distinct-type_id; strictly-decreasing `created_at` + id), TEST-4 (5-row/size-2 boundary crossing with union/no-dup assertions), TEST-5 (fetch-seam URL/method/body assertions on every hook), TEST-6 (suffix discipline stated in the standing notes), TEST-7 (persistent-failure stubs under `retry:false` renderApp; hook error tests), TEST-8 (skeleton-unmount sync in RTL and Playwright), TEST-9 (`interceptCurrentUser` first in every spec; the Task 8.2 hermetic-lane fix for the new bell request is exactly the TEST-9 discipline applied proactively), TEST-10 (reuses the wired `auth_client`). §5 concurrency: dedup tested against the real constraint, idempotency asserted as N>0-then-zero, caps honestly declared sequential-only. The ESI-5xx retry test correctly warns against asserting request-count==1.

**6. Implementation pitfalls — compliant.** FASTAPI-1 (`Annotated[NotificationFilters, Query()]` — the only GET filter model); FASTAPI-2 (ME/TE rejected by `extra="forbid"`, tested); PROXY-1 (bare mounts, trailing-slash conventions stated and sentinel-tested, frontend literals verbatim); SQLA-1 (notifications pagination is single-table — no joined-row pagination anywhere; the matcher's joined SELECT is unpaginated and `.distinct()`); ENV-1/2/3 (no `pdm run dev` during implementation; batch discipline stated); ENV-4 (every new config field paired with a `.env.example` line); ESI-1 (all new ESI calls version-pinned; `resolve_names` pins `/v1/universe/ids/` and the test asserts the path). The new SQLA-2/TEST-11 pitfall entries follow the maintenance framework including TOC/Appendix-B/checklist updates. No secrets/PII in logs; the matcher's log line carries counts only.

---

## Refuted candidates (checked and dismissed — don't re-raise without new evidence)

1. **"`ESIClient` requires a redis client"** — `redis_client` is optional; `resolve_names` touches only `http_client`. Task 3.1's construction is valid.
2. **"Network-error catch tuple too narrow in `resolve_names`"** — `(httpx.ReadTimeout, httpx.ConnectError)` matches the existing `_get_esi_object`/`get_esi_data_with_etag_caching` house convention; widening it is out of the plan's scope.
3. **"`settings` monkeypatch won't affect `get_settings()`-style services"** — `get_settings()` returns the module singleton; both styles see the patch.
4. **"Frontend `sort_by: 'ship_name'` could 422 the saved-search POST"** — backend `SortableContractFields` has all six frontend fields.
5. **"`ContractSearch` spread could leak extra keys into the `extra='forbid'` model"** — `ContractSearch` minus `page`/gated `search` is exactly the `SavedSearchParameters` field set; `undefined` values are dropped by JSON serialization.
6. **"`login_as` import creates a second conftest module instance"** — `tests/` is a package with `__init__.py` and `pythonpath=["src"]`; pytest imports it as `fastapi_app.tests.conftest`, one module object. Task 1.2's round-trip test would catch any deviation immediately anyway.
7. **"204 routes returning `None` produce a body"** — FastAPI 0.139 handles `status_code=204` with `None` returns; the codebase already mixes both styles.
8. **"`/mark-all-read` vs `/{id}/mark-read` route collision"** — different segment counts; the plan's own NOTE is correct.
9. **"pytest-httpx `assert_all_responses_were_requested` breaks the reusable-response tests"** — reusable responses are matched at least once in every test that registers them; the cap test registers none and fires none.
10. **"Bell count query breaks existing `HeaderIdentity`/`pages` tests"** — `HeaderIdentity.test.tsx` fallbacks return a `{total: 0}` shape (verified); `pages.test.tsx` is anonymous (`anonymousMe`), so the count query never fires (`enabled: !!user`). Only the *new* Phase 6/7 stubs have the `[]`-fallback wart (NIT-9).
11. **"`interceptNotifications` regex collides with `/me/notification-settings`"** — `notifications` ≠ `notification-settings` as literals; the plan's registration-order note is accurate.
12. **"`test_me_schema.py`-style sync tests need markers"** — they live in unmarked modules today; that's precisely the pattern MAJOR-2 asks the new files to follow.
13. **"`routes.test.tsx` asserts an exhaustive route list and breaks on new routes"** — it tests only `/` redirect and the detail route; safe.
14. **"Design says `useCurrentUser` is 'already in scope' in ContractsPage (it isn't)"** — true of the design text, but the plan's `SaveSearchControl` calls `useCurrentUser()` internally, so no executor-facing gap.
15. **"`_item` helper's computed `record_id`s collide"** — all computed/explicit record_ids in the matcher tests are distinct.
16. **"Notification model rejects explicit `created_at`"** — `server_default` columns accept explicit values; the seeding helpers are valid.
17. **"`monkeypatch.setattr(wm, 'NOTIFICATION_INSERT_CHUNK', 2)` won't be seen"** — the service reads the module global at call time; the patch works (same pattern as `bg_agg` tests).

---

## Recommended disposition

Apply MAJOR-1 (one-line refresh), MAJOR-2 (marker hygiene in five files), MAJOR-3 (three axe tests or a recorded deviation), and the five minors (three path strings, a type-narrowing line, six commit trailers, one recorded deferral, one stale note) as plan edits before execution. None of these alter the architecture, the task graph, or the naming contract; total edit surface is small and localized.
