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
- 📌 **Correction (added after the operator asked specifically about the packs):** this area originally
  leaned on "lanes out-reasoned the packs" and under-credited the **profile packs themselves**. On
  re-reading the packs against the findings, they were the run's **strongest grounded input** — ~60% of
  non-trivial findings trace to a specific pack bullet (exact pool defaults, the 65 535 param ceiling,
  the HOT-update mechanism, `httpx.Limits`, sync-logging-on-loop, pure-vs-impure pipe). See the
  dedicated **"Did the framework profile packs actually help?"** section below for the
  finding→pack-bullet evidence mapping.

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

## Brutally honest: what did the skill add over a naïve "Claude, do a perf audit of this repo" prompt?

The operator asked for this directly, so here it is without hedging — including the parts that don't
flatter the skill. The honest control to compare against is a *moderate-quality* single prompt:
"Claude, do a performance audit of this repo and write up the findings" given to the same model with
no skill. I'll separate **did it find better problems** from **did it produce a better process**,
because they are not the same thing and conflating them is how skills oversell themselves.

### Where the skill genuinely added analytical value (not just paperwork)
1. **It defeated early-stopping / anchoring.** The single biggest real win. A naïve perf prompt on this
   repo reliably finds the 2–4 loudest things — the serial ESI N+1, the missing read cache, maybe the
   fan-out join — and then *stops*, because they feel like "the answer." The independent-lane structure
   forced coverage of dimensions a single pass skips: the **memory** lane's whole-run accumulation /
   peak-RSS analysis, the **idiom-currency** lane's double-`response_model` validation and the
   `sqlalchemy.future` shim, the **payload** lane's eager `@angular/localize` polyfill. None of those
   is "obvious"; all are real; a naïve pass would have missed most of them. The lanes are, in effect, a
   structural cure for "I found three things, I'm done."
2. **Calibration kept the latent frontend honest — both directions.** This is where a naïve prompt most
   reliably fails. Pointed at the Angular SPA, a default audit does one of two bad things: ignores it
   ("looks fine") or pads it with `trackBy`/`OnPush`/`unsubscribe` boilerplate nits that don't apply
   (it's zoneless + signals + a root singleton). The finding model's `Impact = reachability × frequency
   × cost` plus the explicit "what is NOT a finding" produced the *correct* answer — "this is latent,
   here's what bites once wired, and no, that subscription is not a leak." A naïve prompt almost never
   reasons explicitly about reachability, and it would not have produced the anti-padding restraint.
3. **The bug/perf boundary produced a cleaner deliverable.** Left to its own devices, a naïve audit
   conflates correctness and performance — it would have started *fixing* or deep-diving the
   `drop_all`-on-startup or the `record_id` PK collision mid-audit, muddying the perf report. "Record
   bugs, hand them off, don't chase" is a discipline a naïve prompt does not impose on itself, and it's
   why the perf reports stayed focused and the 23 bugs came out as a clean separate track.
4. **The cross-slice root-cause synthesis is a real emergent.** The roll-up's "the `contracts↔items`
   one-to-many is mishandled on *both* the read (fan-out) and write (serial N+1) sides — same root" is
   something a single linear pass is unlikely to *state*, because it sees the N+1 and the fan-out as two
   separate findings in two parts of the code. Forcing separate slices and then synthesizing surfaced a
   connection that improves the *fix* (one design change, not two patches). Modest, but real, and the
   kind of thing that's worth the ceremony.
5. **Ensemble agreement is a genuine epistemic gain.** "P4/P5 flagged by 4 independent blind lanes"
   is a stronger confidence signal than one model asserting it once. A naïve prompt gives you a single
   sample with a single set of blind spots; the lanes are independent samples. That's real, not theater.
6. **Structured, regression-ready output.** Fingerprints + `runs.jsonl` + per-task verification gates +
   a resumable ledger are things a naïve prompt simply does not produce — it gives you a chat message or
   one markdown blob. For a *recurring* audit this is substantial; for a one-shot it's partly wasted.

### Where it added little, or where the cost outweighs it — the honest debits
1. **On a repo this small, the headline findings were within reach of one careful pass.** This is the
   most important admission. Hangar Bay is ~2.5k production LOC — a single strong model can hold the
   whole thing in context and read it carefully. The serial ESI N+1, the missing cache, the
   leading-wildcard `ILIKE`, the missing indexes, the fan-out, `drop_all`-on-startup — a moderate
   "do a perf audit" prompt **finds most of these.** My honest estimate: a good naïve pass recovers
   ~70–80% of the *critical/major* findings here. The skill's marginal yield on the **top severity band
   was real but not dramatic**; its marginal yield was largest in the **long tail, the calibration, and
   the synthesis** — not in "found a critical nobody would have."
2. **The compute/complexity cost is enormous and only justified at scale.** This run was ~18 Opus
   subagents + a multi-phase orchestration — call it 15–20× the tokens and far more wall-clock and
   moving parts than one prompt. The skill is explicitly distilled from a ~96k-LOC app, and *that's*
   where the math works: at that size a single pass genuinely cannot hold the repo and *will* miss
   whole subsystems, so the slicing + lanes pay for themselves. On a 2.5k-LOC repo, a large fraction of
   the machinery is ceremony relative to the marginal findings. **The skill is sized for repos where a
   single pass structurally fails; this repo is near the floor of where it's worth it.**
3. **"Blind independent lanes" is partly attenuated by a single runner.** I chose every lane's scope,
   load context, and file list, and I synthesized and cross-validated using *my own* prior reading of
   the code. The lanes are genuinely independent at the dimension level, but the framing, the scope, and
   the final judgement are a single point — the same single-perspective limitation a naïve prompt has,
   now with a more authoritative-looking wrapper. The independence is real but smaller than the artifact
   count implies.
4. **Most of the added rigor is *process* rigor, not *analytical* rigor — and that's a trap.** The
   decision log, the three review rounds, the ledger, the fingerprints make the work **legible,
   auditable, and resumable** — genuinely valuable for trust and for recurring use. But they do not, by
   themselves, make the *findings* more correct. A skeptical reader should not mistake the volume and
   structure of the paper trail for analytical certainty. Which leads to the real risk:
5. **The biggest risk the skill introduces: manufactured authority around still-unverified claims.**
   Every finding here is a **static argument** — nothing was measured (no PG/Valkey/ESI/dataset; dynamic
   deferred). A naïve prompt produces obviously-provisional prose; this skill wraps the *same*
   static reasoning in severities, fingerprints, verification gates, a regression ledger, and a
   remediation plan. That presentation is more useful **and** more dangerous — it can make a Heuristic
   look Measured. To its credit the skill is *unusually disciplined* about this (Confidence levels, the
   `Measured|Strong-static|Heuristic` ladder, "dynamic deferred, no fabricated numbers," LOW-confidence
   tags on the ungrounded idiom findings) — which is exactly the guard-rail that keeps the authority
   honest. But the failure mode is latent in the format, and a less careful runner could ship
   confident-looking static guesses. The naïve prompt is less impressive and, in that one narrow sense,
   less able to mislead.
6. **Neither approach substitutes for tooling.** The findings that *most* want confirmation —
   `EXPLAIN ANALYZE`, a flame graph, a bundle analyzer — were produced by neither the skill nor a naïve
   prompt; both are static reasoners. The skill's advantage is that it *names the measurement to run*
   (verification gates) instead of implying it already knows. That's a real but modest edge.

### Net, brutally honest
On **this** repo, a moderate "do a perf audit" prompt would have gotten you **most of the top findings**
and a readable writeup, cheaply. The skill earned its keep in four specific places — **the long tail
(memory/idiom/payload dimensions a single pass skips), the calibration of latent/low-value code, the
cross-slice root-cause synthesis, and the reproducible bug/perf-separated artifact set** — at a large
compute and complexity premium. That premium is **marginal-to-unjustified on a 2.5k-LOC one-shot** and
**clearly justified on a large or recurring codebase**, which is what the skill is actually built for.
The thing to guard against is the skill's own polish: it makes static reasoning *look* like measurement,
and only its (genuinely good) Confidence/verification discipline keeps that honest. If I had to reduce
it to one line: **the skill didn't find dramatically better problems than a good naïve prompt would on a
repo this size — it found more of the boring-but-real ones, refused to pad, connected them across the
codebase, and wrote it all down so it's trustworthy and repeatable. That's worth a lot at scale and
overkill in the small, and the value is in the discipline, not in any single finding.**

---

## Did the framework profile packs actually help? (evidence-based — and a correction)

The operator pushed on this specifically, and re-reading the packs against the findings, **I
under-credited them in area 5 above.** Honest correction: **the profile packs were the single most
useful grounded input in the run — materially more useful than the version-indexes** (which were stale,
see area 5). Here is the evidence rather than an impression: a finding → exact-pack-bullet mapping. I
read the packs the lanes used (`python/orm-database.md`, `sql/postgres.md`, `python/async-asyncio.md`,
`javascript-typescript/angular.md`) and traced each non-obvious finding back to whether a pack bullet
named it.

### Findings the packs directly prompted or sharpened

| Finding | Pack bullet that names it | What the pack added |
|---|---|---|
| **S1 P7** pool defaults cap concurrency | `orm-database` "Connection pool sizing left at defaults" — *names `pool_size=5, max_overflow=10, pool_timeout=30` and "beyond 15 … blocks or times out"* | the **exact numbers** (5/10/15) the lane reported, verbatim from the pack |
| **S1 P3/P4/P6** unindexed cols / DISTINCT-count / sort node | `orm-database` "Query shape and index coverage hidden by the ORM" — *"filtering/sorting on unindexed columns, COUNT(*) … DISTINCT or multi-column ORDER BY forcing a sort node"* | a near-verbatim list of the three S1 index findings |
| **S2 SP7** item batch 50 vs param ceiling | `orm-database` "Bulk write batching depth" — *"PostgreSQL: ~65 535 … `insertmanyvalues_page_size` default 1000"* | the **65 535 param ceiling** the lane used to argue 50 is far too small |
| **S2 SP3** ON CONFLICT rewrites all cols → write amplification | `sql/postgres` "MVCC bloat" + *"HOT avoids writing new index entries when no indexed column changes"* | the **HOT-update mechanism** — a Postgres-distinctive reason a generic pass rarely names |
| **S1 P11** `Numeric` arithmetic cost | `sql/postgres` *"`numeric` … significantly slower than `bigint` or `double precision` for arithmetic-heavy queries"* | a MINOR a naïve prompt almost never surfaces; the pack prompted it |
| **S2 SP4** httpx default pool limits | `async-asyncio` "Client/session created per request" — *"for httpx use `Limits(max_connections=…, max_keepalive_connections=…)`"* | the exact `httpx.Limits` API the fix recommends |
| **S2 SP1/SP5/SP6** serial awaits over independent items | `async-asyncio` "Per-task scheduling…" — *"`await coro()` inside a loop over independent items … sequential await serialises work that could overlap"* + "Unbounded concurrent fan-out" | named the pattern **and** the bounded-semaphore safety |
| **S1 P8** sync logging parks the event loop | `async-asyncio` "Hidden blocking that parks the loop" — *"`logging` to a blocking file handler … symptom is event-loop latency that does not improve as concurrency rises"* | a **subtle** finding a naïve pass likely misses; the lane explicitly cited this bullet |
| **S2 SP2/SP8** whole-run buffering vs streaming | `async-asyncio` "Async generators … buffered into memory" — *"`await resp.read()` … materialises the full payload … back-pressure via bounded Queue rather than collecting into a list"* | the generator/stream refactor direction |
| **S3 FP6/FP10** pure-vs-impure pipe (don't go impure) | `angular` "Template expression cost — … impure pipes run every CD cycle … a `pure` pipe (called only when the input reference changes)" | the exact nuance the memory lane used to **warn against** `pure:false` |
| **S3 FP10** virtual scroll for long lists | `angular` "Long lists (hundreds of items) need CDK virtual scroll regardless of tracking strategy" | named CDK virtual scroll (already a dep) |
| **S3 FP8** no lazy-loading convention | `angular` "Large eager feature modules — `@defer` and lazy routes … `loadComponent`/`loadChildren`" | the lazy-route convention to set |

That is **12 of the ~20 confirmed non-trivial findings traceable to a specific pack bullet** — not
vague topical overlap, but the exact number, API, or mechanism the finding rests on.

### The packs also *prevented* bad output (the under-appreciated half)
- 👍 **They encoded the safety that stopped a false fix.** `async-asyncio`'s "unbounded `gather` opens
  one connection per item → bound with a `Semaphore`" is *why* the concurrency lane recommended a
  **capped** ESI fan-out instead of a naïve `gather` (which would trip ESI rate limits — a regression).
  The pack carried the guard-rail; without it the "obvious" fix is the dangerous one.
- 👍 **Reference-not-checklist worked in the hard direction too.** `angular`'s "unsubscribed
  `subscribe()` leaks" is a checklist item the memory lane **declined to apply** — it judged the
  root-singleton subscription a non-leak. The pack offered the prior; the lane's judgment overrode it.
  The calibration lives in the lane, but the pack gave it the right thing to reason *about*.

### The honest debits on the packs
- 🟡 **Mechanism-naming, not pure discovery, for the loud findings.** For P3/P4/P6 and the serial-await
  N+1, a strong model likely finds the *shape* unprompted; the pack's real contribution there is
  **precision and mechanism** (exact defaults, the 65 535 ceiling, the HOT-update reason) — which is
  what turns "this looks slow" into a credible, actionable finding, but it's *sharpening*, not
  *discovery*. The genuine "pack surfaced something a naïve pass would miss" cases are narrower:
  **P8 (sync-logging-blocks-the-loop), SP3 (HOT-update write amplification), P11 (numeric arithmetic)**.
- 🟡 **One pack item went unused that merited a one-line check.** `async-asyncio` flags running
  FastAPI **without uvloop** on Linux as "throughput left on the table"; no lane confirmed whether the
  project's `uvicorn[standard]` actually selects uvloop (it almost certainly does — but it's an
  *unverified* non-finding the pack explicitly teed up). A small false-negative-adjacent gap.
- 🟡 **Context cost vs applicable bullets on a small repo.** Each pack is 10–16 KB and I loaded several
  per slice; on a 2.5k-LOC repo the lanes used ~3–4 bullets of each and correctly ignored the rest
  (PgBouncer, CTE fences, UUIDv4 fragmentation, `work_mem` spills, eager-task-factory, SSR hydration).
  Good that they didn't pad on the inapplicable ones — but the signal-to-context ratio per pack is
  modest in the small (fine at the scale the skill targets).
- 👍 **The packs were *more current than the version-indexes*.** The `angular` pack knew zoneless /
  signals / standalone / `@defer`; the JS-TS *version-index* lagged at Angular 19. Where the index was
  stale, the **pack carried the load** — which is a strong argument for the pack layer specifically.

### Verdict on the packs
**They earned their keep — and they're where the skill's framework-specific value actually lives**,
more than in the version-indexes. They directly grounded ~60% of the non-trivial findings (with the
exact numbers/APIs/mechanisms that make a finding credible), surfaced a few genuinely non-obvious ones
(sync-logging-on-loop, HOT-update amplification, numeric cost), and — importantly — encoded the safety
that kept the concurrency fix from being a regression. The caveats are honest: for the *loud* findings
they sharpened rather than discovered, the per-pack context cost is high relative to applicable bullets
on a small repo, and one teed-up item (uvloop) went unverified. If the version-indexes are the skill's
weak grounding layer, **the profile packs are its strong one.**

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
