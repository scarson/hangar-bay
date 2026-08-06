<!-- ABOUTME: Session-close handoff for the second 2026-08-02 session — the 6-second contract list -->
<!-- ABOUTME: root cause, the design two reviews rejected, and two credential items needing Sam. -->

# Handoff — contract-list latency, DEPLOY-5, worktree reclamation (2026-08-02, session 2)

**Read this first.** It continues [`2026-08-02-f008-esi4-release-please-handoff.md`](2026-08-02-f008-esi4-release-please-handoff.md), whose priority queue items 1, 2, 6 and 7 are now closed. Item 4 — the F008 implementation plan — is **untouched and is the main remaining work**.

## 0. Two things only Sam can do

Both are credential/console actions. Neither is optional and neither can be done by an agent.

1. **Rotate `RENDER_API_KEY`** — its value was printed into a session transcript by a bad shell existence-probe (`${VAR:+set}${VAR:-…}` expands to the *value* when the var is set). It may already be done: every Render API call began returning HTTP 400 partway through the session, which is consistent with rotation. If it was rotated, update the 1Password item that materializes the repo-root `.env`. **Sam asked that this instruction be repeated in every handoff until he states it is rotated.**
2. **Remove the temporary IP allow rule on the production database.** `hangar-bay-db` (`dpg-d9fj14btqb8s73d71r10-a`) → Connections → allowed source IPs → delete `198.37.143.189/32`, described `temp troubleshooting 2026-08-02 - REMOVE`. It was added with Sam's explicit authorization to run `EXPLAIN ANALYZE` against production; **the API key stopped authenticating before it could be reverted.** The allow list was empty before, so the correct end state is empty.

## 1. Headline state

| | |
|---|---|
| `dev` | `b5d4d0f` |
| `main` (production) | `0edea19` — the `0.2.0` release, live and healthy |
| Open PRs | **#130** (perf fix, `Review`), **#131** (DEPLOY-5 pitfall, `Routine`) |
| Worktrees | 3, down from 11 |
| Production health | `/ready` 200, db ok, cache ok, ingest fresh |
| Production CD | **red** — see §4, and note *why* merging #130 does not by itself turn it green |

## 2. What the previous handoff asked for, and what happened

- **Item 1, merge PR #128 (`0.2.0`)** — already done before this session started. `main` is `0edea19`.
- **Item 2, confirm the production deploy** — done, and it surfaced everything below. The deploy itself succeeded; the **post-deploy live smoke failed**.
- **Item 6, reclaim the worktrees** — done. 11 → 3, and the nine merged branches deleted locally.
- **Item 7, the alembic pitfall** — done, PR #131 (`DEPLOY-5`).
- **Item 3, read the user's reply** — no reply visible; nothing to do.
- **Item 4, the F008 implementation plan** — **not started.** See §6.
- **Item 5, the `min_me` decision** — not taken; still Sam's call.

## 3. The finding: the contract list takes 6 seconds in production

Full investigation, with every measurement, is in
[`docs/perf-audits/2026-08-02-contract-list-watermark-subquery.md`](../../perf-audits/2026-08-02-contract-list-watermark-subquery.md).
Do not re-derive it — it cost most of this session and required production database access
that is no longer available.

The short version: the unfiltered list's exact-`total` count measures **6,022 ms**, of which
~4.6 s is one correlated subquery in `still_listed_by_esi()` executed **61,874 times** to
recompute a value that is the same for every row of a region — and production ingests exactly
one region. The default ships-only view is fine (8.4 ms) because only ~424 rows reach the
predicate.

**PR #130** fixes it by emitting the watermark for *configured* regions as uncorrelated
subqueries (hoisted to an InitPlan, one index probe each) and keeping today's correlated
predicate as the `ELSE` arm of a `case`. Measured on production: **6,022 ms → 1,565 ms**, page
query unchanged at 0.155 ms, semantics verified identical by a both-way `EXCEPT` in a single
snapshot — including under a deliberately wrong configuration, which is what makes
`AGGREGATION_REGION_IDS` safe to use as a hint.

**The design in that document is the second one.** The first — a `contract_region_watermarks`
table written by ingestion — was rejected by two independent adversarial reviews (an Opus
subagent and codex). §8 of the doc records why. The two that would have taken the site down:
a 304 whose cached body was LRU-evicted from Valkey returns `[]` *without raising* and counts
as a successful region fetch, so a watermark would have advanced with nothing restamped; and
"missing watermark ⇒ visible" is unachievable with an unchanged predicate shape, because
`last_seen_at >= NULL` is rejected by `WHERE`. Measuring the proposal also put it at 1,270 ms
— no better than the far simpler change that shipped.

## 4. Seams — where this work meets something else

*   **Merging #130 to `dev` does NOT fix production.** `.github/workflows/deploy.yml` triggers
    on `workflow_run` of CI **restricted to `main`**. Production only changes through a
    `dev` → `main` publication PR. So the live-smoke failure persists until the next release,
    and the next release will also fire Release Please for `0.3.0`. Anyone checking "is the
    smoke green now?" right after merging #130 will see red and misread it.
*   **The smoke test is a real gate that is currently failing, and it should not be silenced.**
    It failed because a 5 s assertion budget met a 6.5 s backend. The prior runs passed at 7.2 s
    and 8.4 s of total test time — it has been near the edge for weeks. Raising the timeout
    hides the next crossing rather than the current one.
*   **Production DB access is gone.** The `EXPLAIN ANALYZE` numbers in the perf-audit doc cannot
    currently be reproduced: the API key returns 400 and the allow-list rule needs Sam anyway.
    A local scale model is described in §6 of that doc, with the trap that makes it produce
    plausible-but-meaningless numbers.
*   **#130 and #131 do not conflict** — different files (`docs/perf-audits/` + backend vs
    `docs/pitfalls/`). Either order is fine.
*   **DEPLOY-5 was allocated against `origin/dev`**, per the known ID-collision trap. If another
    agent adds a `DEPLOY-*` entry concurrently, re-check the number before merging.
*   **This worktree is on `fix/contract-list-watermark-cost`, not the branch its directory name
    suggests** (`secret-scanning-validity-2eb72d`). Harmless, but do not infer the branch from
    the path.
*   **`hangar_bay_postgres` and `hangar_bay_valkey` are bind-mounted to the
    `hangar-bay-frontend-rebuild-2e4fe7` worktree** (ENV-10). That worktree was deliberately
    **not** reclaimed; removing it kills the local Postgres and Valkey everything else uses.

## 5. Operational guardrails from this session

*   **Never probe a secret with `${VAR:+x}${VAR:-y}`.** The `:-` branch expands to the *value*
    when the variable is set, so the two concatenate and print the secret. Use
    `[ -n "$VAR" ] && echo set`. This is how the Render key leaked.
*   **Revert a temporary production access grant in the same session you create it.** An API key
    can stop working mid-session and strand the cleanup — which is exactly what happened.
*   **`ships_only` is a frontend-only URL param; the API param is `is_ship_contract`.** Probing
    the API with `?ships_only=true` silently measures the *unfiltered* query. This produced
    about twenty minutes of wrong measurements and a wrong conclusion before it was caught.
    `filters.ts:102` does the mapping.
*   **Seeding a perf corpus with two `INSERT` statements gives the two batches different
    `now()` values**, because `now()` is transaction time and psql autocommits per statement.
    Every live row then fails a watermark predicate, all the plans short-circuit to zero rows,
    and the timings look plausible while measuring nothing. Normalize to a literal after seeding.
*   **codex refuses to review with a dirty or untracked working tree** — it reads the repo's own
    "STOP and ask about uncommitted work" rule and stops. Commit the artifact under review first.
*   **codex rejects `-m gpt-5.1-codex-max` on a ChatGPT account** (`400 invalid_request_error`).
    Omit `-m` and use `-c model_reasoning_effort=high`.
*   **The Render CLI needs a workspace before any command works** — `render workspace set
    tea-d9dvc8t7vvec73eq2ktg --confirm` — and `render psql` needs a local `psql` binary, which
    this machine does not have. Working alternative: fetch `connection-info` from the API and
    run `psql` inside a throwaway `postgres:18-alpine` container, passing credentials as `PG*`
    environment variables so nothing sensitive lands in argv.
*   **Adversarial review earned its keep decisively here.** Both reviewers independently killed
    a design that had already been written up as settled, and the design that shipped came out
    of *their* suggestions rather than the original analysis. They also caught a flatly false
    claim in the doc (`_fetch_regions` "already tracks which regions succeeded" — it returns
    counters). The recurring lesson, already in memory: open the function before writing "X
    already does Y" into a durable artifact.
*   **Mutation-verify by file copy, never `git checkout --`** — used here to prove the new
    fast-path tests actually detect a broken predicate. Breaking the comparison failed three
    tests; restoring returned 572 green.

## 6. Priority queue

1. **Merge #131** (`Routine`, docs-only) once CI is green — the agent may self-merge. Always
   `gh pr merge 131 --merge --delete-branch --body ""`; the empty body is required or the PR
   title lands in the merge commit and release-please emits a duplicate changelog entry.
2. **Review and merge #130.** Classified `Review` because it changes the predicate deciding
   which contracts every reader sees, shared with the watchlist matcher. The correctness
   argument is the both-way `EXCEPT` in §5 of the perf-audit doc.
3. **Do the two credential actions in §0.**
4. **Publish `dev` → `main`** to actually fix production, then confirm the live smoke goes
   green and Release Please opens `0.3.0`.
5. **Write the F008 implementation plan** — the big one, untouched. Use
   `superpowers-plus:writing-plans-enhanced` then `plan-review-cycle`. Start from
   `design/features/F008-Type-Aware-Contract-Browsing.md` §17 (the normative API contract) and
   §7.1 (single-writer decomposition constraints). Two inputs from this session belong in it:
   the exact-count strategy at corpus scale (F008 makes the 6-second path the *primary* one),
   and DEPLOY-5, which is now a pitfall rather than only a line in §7.1.
6. **Decide the `min_me` question** — fold into F008's single item-level migration, or make the
   four inert params hard-error now. Still Sam's call; unchanged from the previous handoff.
7. **Two measured, uncontroversial follow-ups** from the perf work, both recorded in §9 of the
   perf-audit doc: drop the `DISTINCT` wrapper on the no-join count path (both reviews asked
   for it), and look at `_count_unknown_system_excluded`, which applies the same predicate a
   third time over an unindexed column ahead of the `total == 0` short-circuit.
8. **Optional: reconsider the database plan.** `basic_256mb` takes 0.075 ms for a fully-cached
   three-level index probe, which is CPU starvation rather than a query defect — everything
   measured here is ~100× slower than the same shapes on a laptop. A cost decision, not a
   code one.

## 7. Local machine state a fresh agent should know

- `render` CLI installed via Homebrew this session; workspace set to `Primary`.
- Two scratch databases created in the local `hangar_bay_postgres` container and **not**
  cleaned up: `hangar_bay_perf` (51k-row perf model) and `hangar_bay_test_watermark` (this
  worktree's pytest DB, pointed at by `app/backend/src/.env`). Drop them when done.
- `app/backend/src/.env` exists in this worktree — gitignored, contains only local-dev values
  and a throwaway cipher key. A fresh worktree needs one or pytest cannot even collect.
- Backend deps installed here via `pdm install`.

## 8. Continuation prompt (paste-ready)

> Pick up the Hangar Bay work. Read `docs/superpowers/handoffs/2026-08-02-contract-list-latency-handoff.md` first, then `docs/perf-audits/2026-08-02-contract-list-watermark-subquery.md` for the contract-list latency finding — do not re-derive it, the production database access it required is gone.
>
> State: `dev` is `b5d4d0f`, production is `0edea19` and healthy, two PRs are open — #130 (perf fix, classified `Review`, needs Sam) and #131 (DEPLOY-5 pitfall, `Routine`, agent may self-merge on green). Production CD is red on the post-deploy live smoke; merging #130 to `dev` does NOT fix it, because Deploy only triggers from `main` — production changes only through a `dev` → `main` publication PR.
>
> Two items need Sam and only Sam: rotating `RENDER_API_KEY` (its value was leaked into a transcript) and removing the temporary IP allow rule `198.37.143.189/32` from the production database. Repeat both in any handoff you write until Sam says they are done.
>
> The main remaining work is the F008 implementation plan (`superpowers-plus:writing-plans-enhanced`, then `plan-review-cycle`), starting from `design/features/F008-Type-Aware-Contract-Browsing.md` §17 and §7.1. F008 makes the 6-second unfiltered list the primary surface, so decide the exact-count strategy at corpus scale inside that plan.
>
> Do not put the name of the player whose feedback is recorded in `design/user-feedback/` into the repository; he has not consented and the record identifies him by role deliberately.

## Appendix — adversarial review of this handoff

**Round 1 — naive fresh agent (3 findings applied).** Added the explicit statement that merging #130 does not fix production, which reads as an obvious next step and is wrong. Named what `still_listed_by_esi()` *is* before referring to it. Spelled out that "the design in the doc is the second one," since a reader who skims §5 of the perf-audit doc would otherwise implement the rejected one.

**Round 2 — recency bias (2 findings applied).** The morning's worktree reclamation and the DEPLOY-5 entry were under-represented against the evening's perf investigation; both are now in §2 against the previous handoff's queue. Restored the `ships_only`/`is_ship_contract` measurement error, which happened early and was nearly lost.

**Round 3 — seams (4 findings applied).** Added the deploy-triggers-only-from-`main` seam, the DEPLOY-5 ID-allocation caveat, the worktree-directory-name-vs-branch mismatch, and the ENV-10 reason the frontend-rebuild worktree was deliberately kept.

**Round 4 — operational guardrails (5 findings applied).** §5 existed only as scattered prose. Added the shell secret-probe rule with its exact failure, the revert-in-session rule, the codex dirty-tree and model-flag behaviours, and the containerized-psql workaround for a machine with no local `psql`.

**Round 5 — loss-averse (3 findings applied).** Recovered the local-machine state in §7 (two undropped scratch databases, the new `render` CLI, the gitignored `src/.env`), which exists nowhere else and would silently confuse the next session's test runs.

**Round 6 — "credential and blast-radius auditor" (session-specific, 4 findings applied).** Chosen because this session's distinguishing events were leaking a live API key and opening a hole in the production data boundary — failure modes none of rounds 1–5 look for, and ones where the cost of a dropped item is not lost time but a standing exposure. Applied: promoted both items to §0 above everything else, stated the pre-existing state each must be returned to (empty allow list), recorded that the key may already have been rotated so a reader does not assume the 400s are a different fault, and put both into the continuation prompt with the instruction to keep repeating them.

**Round 7 — "would a reader trust the wrong number?" (session-specific, 2 findings applied).** Chosen because this session produced a large table of measurements taken against a moving production dataset, and both reviewers independently attacked the *evidence quality* rather than the conclusions. Checked every figure quoted here against its source: corrected the subplan arithmetic to the plan's own 0.075 ms, and made §3 state that the count varied between runs because ingestion kept committing, so a future reader comparing against a fresh measurement does not conclude the numbers were fabricated.

Final pass through rounds 1–7 produced zero further material findings.
