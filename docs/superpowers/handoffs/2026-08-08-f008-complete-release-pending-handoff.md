<!-- ABOUTME: Handoff after F008 Phase D merged — the feature is complete on dev and the only -->
<!-- ABOUTME: F008 work left is the dev→main release, which is Sam's call. Written 2026-08-08. -->

# Handoff — F008 complete on `dev`, release pending (written 2026-08-08)

**This supersedes [`2026-08-08-f008-phase-d-and-release-handoff.md`](2026-08-08-f008-phase-d-and-release-handoff.md) entirely.** That document's §1 queue is now history: items 1 and 2 (execute Phase D, run the D5 verification) are done and merged, and its §2 review items are closed. Read it only for its §3 seam notes, which have been folded forward here anyway.

**Still authoritative and NOT restated here:**
- The **release runbook** — [`2026-08-07-f008-overnight-build-handoff.md`](2026-08-07-f008-overnight-build-handoff.md) §3 (idle-window deploy, the one-off resweep, the lock warning, the post-release re-measurement). This is the document the release executor needs.
- The **execution state** — [`docs/superpowers/plans/2026-08-06-f008-type-aware-contract-browsing.md`](../plans/2026-08-06-f008-type-aware-contract-browsing.md): per-phase banners, Deviations, and Discoveries.
- The **reasoning record** — [`2026-08-06-f008-decision-log.md`](../plans/2026-08-06-f008-decision-log.md), D1–D13.

## 0. Headline state

| | |
|---|---|
| `origin/dev` tip | `eee3ab3` (PR #146 merge) |
| Open PRs | **none** |
| F008 status | **All four phases merged.** Nothing about the feature is in flight. |
| This worktree | `.claude/worktrees/secret-scanning-validity-2eb72d`, branch `wip/f008-phase-d-merged` at `eee3ab3`, clean. Fully provisioned: `app/backend/.venv`, `app/backend/src/.env`, `app/frontend/web/node_modules`, scratch DB `hangar_bay_test_f008`. |
| Dev database | `hangar_bay_dev` is **migrated to head** (`685dab7d6df5`) and holds ~99 real ESI contracts. It was EMPTY before this session — `alembic current` printed nothing — so it was migrated forward from baseline. |
| Dev servers | Stopped. Postgres/Valkey containers are up (started from the main checkout, per ENV-10). |

**Phase D shipped as PR [#145](https://github.com/scarson/hangar-bay/pull/145) (merge `b961d8d`), closeout as [#146](https://github.com/scarson/hangar-bay/pull/146) (merge `eee3ab3`).**

## 1. The only F008 work left: publish `dev` → `main`

**This is Sam's call, not an agent's.** It is a production deploy carrying a one-off ~80-minute resweep.

Follow the 2026-08-07 handoff §3 runbook verbatim. The parts most likely to be mis-handled:

- **Time the deploy into the post-ingestion idle window** (DEPLOY-4). A `pre_deploy_failed` about 38 seconds in is the lock-timeout collision signature, not a migration bug — the response is to redeploy the same commit via the CD workflow's `workflow_dispatch` `sha` input, not to revert or re-merge.
- **The first post-deploy run is the ~80-minute resweep**, triggered by the `ENRICHMENT_VERSION` 1→2 bump that shipped in Phase A. The lock-token warning at its end is expected. **Do not redeploy mid-resweep.**
- **No gate needs flipping.** `GET /contracts/taxonomy` reports `complete` on its own once the corpus is restamped, and the item-level surface appears by itself (decision log D1). This was verified end-to-end against live ESI data this session: the endpoint went `partial` → `complete` with 7 categories / 56 groups and the controls appeared with no restart and no human action.
- **The release also carries PR #142** (the `preserve_on_null` name-column fix) and should finally turn the production live smoke green.
- **Post-release, re-measure the reshaped count query once** and record it in the perf-audit doc's §9. The unfiltered count path changed shape in Phase B (decision D2).

## 2. Follow-ups, none of them blocking

Each lives in the plan's Discoveries section; this is the index, not the content.

1. **Two nullable sorts place NULL inconsistently** — `volume` and `ship_name` lack `nulls_last()` while the three sorts Task B8 added have it, so a descending volume sort leads with every volume-less contract. **This was deferred to "PR-C/D" and both have now shipped without deciding it**, so it is a standalone backend follow-up rather than a queued task. Smallest real item here.
2. **Criterion 1.8's count-lifting is not applied to the offered-item filters** — an item-less segment's served count reads 0 whenever a taxonomy or blueprint filter is active. The zero is honest (clicking delivers exactly that empty page, with an explanation), but Criterion 1.8 asks for the lifted number. Backend, `_segment_counts`; needs a decision on whether "lifted" means all offered-item filters together or per-family.
3. **A window refocus spanning a readiness change costs one extra corpus-scale list request.** Accepted, not fixed — every fix is worse than the cost. Recorded because corpus-scale requests are what the 2026-08-02 perf audit is about.
4. **Two production-data measurements** — spec §15.1's market-group NULL-rate re-measure and B7's `_live_category_ids` EXPLAIN. Both need production access, which needs Sam to re-provision the rotated `RENDER_API_KEY` into the root `.env` (pitfall ENV-8: the launch-time export is per-session).
5. **Pre-existing, unrelated:** ~154 jsdom "Not implemented" lines in the frontend test output (measured on a clean sibling worktree, so not introduced by F008). Violates the pristine-output rule; nobody has owned it.

## 3. Seams a fresh agent will otherwise trip on

- **The main checkout is stale.** `/Users/sam/Code/hangar-bay` is on `dev` at `5cebd4b` — two merges behind `origin/dev` (`eee3ab3`). Per `docs/git-strategy.md`, advance it with `git fetch origin dev && git reset --hard origin/dev`, never a pull or a GUI Sync. Left alone deliberately: it is Sam's working checkout.
- **The sibling worktree `eve-ship-order-requirements-ddb49c` is a merged remnant** on `docs/f008-spec-d8-ratification` at `b26c0d6`. The superseded handoff points at it as "fully provisioned — Phase D can execute here"; that advice is now actively wrong, because its tree predates all of Phase D. **This** worktree is the provisioned one.
- **Checking out `claude/phase-d-release-handoff-8aa5cf` in this worktree reverts the tree to pre-Phase-D.** That branch is pinned at the old `dev` (`5cebd4b`). It looks like "the session's branch" and is not.
- **D13's summary in the superseded handoff was wrong and has been corrected in place.** If you read a cached copy saying the readiness gate "is read live", that is the design the review overturned. The shipped design is in D13.
- **Sam's PR #144 merged mid-session** (the D8 ratification, amending spec §3.1/§16.3). Phase D was rebased onto it cleanly; no interaction, but a plan reader should know §3.1's "exactly one branch" sentence is now scoped to boolean families.

## 4. Operational guardrails this session established

- **Quote codex prompts with a heredoc, never a double-quoted shell string.** Backticked terms in a double-quoted prompt run as command substitution and reach the reviewer as empty text. One round-3 review ran on a silently mangled prompt; the only tell was a single `command not found:` line in the output. Recorded in memory as [[codex-rounds-find-defects-in-fixes]].
- **Re-run the reviewer on the rework, not just on the original.** Four codex rounds returned 5, 1, 1, 0 P1s — **rounds 2 and 3 each found a defect inside the previous round's fix.** One round would have shipped four of the five original defects in a different shape.
- **A rejected alternative can become correct later, and nothing prompts a re-check.** Keying the list on readiness was correctly rejected for costing a second corpus-scale request per cold load; an `enabled` gate added two rounds later made that cost zero. The decision log recorded only the rejection. Full write-up in D13.
- **Scripted multi-test deletion is dangerous.** A `python` script removing two stale tests also removed a newly-written one; the suite stayed green because a neighbouring test asserted something similar. Codex caught it. Delete tests individually, or diff the test-name list before and after.

## 5. Test-infrastructure additions a frontend agent should know exist

Reaching for these rather than re-inventing them saves a cycle:

- `src/test/http.ts` — `taxonomyResponse()` and `withTaxonomy(handler, body?)`. **Every contracts view queries `/contracts/taxonomy` now**, so a URL-agnostic stub hands it a contract page by accident.
- `src/test/renderApp.tsx` — now returns `queryClient` alongside `router`, so a test can drive a background query directly (the readiness poll's real interval is five minutes).
- `e2e/helpers/api.ts` — `interceptTaxonomy(page, responder?)`, registered in a top-level `test.beforeEach` in **twelve** spec files. A new contracts spec needs the same, or its taxonomy request escapes the fixture lane.
- `e2e/fixtures/contracts.ts` — `taxonomy(overrides?)` builder, defaulting to `partial` so a spec must opt into the open surface.
- `src/features/contracts/columns.test.ts` — new; pins column-set invariants (no gated column may add a sort field, insertion position, key uniqueness).

## 6. Continuation prompt (paste-ready)

> Hangar Bay: F008 Type-Aware Contract Browsing is COMPLETE on `dev` (tip `eee3ab3`); there are no open PRs and nothing about the feature is in flight. Read `docs/superpowers/handoffs/2026-08-08-f008-complete-release-pending-handoff.md` first. The only F008 work left is publishing `dev` → `main`, which is Sam's call and follows the runbook in `docs/superpowers/handoffs/2026-08-07-f008-overnight-build-handoff.md` §3 — time it into the post-ingestion idle window (DEPLOY-4), expect the one-off ~80-minute resweep and its lock warning, do not redeploy mid-resweep, and flip no gates: `GET /contracts/taxonomy` reports `complete` on its own and the item-level surface appears by itself (decision log D1, verified against live ESI data). If you are instead picking up a follow-up, they are indexed in §2 of that handoff and detailed in the plan's Discoveries section — the smallest real one is extending `NULLABLE_SORTS` in `services/contract_service.py` to cover `volume` and `ship_name`, which both PR-C and PR-D shipped without deciding. Work from `.claude/worktrees/secret-scanning-validity-2eb72d` (branch `wip/f008-phase-d-merged`, fully provisioned, `hangar_bay_dev` migrated to head with ~99 real contracts); do NOT use the `eve-ship-order-requirements-ddb49c` worktree, which is a pre-Phase-D remnant despite what the superseded handoff says. Backend tests serialize on `DATABASE_URL_TESTS=…/hangar_bay_test_f008` with `ESI_USER_AGENT` exported; frontend requires all five lanes green before any completion claim.

## Appendix — adversarial review of this handoff

**Round 1 — naive fresh agent (3 findings applied).** Added the headline-state table (a fresh agent had no single place to learn the dev tip, whether anything was open, or which worktree to use); spelled out that the release is Sam's call rather than leaving it as an unattributed queue item; named the runbook's location instead of assuming the reader would find it.

**Round 2 — recency-bias audit (2 findings applied).** The session's last hour was the merge, which crowded out mid-session state: added §5's test-infrastructure inventory (built early, invisible by the end) and the note that `hangar_bay_dev` was empty and had to be migrated from baseline — a fact a future full-stack verifier needs and which nothing else records.

**Round 3 — seam auditor (3 findings applied).** Found the stale main checkout (`5cebd4b`, two merges behind), the sibling worktree that the superseded handoff actively recommends and should not, and the trap that checking out this session's apparent branch reverts the tree to pre-Phase-D.

**Round 4 — operational guardrails auditor (4 findings applied).** All of §4. The codex shell-quoting trap and the scripted-test-deletion trap existed only in the session transcript; the review-the-rework and stale-rejection lessons existed only in a decision-log entry a release-focused reader would never open.

**Round 5 — loss-averse audit (3 findings applied).** Swept the plan's Discoveries for anything the session invalidated: the `hasActiveFilters` entry was closed by D2 and still read as open, the Criterion 1.8 entry cited a deviation the review had reversed, and the nullable-sorts entry deferred to a PR train that has now ended without deciding. All three corrected in the plan, and the last promoted to §2 item 1 because a deferral whose target has shipped is otherwise invisible.

**Round 6 — reversal-integrity auditor (session-specific; 2 findings applied).** Chosen because this session's defining feature was reversing decisions I had already written into durable artifacts — two deviations withdrawn and D13 reversed twice. The failure mode is a stale summary of a reversed decision outliving the decision itself, since summaries are copied more often than they are re-read. Applied: corrected the superseded handoff's "the readiness gate is read live" line in place (it described the overturned design), and added §3's explicit warning for anyone holding a cached copy. Verified no other artifact summarizes D13 — checked the plan banners, the PR body, both memory entries, and the pitfalls file.

**Round 7 — release-executor rehearsal (session-specific; 1 finding applied).** Chosen because the sole remaining task has a different shape from everything this session did: it is an operations task, run possibly by Sam directly, under time pressure, against production. Read §1 as that person. Applied: promoted the three failure-mode specifics (the 38-second collision signature and its correct response, "do not redeploy mid-resweep", and "no gate needs flipping") from prose scattered across the runbook reference into named bullets, because an operator mid-incident scans rather than reads.

**Final pass through all seven rounds: zero material findings.**
