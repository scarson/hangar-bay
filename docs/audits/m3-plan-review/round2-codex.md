<!-- ABOUTME: Cross-provider (codex gpt, read-only sandbox) round-2 adversarial review of the M3 implementation plan. -->
<!-- ABOUTME: 16 findings surviving self-refutation; extracted from the codex exec transcript 2026-07-17. -->

DONE — 16 findings survived refutation.

1. **Blocker — Task 4.2 / Task 10.1 — `index_where=(Notification.type == "watchlist_match")`**

   SQLAlchemy compiles this predicate as `WHERE type = %(type_1)s`, but the partial unique index uses the literal predicate `type = 'watchlist_match'`. PostgreSQL determines partial-index implication while planning and explicitly warns that parameterized predicates do not reliably imply partial-index predicates. Consequently, `ON CONFLICT` can fail to infer the unique index, particularly through prepared statements. [PostgreSQL partial-index documentation](https://www.postgresql.org/docs/current/indexes-partial.html)

   **Fix:** Use a literal predicate identical to the index DDL, such as `index_where=text("type = 'watchlist_match'")`, everywhere the conflict target appears. Update SQLA-2 accordingly and execute the matcher twice against real PostgreSQL to prove deduplication.

2. **Blocker — Task 2.2 — `row.name = payload.name` before `async with db.begin_nested()`**

   `AsyncSession.begin_nested()` unconditionally flushes pending state before establishing the savepoint. The duplicate-name update therefore raises `IntegrityError` outside the intended savepoint, invalidating the surrounding transaction and likely breaking the planned follow-up GET in the same test.

   **Fix:** Move the assignment inside the nested transaction, immediately before `flush()`. After catching `IntegrityError`, expire or refresh the row as necessary. Test that the session remains usable and both original names remain unchanged.

3. **Blocker — Task 6.2 — `expect(link.getAttribute('href')).not.toContain('sso')`**

   Every valid login URL contains `/auth/sso/login`, so this assertion necessarily fails. It confuses the login endpoint with the transient `sso` query parameter being excluded from `next`.

   **Fix:** Keep the exact expected-href assertion, parse the `next` parameter, decode it, and assert that the decoded return URL lacks an `sso` query parameter.

4. **Major — Task 3.2 — `await db.flush(); return item` followed by `WatchlistItemSchema.model_validate(item)`**

   `updated_at` uses an SQL expression on update. SQLAlchemy does not normally fetch UPDATE-generated values under the default eager-default behavior, leaving the attribute expired. Synchronous Pydantic attribute access can then attempt implicit async I/O and raise `MissingGreenlet`.

   **Fix:** `await db.refresh(item)` after the update flush and before schema conversion. Assert the returned `updated_at` value in the HTTP test.

5. **Major — Tasks 6.1, 7.1, and 8.1 — account hooks throw `ApiError` without consistently invalidating `['auth', 'me']`**

   The authoritative design requires any 401 from any `/me/*` hook to invalidate current-user state. Saved-search, watchlist, notification-list, settings, and unread-count queries omit that behavior; notification mutations omit it as well. The header can therefore remain authenticated while account endpoints report 401.

   **Fix:** Introduce one shared 401-handling helper and use it in every account query and mutation. Add 401 tests for each query family and each notification mutation.

6. **Major — Task 1.4 — race test “passes against the current implementation too”**

   The proposed test cannot distinguish atomic `ON CONFLICT` bootstrap from the existing select-then-insert race. It therefore violates the project’s TDD requirement and does not verify the bootstrap-race pitfall.

   **Fix:** Use two independent sessions/connections synchronized immediately before insertion, run simultaneous first-login bootstrap calls, and assert both succeed with exactly one user row. Otherwise, remove this race fix from the plan rather than claiming it is verified.

7. **Major — Tasks 1.1, 2.2, 3.2, 4.1, and 4.3 — module-level `pytestmark = pytest.mark.asyncio` in files containing synchronous tests**

   The OpenAPI and registration tests in those modules are synchronous. Applying the asyncio marker at module scope produces pytest-asyncio warnings or errors, violating the requirement for pristine test output.

   **Fix:** Mark only asynchronous tests, or place synchronous schema/registration tests in unmarked modules.

8. **Major — Task 6.4 — `p.sort_by.replace(...)` and direct use of `p.sort_direction`**

   Those Pydantic fields have defaults and are therefore optional in generated OpenAPI TypeScript types. Under strict TypeScript, `p.sort_by` can be `undefined`, making `.replace()` a compilation error. This also defeats the claimed defensive handling of older stored parameter blobs.

   **Fix:** Default before use, for example `(p.sort_by ?? 'date_issued').replace(...)` and `p.sort_direction ?? 'desc'`. Test summarization with both fields omitted.

9. **Major — Tasks 6.4, 7.3, and 8.3 — `app/frontend/web/src/routes/routeTree.gen.ts`**

   That file does not exist. The generated route tree is `app/frontend/web/src/routeTree.gen.ts`. The prescribed `git add` commands will fail or omit the regenerated file.

   **Fix:** Correct every Files list and commit command to use `app/frontend/web/src/routeTree.gen.ts`.

10. **Major — Task 3.1 — `resolve_names()` catches only `ReadTimeout` and `ConnectError`, then trusts `response.json()`**

    Other `httpx.RequestError` subclasses and malformed or unexpectedly shaped ESI responses escape as raw exceptions, producing 500 responses rather than the specified ESI failure behavior.

    **Fix:** Catch `httpx.RequestError`, normalize JSON decoding and response-shape failures to `ESIRequestFailedError`, validate required entry fields, and add HTTP tests proving these failures produce 502 without persisting a watchlist row.

11. **Major — Tasks 3.2 and 4.1 — anonymous coverage exercises only a subset of new routes**

    Watchlist PUT/DELETE and notification mark-one, mark-all, and settings PUT are omitted. The authoritative acceptance criterion says every new account route must return 401 anonymously.

    **Fix:** Add a parameterized HTTP test covering every method/path and assert the OpenAPI response declarations include 401 for every operation.

12. **Major — Task 9.4 — immediately asserting `getByRole('status').toHaveCount(0)` after navigation**

    The assertion can pass before React mounts the loading skeleton, so it does not prove the skeleton was later unmounted. The subsequent text assertion may synchronize the test overall, but the explicit TEST-8 guard remains vacuous.

    **Fix:** First observe the loading status or await the corresponding intercepted request, then assert the status disappears, then assert the loaded content.

13. **Major — Task 8.3 — `checked={settings?.watchlist_alerts_enabled ?? false}` while the control remains enabled**

    Before settings load, the UI presents an actionable unchecked control. A user can click it and send a value derived from the fallback rather than persisted state.

    **Fix:** Render a loading state or disable the checkbox until settings are available. Add a delayed-settings-response test proving no mutation can occur during loading.

14. **Minor — Task 8.2 — import `interceptNotifications` from later Task 9.1, with “temporary inline route or reorder” as alternatives**

    This leaves a fresh executor with two implementation paths and no later instruction to remove the temporary duplicate. Task 8 cannot execute as written in order.

    **Fix:** Move the shared notification intercept helper before Task 8.2, or move Task 9.1 earlier. Specify one path and remove the temporary workaround.

15. **Minor — Tasks 6.4 and 7.3 — delete confirmation resets only on blur**

    The design requires timeout-based reset. A focused button can remain armed indefinitely, changing the intended protection against accidental deletion.

    **Fix:** Add a timeout reset and a fake-timer test showing the armed state expires.

16. **Minor — Task 7.3 — maximum-price input uses `min="0"` while the backend requires at least `0.01`**

    The frontend advertises zero as valid, but the backend rejects it with 422.

    **Fix:** Use `min="0.01"` with an appropriate step, validate before submission, and test the zero boundary.

Clean checks:

- The 1,000-row chunked insert is within asyncpg’s parameter limit and correctly handles the final partial chunk.
- The correlated `NOT EXISTS` prune compiles with the intended correlation and active-contract conditions.
- Frontend `/api/v1` path literals, backend route paths, collection trailing slashes, and ESI endpoint versions are otherwise consistent.
- Referenced existing session exports, database/auth fixtures, frontend test helpers, and ESI client methods resolve in the current source tree.
