<!-- ABOUTME: Handoff for the next work after the F008 overnight build — Phase D execution and the -->
<!-- ABOUTME: dev→main release, with the state changes since the 2026-08-07 handoff (PR #142, credentials). -->

# Handoff — F008 Phase D + release (written 2026-08-08)

**Read this first, then the plan's banners.** This supersedes the *queue* sections of [`2026-08-07-f008-overnight-build-handoff.md`](2026-08-07-f008-overnight-build-handoff.md) (three state changes below); that document's §3 production runbook, §4 guardrails, and §5 machine-state notes remain accurate and are NOT restated here. The authoritative execution state is the plan, [`docs/superpowers/plans/2026-08-06-f008-type-aware-contract-browsing.md`](../plans/2026-08-06-f008-type-aware-contract-browsing.md); the reasoning record is the decision log, [`2026-08-06-f008-decision-log.md`](../plans/2026-08-06-f008-decision-log.md) (D1–D11).

## 0. State changes since the 2026-08-07 handoff (all confirmed by Sam, 2026-08-08)

1. **Both standing credential items are RESOLVED** — `RENDER_API_KEY` rotated; the `198.37.143.189/32` allow rule removed from `hangar-bay-db`. The repeat-in-every-handoff instruction (standing since 2026-08-02) is ended. Production API/DB access for agents remains subject to Sam re-provisioning the rotated key into the root `.env` via 1Password — a session needing the Render MCP still needs the launch-time export (pitfall ENV-8).
2. **PR #142 is MERGED to `dev`** (merge `ade36e2`) — the decision-log D10 follow-up, built in a separate session from the task chip: `bulk_upsert` gains `preserve_on_null` coalesce-on-conflict semantics for the four name columns, with a dialect guard (its codex P2) and new pitfall **SQLA-5**. Consequence for this repo's habits: a degraded `/universe/names` run no longer blanks previously-resolved contract names.
3. **Sam has seen the build ("good work") but D8 is NOT yet explicitly ratified** — see §2.

> **Update, 2026-08-08 (later the same day):** queue items 1 and 2 are **DONE** — Phase D is built and the D5 full-stack verification ran against real ESI data, both on `feat/f008-item-surface` ([PR #145](https://github.com/scarson/hangar-bay/pull/145), `Routine`). §2's D8 item is also closed: Sam ratified it and amended spec §3.1/§16.3 via PR #144 (merge `4f97694`). **What remains from this handoff is queue item 3, the `dev` → `main` release, and item 4's two production-data measurements.** The plan's Phase D banner and its Task D5 record carry the execution state; three new artifacts came out of the build — decision **D13** (why the readiness gate is read live), pitfall **WEB-2** (a borrowed formatter rounds a measurement into a false claim), and a Discoveries entry noting that Criterion 1.8's count-lifting is not applied to the offered-item filters. The rest of this document stands as written.

## 1. Next work, in order

1. **Execute Phase D** (plan Tasks D1–D5): the item-level surface — taxonomy cascading filter, ME/TE/runs controls, BPC columns, composition cells, want-to-buy split — all gated client-side on the taxonomy readiness signal. Branch `feat/f008-item-surface` off current `dev` (`ade36e2` or later). The Phase D banner carries the executor corrections (EIGHT params for `toSavedSearchParameters` — `contract_type` landed with C3; and the D2 gating note from the B6 review advisory about taxonomy selections zeroing clickable item-less segments). PR-D classification: `Routine` (frontend-only) under normal merge authority; **the 2026-08-06/07 self-merge grant for Review-classified PRs has lapsed** — anything Review-classified now waits for Sam again.
2. **Include the plan's D5 full-stack verification** — it was deferred with Phase D and is the one remaining evidence gap for the whole feature: migrate the dev DB (`pdm run migrate` with the test-env exports; this worktree does not auto-wipe), run backend + frontend dev servers, click through segments/filters against real ESI-ingested data, screenshot for the report.
3. **Publish `dev` → `main`** when Sam calls it — the 2026-08-07 handoff §3 runbook governs (idle-window deploy, the one-off ~80-minute resweep with its expected lock warning, the automatic readiness flip, and the post-release re-measurement of the reshaped count query recorded into the perf-audit §9). This release also carries PR #142 and should finally turn the production live smoke green. Phase D does NOT gate the release (decision-log D1) — publish whenever suits.
4. **Deferred measurements** (unchanged): the spec §15.1 market-group NULL-rate re-measure and the B7 `_live_category_ids` EXPLAIN both want production data access — now unblocked in principle by the key rotation, but they need Sam to re-provision access first.

## 2. Sam's open review items

- **Decision-log D8** — the range-filter branch-membership ruling where spec §3.1 conflicts with its own existential rule. Codex formally objected that a binding-spec interpretation was the owner's call; implementation follows the existential reading. A general "good work" is not treated as ratification of a specific contested ruling: **please ratify or overrule D8 explicitly**, and on ratification amend §3.1's "exactly one branch" sentence to scope it to boolean families.
- **D11 semantics spot-check** (optional): a segment-reconciled sort persists through Clear filters, and the All tab is count-less while an item-less segment is active — both are deliberate; if either feels wrong in use, they're cheap client-side reversals.

## 3. Seams a fresh agent should know

- **PR #142 vs Phase D:** no interaction — #142 touched `db_upsert`/ingestion name columns; Phase D is frontend-only. But #142's session added pitfall **SQLA-5** and edited `background_aggregation.py`; a Phase D executor rebasing old local branches should take `dev` as truth, not this worktree's leftovers.
- **This worktree** ends on branch `docs/f008-phase-d-handoff`; earlier `feat/*` locals are merged remnants. Phase D can execute here (env is fully provisioned — scratch DB `hangar_bay_test_f008`, `src/.env`, both installs) or in a fresh worktree per the 2026-08-07 handoff §5's bring-up notes.
- **The plan's Deviations/Discoveries subsections are load-bearing** for Phase D: they correct several task instructions post-review (B8's sort parenthetical, the C1 Column-interface deltas, the eight-param count). Read them before the task sections, as the plan's own header instructs.

## 4. Continuation prompt (paste-ready)

> Pick up Hangar Bay F008 Phase D. Read `docs/superpowers/handoffs/2026-08-08-f008-phase-d-and-release-handoff.md` first, then the plan `docs/superpowers/plans/2026-08-06-f008-type-aware-contract-browsing.md` — its Global Constraints, Deviations/Discoveries subsections, and the Phase D section (banner ⏸ with pickup corrections). Phases A/B/C plus PR #142 are merged to `dev`; branch `feat/f008-item-surface` off `dev` and execute Tasks D1–D5 with the plan's TDD steps, finishing with the D5 full-stack browser verification. PR-D is `Routine` (frontend-only) — normal merge authority; anything Review-classified waits for Sam (the overnight grant lapsed). Decision-log D8 awaits Sam's explicit ratification and is not a Phase D blocker. Backend tests: serialize on this worktree's `DATABASE_URL_TESTS=…/hangar_bay_test_f008` with `ESI_USER_AGENT` exported; frontend: all five lanes green before any completion claim.

## Appendix — adversarial review of this handoff

**Round 1 — naive fresh agent (2 findings applied):** spelled out that the self-merge grant LAPSED (a fresh agent reading the F008 PRs would otherwise infer standing authority); made the continuation prompt name the exact env vars rather than "the usual exports".
**Round 2 — recency-bias audit (2 findings applied):** restored the two deferred measurements (mid-build items, easy to lose behind today's news) and the ENV-8 note that key rotation ≠ restored agent access.
**Round 3 — seam auditor (2 findings applied):** added §3's #142-vs-Phase-D non-interaction and the worktree-leftovers-vs-dev caution; pointed Phase D at the plan's Deviations before its task text.
**Round 4 — operational guardrails (1 finding applied):** the D5 verification gap promoted from a footnote to queue item 2 — it is the only evidence class the feature still lacks.
**Round 5 — loss-averse audit (1 finding applied):** recorded that "good work" was deliberately NOT treated as D8 ratification, so the next session re-asks instead of assuming.
**Round 6 — authority-transition auditor (session-specific; 2 findings applied).** Chosen because this session's defining feature was a temporary expansion of agent authority (merge grant, decision latitude) now contracting back to defaults — the failure mode is a successor agent inheriting the expanded posture. Applied: the grant-lapse statement in §1.1 and the PR-D classification note; verified no other instruction in this doc presumes the lapsed grant.
**Final pass through all rounds: zero material findings.**
