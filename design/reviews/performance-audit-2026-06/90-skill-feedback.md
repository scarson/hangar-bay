# Field Feedback — `performance-audit` / `performance-audit-cycle` (superpowers-plus)

> Written **while** running the skill against a real repo, per the skill's own
> `feedback-template.md`. Legend: 👍 worked well · 🟡 friction/ambiguity · 🐞 likely defect ·
> 💡 suggestion. This is a living log; the verdict + top-3 are at the bottom.

## Context header

```
Repo / project:   Hangar Bay — EVE Online public-contract marketplace (ship sales)
Scale:            ~2,018 prod LOC Python backend + ~506 prod LOC Angular/TS frontend;
                  2 ecosystems; single repo, one process boundary (FastAPI ↔ Angular SPA)
Stack highlights: FastAPI 0.115, SQLAlchemy[asyncio] 2.0.41, asyncpg, redis/Valkey, httpx,
                  APScheduler, Pydantic v2, structlog, Prometheus; Angular 20 zoneless+signals,
                  RxJS 7.8, TS 5.8
Skill(s)+version: performance-audit + performance-audit-cycle; superpowers-plus, vendored from
                  agentskills.zip (version per plugin.json)
Harness:          Claude Code (web/remote, ephemeral container); Agent-tool subagent dispatch;
                  model = strongest tier harness allows; NO reasoning-effort knob exposed
Scope run:        whole-repo via whole-repo-scoping.md → 3 slices (S1 read, S2 ingestion, S3 frontend)
Depth:            S1 FULL, S2 FULL, S3 REDUCED+payload-startup (latent); dynamic deferred (static-only)
Blind run?        yes — lanes given scope/load context only, not pre-suspected findings
```

---

## Running notes by area

### 1. Setup, onboarding & dispatch harness
- 🟡 **The named install command doesn't work from a clean machine.** `claude plugin install
  superpowers@claude-plugins-official` failed with "marketplace not found"; the official marketplace
  is auto-present in interactive Claude Code but **not** in this remote CLI. Had to
  `claude plugin marketplace add anthropics/claude-plugins-official` first. *(This is a superpowers/
  Claude-Code-distribution nit, not a perf-audit-skill defect — but it's the first friction a new
  user hits following the README verbatim.)*
- 🐞→clarified **`superpowers` ≠ `superpowers-plus`.** The perf-audit family is in `superpowers-plus`
  (the zip), **not** the official `superpowers` plugin. Installing `superpowers` alone and looking for
  `performance-audit-cycle` finds nothing. The zip's top-level README should state this loudly, and
  ideally the perf-audit `SKILL.md` "install location" references should name the plugin so a runner
  who only has `superpowers` knows they need `superpowers-plus`. *(Fix: superpowers-plus/README.md +
  a one-line note in performance-audit/SKILL.md Phase 2.)*
- 👍 **`plugin_version` is recoverable** because the zip keeps `.claude-plugin/plugin.json`. The
  run-schema's honesty note about vendored-flat skills (version unavailable) is well-judged — vendoring
  the *whole* plugin dir (not flat into `.claude/skills/`) preserved it.
- 🟡 **No reasoning-effort knob.** The Agent tool lets me pick a subagent model but exposes no effort
  level. The skill *anticipates this exactly* (`run-schema.md` honesty constraint) — 👍 for that — and
  I recorded `reasoning_effort: "default (harness exposes no knob)"`. Good that the skill told me what
  to write instead of leaving me to fudge `x-high`.

### 2. Scope handling
- 👍 **The size-router routed cleanly.** "Whole repo" → `whole-repo-scoping.md` size-router → measured
  production LOC → recognized this as the lightweight/full boundary. The PRIMARY-gate-on-slice-count
  (≤2) vs LOC-as-secondary framing is right: LOC alone (~2.5k) screamed "lightweight," but 3 natural
  slices pushed me to the full method. Without that explicit "slice count is primary" rule I'd have
  under-ceremonied it.
- 🟡 **"Same axis at two scales" took a second read.** The rule that a backend+SPA in one repo is a
  *process boundary* (handled by one-primary-ecosystem) and **not** a per-service split is correct but
  dense. A one-line worked example ("FastAPI + Angular in one repo → 1 process boundary → ≥1 slice per
  side, NOT a service-monorepo split") in the "One program, or many?" section would save the re-read.
- 👍 **Latent-code guidance paid off immediately.** `app.routes.ts = []` makes the entire frontend
  reachability ≈ 0 today. The "LIVE-uncertain / fires once wired in" framing gave me the exact handle
  to tier S3 as WARM-**latent** and to set up the anti-padding stress test, instead of either dropping
  it (false "done") or auditing it as if hot (false findings).
- 💡 **Python LOC band vs reality.** The Python per-slice band (~0.5–2k) put my ~2k backend right at
  the ceiling as *one* unit, but hot-path *character* (request-latency vs batch-fan-out) is what
  actually justified the 2-way split — not LOC. The method does say "build-unit/character is the
  primary sizer, LOC is a check," and that was the correct guide here; just noting the band would have
  *merged* these two and been wrong. The character rule rescued it. (Working as intended; logging as a
  datapoint that character > LOC held on a real repo.)

### 3. Detection & pack loading (Phase 0)
- 👍 Manifest detection was unambiguous: `pyproject.toml` → FastAPI/SQLAlchemy/asyncpg/redis/httpx;
  `package.json` → Angular 20. Content-detection correctly flags the **SQL companion pack** (the read
  path hand-shapes a DISTINCT-count-over-join subquery, and the schema/DDL is in scope via the ORM
  models) and selects the **Postgres** dialect (asyncpg DSN).
- 👍 **Materiality gate works.** `import json`/`asyncio` appear incidentally, but asyncio *is* central
  to S2 (the ESI fan-out), so loading `python/async-asyncio.md` for S2 but treating it as peripheral
  for S1 is exactly the materiality call the pack asks for.
- 🟡 The Angular stack is **zoneless + signals** (Angular 20). Whether the `javascript-typescript/
  angular.md` module's lens is current for zoneless (vs Zone.js/OnPush-era advice) is something the
  idiom-currency lane has to verify — flagged for that lane to check (see area 5 once lanes return).

### 4. Lane dispatch (Phase 2)
- 👍 **`lane-reads-own-pack` was the right mode and it worked at scale.** The Agent-tool subagents
  don't share my skill registry (can't `Skill`-invoke `performance-audit` by name), so I used the
  first-class "lane reads its own slice" path: each subagent was told the exact pack files to read
  from `.claude/agent-skills/.../profile-packs/…` + its scope + output path. 18 lanes across 3 slices,
  each read only its lens — no runner-side pack re-pasting. The skill *names this exact case* (subagents
  without the registry) — 👍 it predicted my environment.
- 🟡 **I had to hand-author the dispatch prompts** (shared preamble + lane body, filling placeholders)
  per lane because nothing ships a ready-to-paste, parameterized dispatch block. `lane-prompts.md` has
  the bodies, but assembling "preamble + body + stack profile + pack paths + scope + output path" into
  a runnable subagent prompt was manual boilerplate I repeated 18×. **💡 Ship a dispatch *template*
  (a fill-in-the-blanks block, or a tiny script that emits one prompt per lane given scope + pack
  paths)** — `lane-prompts.md` is the content, but the *assembly* is left entirely to the runner.
  (Pointer: `performance-audit/lane-prompts.md` + SKILL Phase 2.)
- 👍 **Blind discovery genuinely DISCOVERED.** Lanes were given only load/scope context, never my
  pre-suspected findings. They independently reconstructed the entire S1 hot-path map (fan-out join,
  DISTINCT count, missing cache, pool ceiling) and the S2 budget (the per-contract serial N+1 as the
  run's wall-clock) — the discovery the skill is built for, confirmed on a real repo.
- 👍 **Persist-before-synthesis saved me.** The harness asynchronously kicked 2 of 12 backend lanes to
  the background (S1 data-access, S2 concurrency completed minutes after their batch-mates). Because
  every lane writes its own raw file immediately, staggered/out-of-order completion was a non-issue —
  I synthesized from files, not from return order. Strong design validation under a real,
  unpredictable harness.

### 5. The lanes & profile packs (the heart of it)
- 👍 **Reference-not-checklist held — lanes out-reasoned the packs.** Examples the pack lens did *not*
  hand them: the `concurrency` lane found the default connection-pool ceiling **and** correctly
  rejected the tempting count+data `gather` (dependent + shared session); the `cost-map` lane produced
  the highest-value architectural note of S1 (a Redis layer exists but the read path never calls it);
  `idiom-currency` found the double Pydantic validation via `response_model`. None of these is a pack
  bullet walked mechanically.
- 👍 **Anti-padding held under a deliberate stress test (S3).** Pointed at a latent SPA (`routes=[]`),
  the lanes did **not** manufacture render nits: the `memory` lane refused to call the root-singleton
  subscription a leak and explicitly warned against the naive `pure:false` "fix"; `payload-startup`
  returned "no critical/major, here's the posture"; `@angular/cdk` was grep-confirmed unimported and
  **not** charged to the bundle. This is the single best signal the calibration works.
- 🐞 **Version-index staleness is a real grounding gap (two instances).**
  - `version-indexes/javascript-typescript.md` is `covered_through` **Angular 19** ("zoneless GA in 21";
    `resource` marked Angular-19-experimental) — but the audited app is **Angular 20** with zoneless +
    signals already in production. The `idiom-currency` lane correctly dropped its `httpResource`/
    `rxResource` recommendation to **Heuristic + manual-check** rather than fabricating — 👍 the honesty
    rule worked — but the index needs an Angular-20 refresh (zoneless GA status, `httpResource`,
    `resource`/`linkedSignal` stabilization) to ground these as Strong. (Pointer: the JS/TS version index.)
  - `version-indexes/python.md` has **no** redis-py / httpx / APScheduler entries, so S2's idiom
    findings on those libs fell to **LOW/ungrounded** (e.g. `.close()`→`.aclose()`, httpx transport
    retries). Either add those libraries or state in the index that they're intentionally out of scope,
    so a lane knows LOW is expected, not a research failure. (Pointer: the Python version index +
    `currency-protocol.md` — there was no live brief to extend past the index this run.)
- 👍 **`cost-map` earned its keep.** It reframed S2 as "the network round-trip total is the run's time
  budget, and the serial per-contract fetch is the single term that scales" — a framing that made the
  #1 finding obvious, and it caught the no-cache and commit-on-read architecture notes in S1.
- 🟡 **No false-negative I can prove** — but worth noting the static-only run means index-scan and
  serialization wins are *argued*, not measured; a lane can't confirm a trigram index actually fires
  without a DB. Honest, but a ceiling on confidence the skill already acknowledges.

### 6. Synthesis & finding model (Phase 3)
- 👍 **Cross-lane agreement read as a true confidence signal, not noise.** P4/P5 (the fan-out cluster)
  were flagged by 4 lanes each through different framings; SP1 by 3. Collapsing them to one finding
  with an agreement count (and leading the report with the most-agreed) is exactly right and made
  ranking trivial.
- 👍 **Calibration + latent/dead-code handlingは the standout.** The whole-repo method's latent guidance
  ("reachability ≈ 0 today, fires once wired in") was the single most useful concept in the whole run —
  it's what let S3 be both *honest* (not a false "all clear") and *non-padding* (not auditing
  unreachable code as if hot). Without it I'd have either dropped the frontend or over-reported it.
- 👍 **bug-no-chase boundary held perfectly, including co-located bugs.** Every lane put correctness
  issues in a Suspected Bugs section and stopped. The co-located cases were handled exactly per
  `finding-model.md`: SB1 (short pages) sits in the same function as perf P5, SB-S2-2/3 in the same
  upsert as SP3 — recorded, noted as "the perf fix will touch this," **not** fixed.
- 👍 **Run metadata / `runs.jsonl` / fingerprints sane.** Symbol-based fingerprints (not line numbers)
  are stable; first-run regression = all-new; the ledger is trivially greppable. `plugin_version` came
  straight from `plugin.json` (0.2.0). `reasoning_effort: "default (harness exposes no knob)"` recorded
  honestly per the schema's instruction — 👍 the schema told me what to write instead of leaving a gap.

### 7. Cycle phases (`-cycle`)
- 👍 **Cross-validation (Phase 3 of the cycle) worked.** Because I'd read every source file during
  scoping, re-checking each finding against code was fast; I confirmed all and reclassified none as a
  false positive (only the *already-rejected* parallelization is recorded as an FP-avoided). Completeness
  check (every lane finding accounted as confirmed/design/FP/OOS) was enforceable from the lane files.
- 🐞 **The cycle has no autonomous / non-interactive operator mode — this was my single biggest
  improvisation.** Phase 5 ("present to user… MUST wait for the user's input on design decisions and
  opt-outs before Phase 6"), Phase 6 ("after user input… invoke `writing-plans-enhanced`"), and Phase 7
  (`plan-review-cycle`) **all assume a synchronous human in the loop.** My operator was offline and
  could not be prompted. I adapted by: capturing Phase 5 as written **`[DECISION]` blocks inside the
  remediation plan**, marking the plan **DRAFT — awaiting sign-off**, and **not** running Phase 7's
  plan-review or executing anything (the design decisions gate it). **💡 The cycle should document an
  explicit non-interactive fallback** ("if no user is available: emit the design decisions as a written
  decision artifact, produce the plan as DRAFT pending sign-off, do not auto-execute, defer
  plan-review"). This is a first-class use case for CI / overnight / autonomous runs and right now the
  runner has to invent the protocol. (Pointer: `performance-audit-cycle/SKILL.md` Phases 5–7.)
- 🟡 **Sibling-skill delegation has the same "can't invoke by name" issue as lane dispatch, but only the
  lane dispatch documents the fallback.** Phase 2 tells me what to do if the framework can't invoke
  `performance-audit` by name (read its SKILL.md). Phases 6–7 say "invoke `writing-plans-enhanced` /
  `plan-review-cycle`" with no equivalent fallback note for a runner whose subagents lack the registry.
  **💡 Add the same "or read its SKILL.md from the install path" note to the Phase 6/7 delegations.**
- 👍 **The whole-repo roll-up delivered on its premise.** It surfaced two themes invisible per-slice:
  the `contracts↔contract_items` one-to-many is mishandled on **both** the read (fan-out) and write
  (serial N+1) sides — same root, different slices — and the **frontend↔backend API contract drift**
  (the SPA reads `total_items`/sends `sort_order`; the backend returns `total`/expects `sort_direction`).
  Neither is visible in any single consolidated report. This is the highest-value artifact of the run,
  exactly as the method claims.
- 👍 **Cross-slice frequency calibration stayed clean** — no `frequency-unresolved — assume-hot`
  findings arose (read/write paths independent; the shared schema calibrated to the hotter read caller),
  so nothing shipped top-ranked on an unverified assumption. The fail-safe machinery wasn't needed here,
  but the *check* (is any hot symbol's frequency set by another slice?) was worth running.

### 8. Artifacts & ergonomics
- 👍 **`docs/perf-audits/` + `runs.jsonl` + `cache/` created cleanly; resumable.** The progress ledger +
  decision log made the run genuinely restartable after a context reset (which the ephemeral container
  threatened) — I committed+pushed after every slice and the ledger always pointed at the next
  non-DONE slice. Commit cadence (per slice) was natural.
- 🟡 **Hard-coded `docs/perf-audits/` + `docs/plans/` vs this repo's `design/` + top-level `plans/`.**
  Minor but real friction: the skill assumes a `docs/`-rooted layout; this repo uses `design/` for
  reviews and a root `plans/`. I followed the skill's literal paths (to test it faithfully) and put my
  meta-artifacts under `design/reviews/…`, but a project with an established `docs/`-less convention
  has to either adopt the skill's or diverge. **💡 Make the artifact base path a parameter, or detect
  an existing `design/`/`docs/` convention.** (Pointer: SKILL Phase 8 `git add` paths + Artifacts.)
- 🐞 **Minor filename-template inconsistency.** `lane-prompts.md`'s shared preamble writes the lane
  output path as `docs/perf-audits/<date>-<slug>-<lane>.md` (no time), but the SKILL Artifacts +
  consolidated-format use `<date>T<HH-MM>-<slug>-<lane>.md` (with time). Harmless, but two spots
  disagree on the raw-lane filename. (Pointer: `lane-prompts.md` preamble vs `performance-audit/SKILL.md`
  Artifacts.)
- 👍 **Nothing errored on first run.** The "create the paths before dispatch" instruction (Phase 2) was
  necessary and sufficient — `runs.jsonl`/`cache/` didn't pre-exist and the skill told me to make them.

### 9. Authoring
- I did **not** extend the skill (only ran it). I *did* author ~13 audit artifacts under the reference
  discipline (self-contained finding titles; `P#`/`SP#`/`FP#` only as traceability suffixes; lane
  *slugs* not numbers in prose). 👍 **The finding format's mandatory descriptive-title field made this
  nearly automatic** — it's hard to write a non-self-contained finding when the template's first field
  is "self-contained title (what/where/why)." Good forcing function.

### 10. Top changes + verdict

**Top 3 changes I'd make to the skill (ranked):**
1. **Add a documented non-interactive / autonomous operator mode to `performance-audit-cycle`.** Phases
   5–7 assume a synchronous human; an offline/CI run has no protocol and the runner must improvise
   (write decisions as an artifact, mark the plan DRAFT, skip auto-execute + plan-review). This is the
   single biggest gap for autonomous use. *(SKILL Phases 5–7.)*
2. **Refresh the version indexes / state coverage explicitly.** The JS/TS index is a major behind
   (Angular 19 vs the audited Angular 20 zoneless+signals), and the Python index silently omits
   redis-py/httpx/APScheduler — both pushed real `idiom-currency` findings to LOW. The honesty rules
   handled it gracefully, but grounding is thin exactly where modern stacks live. *(version-indexes/.)*
3. **Ship a ready-to-run lane-dispatch assembler.** `lane-prompts.md` has the bodies; the
   preamble+body+packs+scope+output assembly is left fully manual (I hand-built it 18×). A fill-in
   template or a tiny emitter would cut the highest-volume runner boilerplate. *(SKILL Phase 2 +
   lane-prompts.md.)*

**Overall verdict (1 line):** **Yes — it found real, high-leverage, well-calibrated performance work**
(two hot paths each with a clear #1 — the serial ESI item-fetch N+1 and the missing read-path cache —
rooted in one shared one-to-many mishandling), discovered it **blind**, held anti-padding on latent
code, kept the bug/perf boundary clean, and the whole-repo roll-up surfaced cross-slice themes no
single slice showed; the main rough edge is the absence of an autonomous-operator mode for the cycle's
human-in-the-loop phases.

---

## Minimal quick version
```
Context: Hangar Bay (FastAPI + Angular 20), ~2.5k prod LOC, 2 ecosystems; Claude Code remote, Agent-tool
  subagents (opus, no effort knob); whole-repo via scoping method → 3 slices; static-only; blind lanes.
👍 What worked: blind lanes DISCOVERED the hot-path maps (not just confirmed); anti-padding held on the
  latent frontend (refused a leak FP + a pure:false trap, no manufactured nits); persist-before-synthesis
  made async/staggered lane completion a non-issue; the whole-repo roll-up surfaced real cross-slice
  themes (one-to-many mishandled on both read+write; FE/BE contract drift); resumable ledger + per-slice
  commits survived the ephemeral container.
🟡 Friction / improvised: hand-assembled every lane-dispatch prompt (18×); followed the skill's docs/ paths
  vs the repo's design/+plans/ convention; ran lanes blind+parallel via the Agent tool myself.
🐞 Defects: cycle Phases 5–7 assume a synchronous human — no autonomous-operator fallback (I improvised
  written [DECISION] blocks + a DRAFT plan); version indexes stale/incomplete (JS-TS at Angular 19 vs the
  app's 20; Python index lacks redis-py/httpx/APScheduler) → idiom findings dropped to LOW; minor raw-lane
  filename-template mismatch (lane-prompts vs SKILL Artifacts).
💡 Top 3: (1) document a non-interactive/CI mode for the cycle; (2) refresh/version the indexes & state
  coverage; (3) ship a lane-dispatch assembler/template.
Verdict: Yes — real, well-calibrated, high-leverage perf work, discovered blind, with clean
  bug/perf separation and a genuinely useful cross-slice roll-up.
```
