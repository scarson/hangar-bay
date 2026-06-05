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

*(Areas 4–10 filled as slices execute, below.)*
