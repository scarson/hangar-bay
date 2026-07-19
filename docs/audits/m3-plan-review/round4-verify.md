<!-- ABOUTME: Round-4 verification review of the M3 implementation plan — fresh cold read after ~40 findings fixed across rounds 1-3. -->
<!-- ABOUTME: Focus: second-order damage from round-3 fixes + fresh-executor blockers; every load-bearing fix verified against source. -->

# M3 Plan — Round 4 Verification Review (post-fix cold read)

**Plan under review:** `docs/superpowers/plans/2026-07-17-m3-account-features.md` (6,946 lines)
**Design authority:** `docs/superpowers/specs/2026-07-17-m3-account-features-design.md`
**Prior rounds:** `round2-claude.md` (11 findings) + `round2-codex.md` (16 findings); ~40 total fixed across rounds 1-3.
**Stance:** refuted-first. This round's job — confirm the plan is NOW clean and catch second-order damage the round-3 fixes may have introduced. Load-bearing fix claims were re-verified against actual source.

---

## Verdict

**CLEAN.** Zero substantive findings. Every round-3 fix is internally consistent (symbols renamed consistently across producers and consumers; test code agrees with its surrounding prose; the one reordering left no dangling reference; instructions are balanced). No fresh-executor blocker surfaced in the fix regions or in the load-bearing infrastructure they depend on. The pitfalls/design violations flagged in round 2 (FASTAPI-1, PROXY-1, MissingGreenlet-on-serialize, marker hygiene, design §6 a11y binding, design §9.2 audit trail) are all now satisfied.

A fresh executor can run this plan task-by-task as written.

---

## Second-order-damage audit — the 10 round-3 fix regions

Each region was read in full and its consumers cross-checked. All clean.

1. **Matcher `ON CONFLICT` → `index_where=text("type = 'watchlist_match'")` (Task 4.2, codex #1).**
   Consistent in three places that must agree: the model DDL (`Task 1.1`, `postgresql_where=text("type = 'watchlist_match'")`, plan L401), the service `_match_and_notify` (L3237), and the direct `test_dedup_partial_index_binds` test (L2888). All three use the byte-identical literal predicate. `_render_message`/idempotency/chunk tests unaffected. The SQLA-2 pitfall entry (Task 10.1) restates the same rule.

2. **`rename_saved_search` savepoint (Task 2.2, codex #2).**
   `row.name = payload.name` is now INSIDE `async with db.begin_nested():` (L1337), with a comment explaining why (begin_nested flushes on entry). The `test_rename_to_existing_name_409` test (L1188) does a follow-up GET after the 409 and asserts both names survive — which only passes because the savepoint kept the outer transaction alive. Test and code agree.

3. **Task 1.4 two-session race test (codex #6).**
   The RED-first claim holds against actual current source: `auth_service.upsert_user` does `db.add(user); await db.flush()` (verified `auth_service.py:48`) with no commit, so session A's flushed-uncommitted INSERT holds the unique-index lock and session B blocks, then raises `IntegrityError` on A's commit → RED; `ON CONFLICT DO UPDATE` → B lands on A's row → GREEN. The test manages its own two engines against `DATABASE_URL_TESTS` and does its own `drop_all`/`create_all`; this does NOT interfere with sibling tests because `conftest.py`'s `db_session` recreates schema per-function (verified `conftest.py:60-69`), so schema teardown is self-healing. All referenced symbols (`settings`, `select`, `User`, `VerifiedIdentity`, `auth_service`, `pytest`) already import in `test_auth_service.py`; the plan adds the three missing (`asyncio`, `async_sessionmaker`/`create_async_engine`, `Base`).

4. **Five test modules' asyncio markers (MAJOR-2 / codex #7).**
   All five mixed-marker modules now decorate async tests individually with `@pytest.mark.asyncio` and leave sync tests unmarked (no module-level `pytestmark`): `test_account_models.py` (Task 1.1), `test_saved_searches.py` (Task 2.2, L1108-1223), `test_watchlist.py` (Task 3.2), `test_notifications.py` (Task 4.1), `test_scheduled_jobs_watchlist.py` (Task 4.3, L3341/3355 sync + L3366 async-decorated). Pure-async modules (`test_watchlist_matcher.py`, `test_esi_client_resolve_names.py`, `test_current_user.py`, `test_account_fixtures.py`) correctly keep the module-level `pytestmark`. No sync test carries the marker anywhere.

5. **Shared `raiseApiError` helper + `unreadCountQueryOptions` signature change (codex #5).**
   `raiseApiError(queryClient, status): never` (L3597) invalidates `['auth','me']` only on 401 then always throws. Every one of the 14 call sites passes exactly `raiseApiError(queryClient, response.status)` (Tasks 6.1/7.1/8.1). The `: never` return type gives the queries' `return data` its non-undefined narrowing. The signature change to `unreadCountQueryOptions(queryClient, enabled)` (L5637) is matched by its only real consumer `useUnreadCount()` (L5655, supplies `queryClient` + `!!user`) and by the bell, which consumes `useUnreadCount()` — not the factory directly (`NotificationBell.tsx`, L5791). The factory's three unit tests call it with the new two-arg shape (L5493/5503/5515). No self-invalidation loop: `useCurrentUser` treats 401 as `null` data (does not route through `raiseApiError`), so invalidating `['auth','me']` refetches to anonymous and stops.

6. **`interceptNotifications` relocated Task 9.1 → 8.2 (codex #14).**
   Defined once in Task 8.2 Step 5 (L5856) alongside `AccountCall`/`readBody`. Task 9.1 explicitly reuses and does NOT redefine them (L6496, L6536); its new `interceptSavedSearches`/`interceptWatchlist` reference the existing `AccountCall`/`readBody`. `Page` is `import type`'d at the top of `e2e/helpers/api.ts` (verified on disk), and `interceptNotifications` uses only inline types (no `../fixtures/account` import), so Task 8.2 can add it before `account.ts` exists in Task 9.1. Consumers (Task 8.2 auth specs, Task 9.4 notifications spec) call it as `(page, opts)` — matching signature.

7. **`CheckboxField` gains `disabled` prop (Task 8.3, codex #13).**
   The plan's COMPLETE replacement (L6007) is a faithful superset of the actual current `src/components/Checkbox.tsx` (verified: same `label`/`checked`/`onChange` destructure, same `<label>`/`<input>` structure) plus `disabled = false` + `disabled={disabled}`. Backward-safe default means the existing `FilterRail.tsx` consumer is unaffected. `SettingsToggle` passes `disabled={settingsQuery.isPending || update.isPending}` (L6274) and the "no PUT before load" test (L6135) verifies it.

8. **Two-step deletes gain 5s timeout reset (Tasks 6.4/7.3, codex #15).**
   `useEffect(() => { if (!confirmDelete) return; const t = setTimeout(() => setConfirmDelete(false), 5000); return () => clearTimeout(t) }, [confirmDelete])` in both pages (L4469, L5297). Each has a fake-timer test (`vi.useFakeTimers()` after initial load, `userEvent.setup({ advanceTimers })`, `advanceTimersByTime(5000)` inside `act`) asserting the confirm button disarms (L4317, L5112). Button-name regexes are correctly anchored (`/^delete$/i` for the unarmed state vs `/confirm delete/i` for the armed state).

9. **a11y test files added to Tasks 6.4/7.3/8.3 (MAJOR-3).**
   `vitest-axe@0.1.0` is a real dependency (`package.json:51`) and the house pattern `src/features/contracts/components/a11y.test.tsx` exists — the three new files mirror it (`expect.extend(matchers)`, `axe(container)`, `toHaveNoViolations()`). The awaited anonymous headings match the `RequireSignIn feature=` props exactly: `"saved searches"`→`/sign in to use saved searches/i`, `"your watchlist"`→`/sign in to use your watchlist/i`, `"notifications"`→`/sign in to use notifications/i` (component renders `Sign in to use {feature}` as an `<h2>`, matched by role `heading`). Authed states use deterministic gates (`findByText('Cheap frigates')` / `'Rifter'` / `/rifter available/i`).

10. **Commit-step reformatting (MINOR-6).**
    Zero `git commit -m` one-liners remain; all 28 commit-subject blocks are multi-line with the mandated `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` trailer (29 trailers total, ≥ one per commit). Spot-verified Section A commits (Tasks 1.1/1.2/1.3/1.4/2.1/2.2).

---

## Other round-2 fixes spot-verified (no second-order regressions)

- **MAJOR-1 / codex #4 — `update_watchlist_item` refresh.** `await db.refresh(item)` after the update flush (L2202), with a Section-A-referencing comment. The `add` path stays refresh-free (safe via INSERT RETURNING; round-2 verified) — the required fix is on the UPDATE path only, which is present.
- **codex #10 — `resolve_names` error handling.** Catches `httpx.RequestError` (L1663), normalizes non-JSON body (`ValueError`→`ESIRequestFailedError`, L1674) and non-dict shape (L1676). Returns `dict[str, Any]` — `Any` IS imported (`esi_client_class.py:4`). Test module covers all six paths including `test_resolve_names_non_json_body_raises`.
- **codex #11 — anonymous 401 on every route.** Parametrized over POST/GET/PUT/DELETE for watchlist (L2029) and every method for notifications; OpenAPI schema tests assert `"401" in responses` for every operation (L2054).
- **codex #16 — min-price boundary.** Backend `max_price: … ge=0.01` on both create + update schemas (L1751/1772); frontend `min="0.01"`/`step="0.01"` + client-side guard + `/max price must be at least 0\.01/i` test.
- **codex #3 — RequireSignIn href assertion.** Uses exact-href assertion + parses/decodes `next` and asserts `decodedNext` has no `sso=` (L3900), not the impossible `.not.toContain('sso')`.
- **codex #12 — Task 9.4 TEST-8 sync.** The loaded row is the sync gate (`getByText(/rifter available/i)` visible) BEFORE the skeleton `toHaveCount(0)` check, making the check non-vacuous (L6780).
- **codex #8 / MINOR-5 — `summarizeSearch` narrowing.** `(p.sort_by ?? 'date_issued').replace(...)` + `p.sort_direction ?? 'desc'` (L4405); the `summarizeSearch({})` test proves the older-blob path.
- **MINOR-4 — routeTree.gen.ts path.** All three commit steps + the codegen step use `app/frontend/web/src/routeTree.gen.ts` (correct location).
- **MINOR-7 — design §9.2 deferral.** Recorded in the top-of-plan Deviations subsection (L85) with a note to mirror into the Task 10.2 PR body.
- **MINOR-8 — stale matcher note.** Now describes the real `test_matcher_service_is_picklable` (real settings singleton, `now_fn is None`), L3373.
- **NIT-10 — single M3 config block.** Task 2.2 establishes `# --- M3 account features ---`; Tasks 3.2/4.3 explicitly append INTO it ("do NOT start a second M3 block", L1732/L3309).

## Load-bearing source facts re-verified this round

- `settings.SESSION_COOKIE_NAME = "hb_session"` exists (`config.py:47`); `create_session(redis, *, user_id, character_id, character_name, now=None)` matches the Task 1.2 call (`session.py:49`); `get_current_session`/`destroy_session`/`read_session` exist.
- `esi_client_class.py` imports `Any` (needed by `resolve_names -> dict[str, Any]`); `resolve_ids_to_names` at L263 (insertion point ~288 valid).
- `HeaderIdentity.tsx` authed branch matches the Task 8.2 replacement block exactly (bell prepended to `img`/`span`/`Button` cluster).
- Both `auth.spec.ts` authed tests the hermetic-lane fix targets exist ("authenticated header shows portrait…", "logout POSTs exactly once…").
- `NotificationSchema`/`NotificationSettingsSchema` carry `ConfigDict(from_attributes=True)` (needed for `model_validate(user)`/`model_validate(r)`).
- Backend routes ↔ frontend hook literals agree end-to-end: `/me/saved-searches/`, `/me/watchlist-items/`, `/me/notifications/` (trailing slash), `/me/notifications/{id}/mark-read`, `/me/notifications/mark-all-read`, `/me/notification-settings` (no slash, singleton).

## Refuted this round (did not clear the bar for a finding)

- **`add_watchlist_item` lacks `db.refresh`.** Not a blocker: created_at/updated_at load inline via INSERT RETURNING at flush, before serialization; `begin_nested` release does not expire, and the test session is `expire_on_commit=False`. Round-2 examined and refuted this; MAJOR-1 only required the UPDATE-path refresh, which is present.
- **Notifications a11y count regex `/is_read=false&size=1/` fragility.** openapi-fetch serializes in insertion order (`is_read` then `size`), which also equals alphabetical order — the combined regex matches robustly either way.
- **Three identical `## Implemented with deviations (M3, 2026-07-17)` headers (Task 10.2).** Intentional — three distinct note bodies for three separate feature-spec files, each with different content.

---

## Recommended disposition

Ship the plan. No edits required before execution.
