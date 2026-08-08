<!-- ABOUTME: Handoff after the 2026-08-08 overnight campaign: handoff-§2 follow-ups shipped, pre-release -->
<!-- ABOUTME: bug hunt executed (3 fix PRs merged, schema PR #156 held for Sam), perf plan dispositioned. -->

# Handoff — overnight campaign complete; PR #156 and the release await Sam (written 2026-08-08, late)

**Supersedes** [`2026-08-08-f008-complete-release-pending-handoff.md`](2026-08-08-f008-complete-release-pending-handoff.md)'s
§2 follow-up queue (all items resolved) and its §0 worktree/machine facts (that worktree is gone;
this session ran on the **Windows** machine — see the decision log's OD1/OD6 for what exists here
now). Its §1 release runbook pointer remains authoritative and is NOT restated:
[`2026-08-07-f008-overnight-build-handoff.md`](2026-08-07-f008-overnight-build-handoff.md) §3.

## 0. Headline state

| | |
|---|---|
| `origin/dev` tip | `0c8ed62` + docs merges (PRs #148–#155 all merged) |
| Open PRs | **#156 only** — `fix/price-nullable`, `Review — database schema`, deliberately held for Sam |
| Machine | Windows (`C:\Users\Sam\Code\hangar-bay`); provisioned this session — OD1/OD2/OD6 in the [overnight decision log](../plans/2026-08-08-overnight-followups-decision-log.md) |
| Worktree | `.claude/worktrees/pr-147-handoff-beaace`, fully provisioned (backend `.venv`, `src/.env`, node_modules, Playwright chromium, scratch DB `hangar_bay_test_f008`) |
| Test baselines | backend 686 green · frontend eslint/tsc clean, vitest 320×2, e2e 140 — all green at handoff |

## 1. What Sam decides next (in priority order)

1. **The production DB IP allow rule `198.37.143.189/32`** — flagged "REMOVE - temp troubleshooting
   2026-08-02", still open, needs Render access (ENV-8). Security, not perf. Two minutes once the
   rotated `RENDER_API_KEY` is available. *(Perf disposition §"Still open" item 1.)*
2. **PR #156** (`price` nullable end-to-end) — schema migration, so held per merge policy. Two codex
   rounds ran on it (0 P1 initially; round 2 found a real pre-existing P1 in env.py's offline path,
   fixed and pinned). The PR body carries the full case, including why `0.0`-defaulting was
   rejected (ESI-3).
3. **The `dev` → `main` release** — unchanged from the prior handoff; runbook §3 there. PR #156 can
   ride the release or follow it, Sam's call — nothing else depends on it.
4. **Design decisions D-a–D-k** from the bug hunt (none blocking) — enumerated in
   [`docs/bug-hunts/2026-08-08-f008-prerelease-consolidated.md`](../../bug-hunts/2026-08-08-f008-prerelease-consolidated.md).
   The two most consequential: D-a (migrate `search`/`type_ids` to §3.1's offered-only EXISTS
   semantics — also closes the perf audit's P5 remainder) and D-b (mirror segment counts — the
   complete answer to the numeral suppressions PR #155 shipped as stopgap).

## 2. What shipped tonight (all merged unless noted)

- **PR #148** — `NULLABLE_SORTS` gains `volume`/`ship_name` (handoff-§2 item 1).
- **PR #149** — jsdom scrollTo/canvas stubs; test output pristine (item 5).
- **PRs #150/#151** — Criterion 1.8 count-lifting resolved as working-as-designed (item 2; OD4
  ratified under Sam's delegation).
- **PR #152** — bug-hunt artifacts: 4 hunter reports + consolidated findings (7 confirmed bugs,
  11 design decisions) + remediation plan (5-round review cycle) + perf-remediation disposition +
  TEST-22.
- **PR #153** — parser junk-tolerance gaps: blueprint-bound integer guard, per-field default sort
  direction (courier entry now Time-left *ascending*), `contract_type` dedupe.
- **PR #154** — composition pluralization by name shape; false comment fixed.
- **PR #155** — item-bearing segment numerals hidden when either the captured or live search is
  item-less (D11 rule extended, WEB-1 capture); accepted residuals documented at the predicate.
- **PR #156 (OPEN, Sam's)** — `price` nullable: migration with locked SQL-emitted downgrade guard,
  `NULLABLE_SORTS`, watchlist matcher NULL-render fix, detail-page dash, TEST-22 ingestion test,
  offline-render pin; plus TEST-23 and the env.py offline transaction-wrapper fix.

## 3. The queued docket (next sessions)

1. **Perf quick-wins** — ranked list in
   [`docs/perf-audits/2026-08-08-remediation-status.md`](../../perf-audits/2026-08-08-remediation-status.md)
   §"Still open, worth doing". Local, no production access needed: item upsert batch 50→500
   (`background_aggregation.py:584` — one line), search debounce (`FilterRail.tsx` — the React
   rewrite dropped it entirely; every keystroke is a corpus-scale double-ILIKE), the two remaining
   location indexes (schema → `Review` classification, could fold into a wave with D-g's
   issuer-int64 widening). The bigger items (Valkey cache-aside, ESI fan-out semaphore, ingestion
   streaming) each deserve their own plan.
2. **Test-coverage review of the F008 surface** (`test-coverage-review` skill). Inputs already
   queued: O1/O2 from the consolidated report (fixture wire-mirror drift, type-partition
   invariant) and PR #156's deferred e2e null-price type pin.
3. **Reward-per-jump spec + plan.** Groundwork is better than the task list assumed: the courier
   spike ([`2026-08-01-courier-route-jumps-spike.md`](../specs/2026-08-01-courier-route-jumps-spike.md))
   measured the live population (161 ESI calls, 8.4 s cold) and F008 spec §15.2 records what the
   follow-on inherits — including the ESI `/route/` GET→POST shape change entangled with the open
   ESI-4 pinning decision. Produce spec + plan for Sam's review before implementing; the route-graph
   data source is an architectural decision.

## 4. Seams a fresh session will otherwise trip on

- **Machine gotchas are in memory and OD6**: `pdm` via `python -m pdm`; npm rewrites
  `package-lock.json` (never commit that churn); baseline all five lanes; backend tests serialize
  on `hangar_bay_test_f008` with `ESI_USER_AGENT` exported.
- **`blank_migrated_sync_connection` is SESSION-scoped** (TEST-23, learned expensively tonight):
  consumers must be footprint-free; a mutating consumer poisons its siblings in whatever error the
  sibling's first statement produces.
- **Codex on this machine**: quote prompts with heredocs; tell it up front that `.private-journal/`
  and `.serena/` are out-of-scope agent tooling or it stops to ask; `gh pr merge` inside the
  worktree can't do local branch cleanup (dev is checked out at the repo root) — the merge itself
  succeeds.
- **Never chain the CI-green check and the merge with `;`** — the check's output must gate the
  merge (`grep non-green && block || merge`). The one process slip tonight is recorded in the
  decision log under OD7's addendum.
- **Fixture regions claimed through 99999973** (99999972 nullable sorts, 99999973 price sort);
  next free is 99999974.

## 5. Continuation prompt (paste-ready)

> Hangar Bay: read `docs/superpowers/handoffs/2026-08-08-overnight-campaign-handoff.md` first. All
> overnight follow-ups and the F008 pre-release bug-hunt remediation are merged to `dev`; the only
> open PR is #156 (`price` nullable, `Review — database schema`) which ONLY Sam merges, and the
> dev→main release remains Sam's call per the 2026-08-07 handoff §3 runbook. Work the queued docket
> in §3 of the handoff: perf quick-wins from the ranked list in
> `docs/perf-audits/2026-08-08-remediation-status.md`, then the F008 test-coverage review (inputs
> O1/O2 in the consolidated bug-hunt report plus PR #156's deferred e2e null-price pin), then the
> reward-per-jump spec. Mind §4's seams — session-scoped migration fixture (TEST-23), npm lockfile
> churn, codex heredocs, and CI-gating merges properly. Work from
> `.claude/worktrees/pr-147-handoff-beaace` (fully provisioned) on the Windows machine; backend
> tests serialize on `DATABASE_URL_TESTS=…/hangar_bay_test_f008` with `ESI_USER_AGENT` exported;
> all five frontend lanes green before any completion claim.
