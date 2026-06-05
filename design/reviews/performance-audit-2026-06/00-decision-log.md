# Performance Audit Cycle — Decision Log

**Run owner:** Claude Code (autonomous session, no user available — user in transit).
**Date:** 2026-06-05 (UTC).
**Skill under test:** `superpowers-plus/performance-audit-cycle` (+ sibling `performance-audit`),
vendored into this repo at `.claude/agent-skills/plugins/superpowers-plus/skills/` from the
attached `agentskills.zip`.
**Planning commit SHA:** `68925a0` (the partition was designed against this tree state).

This log exists because the operator explicitly asked: *"approach decisions from multiple
perspectives, do at least three rounds of adversarial review, and document the decision in a
persistent artifact."* It is the durable record of every non-trivial judgement call this run made,
so a fresh context (or the operator on landing) can audit the reasoning, not just the output.

---

## Decision 0 — The "attached zip" was initially absent, then arrived. How to proceed.

**Context.** The task said "add the skills in the attached zip." For the first ~30 minutes of the
session the zip was **not present anywhere** in the container: exhaustive search of the filesystem
(`find / -iname '*.zip'`), the Claude upload/projects/session dirs, and the conversation JSONL all
came up empty; the `superpowers` plugin (installed fine from the official marketplace) does **not**
contain a `performance-audit-cycle` skill; and no such skill exists publicly (web search). I had
begun designing a fallback (reconstruct the skill from its name + best practices, clearly labelled)
when the operator's harness delivered the real upload at
`/root/.claude/uploads/.../14ad1d69-agentskills.zip` (later a second identical copy; verified by
md5 `9213979e…`).

**Decision.** Discard the reconstruction path entirely; use the **real** skill. The reconstruction
scaffolding I had created (`.claude/skills/performance-audit-cycle/`) was deleted before it was
committed, so nothing invented leaked into the repo.

**Why it matters for the operator.** Had the zip never arrived, the documented fallback would have
been: run a methodologically-sound perf audit anyway (the *audit* is the real deliverable), produce
the feedback as "feedback on a reconstruction, not your skill," and flag the missing input loudly.
The zip arriving made that moot — recorded here only so the decision trail is complete.

---

## Decision 1 — Marketplace + plugin install

**Options weighed.** (a) `claude plugin install superpowers@claude-plugins-official` directly —
failed: marketplace not configured locally. (b) Add `obra/superpowers-marketplace` (the community
source). (c) Add the official `anthropics/claude-plugins-official` marketplace, then install.

**Decision:** (c). The task named the *official* marketplace explicitly. `claude plugin marketplace
add anthropics/claude-plugins-official` → `claude plugin install superpowers@claude-plugins-official`
succeeded (superpowers **v5.1.0**, user scope; its 14 skills are now active in-session). This is the
genuine official artifact, not a third-party mirror — the right call for provenance.

**Note:** `superpowers` (official) and `superpowers-plus` (the zip) are *different* plugins. The
perf-audit family lives only in `superpowers-plus` (the zip), which is why installing `superpowers`
alone never surfaced `performance-audit-cycle`.

---

## Decision 2 — Where to put the vendored skills

**Options.** Repo root `plugins/` (mirrors the zip; clutters root of an EVE-marketplace app); a
project skills dir `.claude/skills/<name>/` (auto-loadable but flattens the marketplace structure
and drops `plugin.json`/scripts); or `.claude/agent-skills/<zip structure>` (faithful copy,
Claude-namespaced, out of the app's way).

**Decision:** `.claude/agent-skills/` preserving the zip's `plugins/` + `scripts/` layout verbatim,
including `plugin.json` (so `plugin_version` is recoverable for run metadata) and the test fixtures.
I kept the *entire* bundle (all three plugins, 161 files, ~2.8 MB) rather than pruning to just the
perf-audit skill, because the operator said "add the skills in the attached zip" (plural, whole
bundle) — under-delivering by pruning risks more than the modest size cost. The ~900 KB of
`url-to-markdown` HTML test fixtures is the bulk of the size; noted as a tradeoff, not hidden.

**Execution mechanism.** I run the skill by **reading its `SKILL.md` and following the methodology**
(the runner role), which works regardless of install location — I did not need Claude Code to
auto-load `superpowers-plus` as an active plugin. The operator only asked to *install* `superpowers`
(done) and *add* the zip skills to the repo (done); they did not ask to install `superpowers-plus`
as a live plugin.

---

## Decision 3 — Scope routing: whole-repo, so start at the size-router

Per `performance-audit-cycle/SKILL.md`, a "whole repo" request MUST start at
`whole-repo-scoping.md`'s size-router, never cram everything into one run.

**Survey (production LOC, tests/migrations/generated excluded):** backend **~2,018** Python LOC;
frontend **~506** TS LOC (+ a little HTML). Two ecosystems, one real process boundary
(FastAPI service ↔ Angular SPA).

**Router outcome.** This is the lightweight/full boundary: ≤2 languages, but **3 natural slices**
(below). The lightweight path's PRIMARY gate is "≤2 natural slices"; we have 3, so I took the
**full survey-through-execute method with the review gate** — but scaled to the small surface (the
LOC bands keep each slice well inside one run's capacity, so no sub-partitioning).

See `01-slice-plan.md` for the survey table, hot-path map, the partition, the coverage ledger, depth
tiers, and cross-slice frequency calibration.

---

## Decision 4 — The partition (3 slices) and three adversarial review rounds

The method requires reviewing the partition *before* spending runs on it. For 3–5 slices it asks for
**1** general round with the partition-design checklist folded in. The **operator asked for ≥3
rounds**, which is the stronger bar — so I ran three. Each round attacked the partition grounded in
the actual code; revisions between rounds are recorded.

**Candidate partition (entering review):**
- **S1 — Backend read/request pipeline** (HOT, FULL): the user-facing IO-bound read path.
- **S2 — Backend ESI ingestion & aggregation** (HOT, FULL): the scheduled ESI-fan-out + bulk-write path.
- **S3 — Frontend Angular SPA** (WARM/latent, REDUCED + payload-startup).

### Round 1 — sizing & hot-path accuracy (general lens)
- *Attack:* Is splitting the ~2k-LOC backend into two slices over-fragmentation? The prefer-fewer
  tie-breaker says merge unless they differ in hot-path character.
- *Finding:* They genuinely differ. S1's frequency driver is **request rate** and its hot-path
  character is **per-request latency** (the listing query, serialization). S2's frequency driver is
  the **15-minute scheduler interval** and its character is **batch throughput / network fan-out**
  (per-contract ESI item fetches, bulk upserts). Different character AND different frequency driver →
  the split/keep rule says **SPLIT**. Kept the split.
- *Attack:* Is the hot-path hypothesis name-inferred? Verified against code: S1's
  `get_contracts` builds a real DISTINCT-count-over-outer-join + a leading-wildcard `ILIKE`; S2's
  `_process_contracts` has a real serial `await get_contract_items()` per contract. Both hot paths
  are code-confirmed, not name-inferred. ✓

### Round 2 — mis-tiering, latent/dead code, coverage (partition-design lens)
- *Attack:* Is S3 (frontend) really WARM, or is it latent? `app.routes.ts` is `routes = []` — the
  SPA has **no wired routes**, so `ContractSearch`, the resolver, and the pipes are **reachability ≈
  0 today** (latent, "fires once wired in"). Re-tiered S3 from a naive "WARM render path" to
  **WARM-latent**: run a REDUCED + payload-startup pass, and *expect* the lanes to honestly return
  mostly latent/structural notes — this is the run's built-in **anti-padding stress test** (will the
  lanes manufacture render nits over code nothing currently reaches?).
- *Attack:* Coverage gaps / double-counts. `models/contracts.py` is shared by S1 (read/index
  relevance) and S2 (write target). Per the shared-substrate rule it is audited **once** — homed in
  **S1** (where the index/query-shape lens matters most) and *referenced* by S2, not re-sliced. The
  two `config.py` modules and `core/logging.py` were explicitly homed (S1) so nothing falls through.
  Built the disjoint-coverage ledger against an actual `find` listing (see slice plan). ✓
- *Revision:* Added `main.py` (app wiring, middleware, the destructive `create_db_tables`) to S1
  rather than leaving it unhomed.

### Round 3 — cross-slice frequency calibration (the lens a hot-path hunt misses)
- *Attack:* Does any slice's hot symbol have its **frequency set by a caller in another slice**,
  causing under-ranking? Walked the candidates: `bulk_upsert` (db_upsert) is called **only** from S2;
  `get_contracts` only from S1's router; the ESI client's caching helper only from S2. The
  read path and the write path are **independent** — no cross-slice impl/caller split that would
  under-rank a finding. The one genuine shared substrate, the **`contracts`/`contract_items` table
  schema + indexes**, is a fan-in: its *read* frequency (S1, per request) and *write* frequency (S2,
  per interval) both bear on index design, so missing-index findings are calibrated against the
  **hotter** caller (S1 per-request reads). Recorded this as adjacent context for both slices rather
  than building a formal frequency map (a ≤1-page map would be overkill at this size). ✓
- *Outcome:* Round 3 found only this one calibration nuance (already handled), i.e. **nits only** →
  partition finalized.

**Final partition: 3 slices as above.** Recorded in `01-slice-plan.md` with the coverage ledger.

---

## Decision 5 — Verification mode: static-only (dynamic lane deferred)

The environment has no running PostgreSQL + Valkey + a representative dataset, and no load test or
production-like ESI workload exists. Per the skill, fabricating benchmark numbers is forbidden.
**Decision:** run **static-only**; the `dynamic` lane is **deferred** for every slice, recorded as
such, and all findings rest on complexity/allocation/structural arguments or query-shape reasoning —
never invented ms. Where a finding *could* be confirmed cheaply later, the verification plan says so.

I did **not** stand up Postgres+Valkey to construct a workload, because any dataset I invented would
not reflect real ESI contract volumes/distributions — a meaningless micro-benchmark is worse than an
honest complexity argument. This is the skill's own guidance and the right call.

---

## Decision 6 — Lane dispatch: real parallel subagents, blind, lane-reads-own-pack

To actually **test** the skill (the operator says the feedback matters as much as the audit), I
dispatch each lane as a real independent subagent (the Agent tool), **blind** (given scope/load
context only, never my pre-suspected findings), in **lane-reads-own-pack** mode (each subagent reads
its profile-pack slice from the vendored path itself). This exercises the skill's core
parallel-discovery primitive and the dispatch-adaptation path the feedback template specifically
asks about. The harness (Claude Code Agent tool) exposes **no reasoning-effort knob**, so run
metadata records `reasoning_effort: "default (harness exposes no knob)"` — the honest value, not a
claimed `x-high`. Model requested: the strongest available tier the harness allows for subagents.

---

## Decision 7 — Artifact paths: follow the skill's `docs/perf-audits/`, keep meta under `design/reviews/`

The skill hard-codes `docs/perf-audits/` (run artifacts) and `docs/plans/` (remediation plan). This
repo instead uses `design/` (specs, reviews) and a top-level `plans/`. **Decision:** for the
skill-*generated* artifacts (raw lane reports, consolidated reports, `runs.jsonl`, validated reports,
the remediation plan) I follow the skill's literal paths — that is part of faithfully running and
testing it, and Phase 8's `git add docs/perf-audits/...` works as written. My *meta* artifacts about
running the skill (this log, the slice plan, the progress ledger, the field feedback) live under
`design/reviews/performance-audit-2026-06/`, matching the repo's existing `design/reviews/`
convention. The `docs/` vs `design/`+`plans/` path mismatch is captured as ergonomics feedback
(feedback area 8) rather than silently papered over.

---

## Standing constraints honoured this run
- **Commit + push after every work item** (ephemeral container) — each slice's artifacts are
  committed and pushed as they complete; the progress ledger is updated per slice and is the resume
  point.
- **No fabricated measurements**; static/complexity arguments only.
- **Audit records bugs, never chases them** — correctness issues spotted (e.g. the unconditional
  `drop_all`/`create_all` on startup, the `start_location_id` schema/model nullability mismatch, the
  frontend↔backend response-shape mismatch) go to a Suspected Bugs appendix + a bug-hunt kickoff, not
  fixed here.
- **Persistent-artifact reference discipline** — findings are referenced by self-contained
  descriptions; `P#`/lane-slug only as traceability suffixes.
