<!-- ABOUTME: Decision log for the 2026-08-08 overnight session working the F008 post-completion -->
<!-- ABOUTME: follow-ups (handoff §2). Every consequential autonomous decision is recorded here for Sam's morning review. -->

# Overnight follow-ups decision log — 2026-08-08/09

Session context: Sam asked for autonomous overnight work continuing from
[`2026-08-08-f008-complete-release-pending-handoff.md`](../handoffs/2026-08-08-f008-complete-release-pending-handoff.md).
Scope taken: handoff §2 follow-up items 1 (nullable sorts), 2 (Criterion 1.8 count-lifting), and 5
(jsdom test-output noise). Explicitly NOT taken: the `dev` → `main` release (§1 — Sam's call), item 3
(accepted-not-fixed by design), item 4 (blocked on production credentials only Sam can provision, ENV-8).

Format per entry: **Background / Alternatives / Decision / Reversibility**, matching the F008 decision log.

---

## OD1 — This session runs on a different machine than every prior F008 session; provision from scratch

**Background.** The handoff directs work to the provisioned worktree
`.claude/worktrees/secret-scanning-validity-2eb72d` (backend `.venv`, `src/.env`, `node_modules`,
scratch DB). That worktree no longer exists (`git worktree list` shows only the main checkout and this
session's `pr-147-handoff-beaace`). Every prior-session path is macOS (`/Users/sam/Code/hangar-bay`);
this session is Windows (`C:\Users\Sam\Code\hangar-bay`). On this machine: `pdm` is not installed,
no Docker containers are running, and no `.env` exists in the main checkout or any worktree.

**Alternatives.** (a) Stop and escalate as BLOCKED — rejected: everything needed to provision is
derivable from `app/backend/.env.example`, `compose.dependencies.yml`, and the plan's environment
notes; blocking would waste the night on a mechanical setup task. (b) Provision this worktree from
scratch — chosen.

**Decision.** Provision `pr-147-handoff-beaace` in place: containers started from the MAIN checkout
(ENV-10 — containers created from a worktree die when the worktree is reclaimed), `pdm` installed
user-level, backend `.venv` via `pdm install`, frontend `node_modules` via `npm install`,
`app/backend/src/.env` reconstructed from `.env.example` with the compose-matching dev values,
`DB_RECREATE_ON_STARTUP` left unset (defaults False — non-destructive), SSO fields left empty.
Baseline both test suites green before touching any code, so pre-existing breakage on this machine
is distinguishable from breakage I introduce.

**Reversibility.** Fully — all state is dev-local (venv, node_modules, containers, .env); nothing
touches production or git history.

---

## OD2 — Stale PG16 Docker volume set aside in place rather than deleted

**Background.** This machine's `docker_postgres_data` volume held a Postgres **16** cluster; the
compose file pulls `postgres:18-alpine`, whose entrypoint refuses pre-18 data at the volume root
(the ENV-9 trap — the compose mount was already fixed for it, but this volume predates the fix).
The container could never become healthy. The volume's content is dev data that the project treats
as disposable by design (ENV-2: every dev boot drops/recreates/re-ingests; the authoritative dev DB
with real contracts is on the macOS machine).

**Alternatives.** (a) `pg_upgrade` 16→18 — rejected: needs both binaries, high ceremony for data
that is disposable by design. (b) Delete the volume — blocked by the session's permission
classifier, and unnecessarily destructive. (c) Move the PG16 cluster files into a `pg16-legacy/`
subdirectory inside the same volume so the PG18 entrypoint initializes fresh alongside — chosen.

**Decision.** Cloned the whole volume to `docker_postgres_data_pg16_backup` first (72 MB), then
moved the PG16 files to `pg16-legacy/` within `docker_postgres_data`. Postgres 18 initialized a
fresh cluster and reports healthy. Scratch DBs `hangar_bay_test_f008` and `hangar_bay_test` created.

**Reversibility.** Fully — the PG16 data exists twice (in-volume `pg16-legacy/` and the backup
volume). Sam can delete both copies whenever convenient:
`docker volume rm docker_postgres_data_pg16_backup` and, inside the live volume, `pg16-legacy/`.

---

## OD3 — Fix the volume/ship_name NULL placement (rather than deliberately keeping it), classify Routine

**Background.** Plan Discoveries: `volume` and `ship_name` are the only two nullable sorts outside
`NULLABLE_SORTS`, so a descending volume sort led with every volume-less contract and a descending
ship-name sort with every item-less one — inconsistent beside the three Task B8 sorts that place
NULL last. The deferral target ("decide in PR-C/D") shipped without deciding, making this the
handoff's "smallest real item".

**Alternatives.** (a) Deliberately keep NULL-first for these two — rejected: no reading of the
domain supports it (a missing volume is not a small cargo; an item-less contract has no ship name
to alphabetize), and the UI now offers all five sorts side by side, where the inconsistency reads
as a bug. (b) Extend `NULLABLE_SORTS` to cover both — chosen; it is the exact `nulls_last()`
treatment one rule over, and B8's tests already define the contract.

**Decision.** TDD: two new acceptance tests in `test_contract_filters.py` (region 99999972 claimed
per the plan's fixture-region protocol), watched RED against the pre-fix code (only the descending
assertions failed — PostgreSQL defaults to NULLS LAST ascending / NULLS FIRST descending, which is
why the bug only shows descending), then the two-line `NULLABLE_SORTS` extension, GREEN. The RED
run against unmodified production code is the TEST-12 mutation evidence.

**Merge classification: Routine.** The Discoveries entry itself called this
"`Review — data-integrity`-adjacent **only** in that it changes a live sort's plan". It changes no
schema, no API shape, no data path — only result ordering, to match the rule the feature already
established and tested. Per `docs/git-strategy.md` §Merge authority, agents merge Routine on green
CI; adversarial review still applied before merge.

**Reversibility.** Trivial — remove two enum members from the frozenset.

---
