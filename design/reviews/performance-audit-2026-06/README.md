# Whole-Repo Performance Audit — 2026-06-05 (index)

Run of the **`superpowers-plus/performance-audit-cycle`** skill (vendored from the attached
`agentskills.zip` into `.claude/agent-skills/`) against the entire Hangar Bay repo, executed
autonomously. This folder holds the **meta-artifacts about running the skill**; the skill-generated
audit reports live under [`docs/perf-audits/`](../../../docs/perf-audits/) and the remediation plan
under [`docs/plans/`](../../../docs/plans/).

## Start here
- **[Field feedback on the skill](90-skill-feedback.md)** — the deliverable the operator weighted as
  highly as the audit. Wins / friction / defects / top-3, per the skill's own `feedback-template.md`.
  Includes a brutally-honest marginal-value section (vs a naïve "do a perf audit" prompt) and an
  evidence-mapped assessment of the framework profile packs.
- **[Skill-value evaluation prompt](91-skill-value-eval-prompt.md)** — a portable, repo-agnostic prompt
  to hand *other* agents running this skill, so their skill-value assessments are structured the same
  way and become comparable data points on the same question.
- **[Whole-repo roll-up](../../../docs/perf-audits/2026-06-05-WHOLE-REPO-ROLLUP.md)** — cross-slice
  themes + heat map + the prioritized repo-wide fix list. The single highest-value audit artifact.
- **[Remediation plan (DRAFT)](../../../docs/plans/2026-06-05-whole-repo-perf-audit-remediation-plan.md)**
  — sequenced tasks with verification gates; **awaiting operator sign-off** on the flagged design decisions.
- **[Decision log](00-decision-log.md)** — every autonomous judgement call (incl. the 3 adversarial
  partition-review rounds the operator asked for).
- **[Slice plan](01-slice-plan.md)** · **[Progress ledger](02-progress-ledger.md)** (resumable).

## What was done
1. Installed **superpowers v5.1.0** from the official `claude-plugins-official` marketplace.
2. Vendored the zip's skills into [`.claude/agent-skills/`](../../../.claude/agent-skills/) (3 plugins,
   18 skills).
3. Ran the **performance-audit-cycle** for the whole repo: surveyed + partitioned into 3 reviewed
   slices, dispatched **18 blind parallel lane subagents**, synthesized + cross-validated each slice,
   rolled up cross-slice themes, drafted a remediation plan, and kept a running field-feedback log.

## Headline results

| Slice | Tier | Critical | Major | Minor | Suspected bugs |
|-------|------|:---:|:---:|:---:|:---:|
| S1 — backend read pipeline | FULL (hot) | 2 | 7 | 5 | 8 |
| S2 — backend ESI ingestion | FULL (hot) | 3 | 7 | 7 | 7 |
| S3 — frontend Angular SPA | REDUCED (latent) | 0 | 1 | 9 | 8 |

**The two repo-wide #1s:** (1) the scheduled ingestion fetches contract items **one HTTP request at a
time** — a serial network N+1 that can exceed the job's own 900 s interval (fix: bounded concurrency
capped to ESI's rate limit); (2) the read endpoint has **no cache-aside** despite a wired Valkey layer
and a spec mandate. Both trace to the same `contracts↔contract_items` one-to-many being handled naïvely
on read (fan-out join + DISTINCT) and write (serial fetch). The frontend is sound but **latent**
(`routes=[]`) — its slice was the anti-padding stress test, which the skill passed (honest non-findings,
no manufactured nits).

**Correctness (separate track):** 23 suspected bugs were *recorded, not fixed* (a perf audit hands bugs
to `bug-hunt-cycle`). Highest-severity: an unconditional `drop_all`/`create_all` on every startup;
dropped ESI item pages >1; a `record_id` PK collision; frontend↔backend response/param contract
mismatches. Per-slice bug-hunt kickoffs are under `docs/perf-audits/`.

## Artifact map (`docs/perf-audits/`)
Per slice: 5–6 raw `*-<lane>.md` lane reports · one `*-consolidated.md` (with run frontmatter) · one
`*-validated.md` (cross-validation dispositions) · one `*-bug-hunt-kickoff.md`. Plus `runs.jsonl`
(3 run records, the regression substrate) and `2026-06-05-WHOLE-REPO-ROLLUP.md`.

> Nothing in the application was modified — this was an audit. The only code added is the vendored
> skills bundle and these reports.
