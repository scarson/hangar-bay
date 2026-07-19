# Grafana Cloud Observability Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken local Prometheus+Grafana Docker stack with Grafana Cloud (org `scarson`): a single Grafana Alloy container ships backend metrics and JSON logs to the cloud stack, dashboards are committed JSON provisioned via the stack's HTTP API, and the local stack is torn down.

**Architecture:** Grafana Alloy (one container on `hb-monitoring-net`) scrapes the FastAPI `/metrics` endpoint on the host and `remote_write`s to Grafana Cloud hosted Prometheus; the backend gains an optional `LOG_FILE` JSON file sink that Alloy tails and pushes to Grafana Cloud Loki. Dashboards live in the repo as JSON and are provisioned with a small script using a stack service-account token. Cloud credentials live in 1Password (canonical) and a gitignored `grafana-cloud.env` (runtime); nothing secret is committed.

**Tech Stack:** Grafana Alloy v1.17.1 (Docker), Grafana Cloud (hosted Prometheus/Mimir + Loki + Grafana), `prometheus-fastapi-instrumentator` 8.0.2 (already wired), structlog (already wired), httpx + pydantic-settings (provision script), 1Password `op` CLI (secret storage).

---

## Living Document Contract

This plan is a living document. Every executing agent MUST update it as
execution progresses, not only at completion.

- **On phase claim:** the executor MUST flip the banner to 🚧 IN PROGRESS
  with a claim timestamp (ISO 8601 UTC) and the active branch name. The
  banner MUST NOT include an expected-completion estimate — agents cannot
  reliably estimate their own wall-clock, and a fabricated duration
  becomes a stale anchor that misleads future readers. Followers
  encountering a 🚧 banner determine liveness by observable signals (PR
  existence, recent branch commits), not by arithmetic on expected times.
  See Step 5's stale-claim reclaim protocol.
- **On phase ship:** the executor MUST update that phase's **Execution
  Status** banner with the shipped commit SHA(s) and date. If a PR is
  open, the PR number and URL MUST appear in the top-of-plan Execution
  Status table.
- **On phase defer:** the executor MUST update the banner with ⏸ status
  AND a prose description of the unblock condition + a link to the
  likely-unblocker artifact (plan page, task, or PR whose own Execution
  Status banner will signal completion). Prose + link is durable across
  paraphrases and scope edits; exact-string coordination between agents
  is not.
- **On PR merge:** the executor MUST record the merge SHA in the banner
  + the top-of-plan Execution Status table.
- **On deviation from the written plan** (scope edits, structural
  refactors, dropped tasks, reordered phases): the executor MUST
  inline-document the deviation in the affected task AND summarize it
  in the top-of-plan Execution Status as a "Deviations" subsection.
  Deviation state MUST NOT live only in PR notes or status reports.
- **On discovery** (pre-existing drift surfaced during execution, new
  bugs found, architectural issues noted): the executor MUST add a
  "Discoveries" subsection at the top of the plan with pointers to the
  files/lines affected. Follow-up dispatches read this subsection to
  avoid duplicate discovery work.

The plan SHOULD reflect reality at the end of every session that touches
it. Anything worth putting in a status report to the user is worth
putting in the plan.

Rationale: `/writing-plans-enhanced` Step 5. Writing at ship time is
cheap; reconstruction by downstream readers is expensive, compounds
across dispatches, and fails silently when state is split across PR
notes and commit messages.

---

## Execution Status

**Overall:** 5/6 phases shipped and verified end-to-end; Phase 5 (PR) in flight.

| Phase | Status | Ship SHA(s) | Notes |
|---|---|---|---|
| 0 — Grafana Cloud stack setup | ✅ Done | — (no repo files) | tokens in 1Password; see banner for endpoints/IDs |
| 1 — Backend `LOG_FILE` sink (TDD) | ✅ Shipped | `906fdd2` | 3 new tests; full suite 365 passed; lint green |
| 2 — Alloy service + config | ✅ Shipped + verified | `39a1ced` | Alloy ready; remote_write pushing; Loki 8.9KB sent / 0 dropped; `up{job="fastapi"}=1` in cloud |
| 3 — Dashboards as code | ✅ Shipped + verified | `15eaa3e`, `c884808` (DS regex) | provisioned idempotently; panels render live data |
| 4 — Teardown + docs sweep | ✅ Shipped | `c884808` | prometheus/+grafana/ dirs deleted; no local containers/volumes existed |
| 5 — Verification + PR | 🚧 In progress | — | — |

### Deviations

- **Phase 1 executed inline by the orchestrator, not a dispatched subagent** — the Agent-dispatch safety classifier was unavailable (outage) throughout; the parallelism rationale was moot with Phase 0 blocked. TDD sequence followed exactly (RED confirmed → GREEN → full suite).
- **Phases 2/3 file tasks committed before their cloud verification steps** (Tasks 2.4/3.4 pend Phase 0). Any verification finding becomes a follow-up commit before the PR.
- **Task 3.4 Step 3 rewritten**: `pdm run format` is repo-wide black on a non-black repo — ran once, churned 64 files, fully reverted (`git restore app/backend/src`); instruction now file-scoped.
- **Task 1.3 extended**: fixed BOTH `.env.example` DB URLs (dev + tests) — the dev `DATABASE_URL` example had the same uncopyable `user:password` creds and wrong db name (`hangar_bay_db` vs compose's `hangar_bay_dev`).

### Discoveries

- **Worktree env bootstrap already done (2026-07-18, orchestrating session):** `pdm install` completed in this worktree (67 packages), `src/.env` copied from the main checkout, and `DATABASE_URL_TESTS`/`CACHE_URL_TESTS` appended (derived from the real `DATABASE_URL`). Task 1.0 is effectively complete for this worktree.
- **`app/backend/.env.example` test-DB example is uncopyable:** its `DATABASE_URL_TESTS` uses `user:password`, but compose creates `hangar_bay_user`/`hangar_bay_password` (`docker/compose.dependencies.yml:36-37`). Fix folded into Task 1.3.
- **Main checkout's `src/.env` lacks `DATABASE_URL_TESTS`** despite conftest hard-requiring it — Sam's local runs presumably export it another way; worth a question later, not blocking.
- **Claude-in-Chrome extension not connected on this machine (2026-07-18)** — Phase 0 is blocked until Sam either logs into grafana.com in the app Browser pane or connects the extension.
- **Port 5432 has an ssh listener (`ssh` PID 64957 binding `*:5432`)**, yet connections from the host reach the compose Postgres — verified by matching `pg_control_system()` system identifiers (container vs `localhost:5432`: both `7661406024165437474`). The main checkout's `src/.env` uses `user:password@localhost/hangar_bay_db`, which matches NEITHER the compose container nor anything reachable now — probably a relic of whatever that tunnel once pointed at. Worktree `src/.env` fixed to compose creds; suite then 365-green. Ask Sam about the tunnel.
- **Main checkout's `src/.env` contains a real `ESI_CLIENT_SECRET`** (fine in a gitignored file, but it surfaced during debugging reads this session — Sam may want to rotate it on the EVE dev portal out of caution).
- **`pdm run format` (= `black .`) is unsafe on this repo** — see Deviations; candidate for a pitfalls entry (ENV-7) in the PR.

---

## Context for a zero-context engineer

**What exists today** (all paths relative to repo root):

- `app/backend/docker/compose.observability.yml` — defines `prometheus` (`prom/prometheus:v3.4.2`, port 9090) and `grafana` (`grafana/grafana:12.0.2`, port 3000) on network `hb-monitoring-net`. Named volumes `prometheus_data`, `grafana_data`.
- `app/backend/docker/prometheus/prometheus.yml` — scrapes `host.docker.internal:8000` (job `fastapi-app`, 5s) + self-scrape.
- `app/backend/docker/grafana/provisioning/` — one Prometheus datasource + a dashboard provider pointing at a directory that contains **zero dashboards**. Local Grafana boots empty; there is nothing to migrate.
- `app/backend/src/fastapi_app/main.py:139-150` — `prometheus-fastapi-instrumentator` exposes default HTTP metrics at `/metrics` (`http_requests_total`, `http_request_duration_seconds_*`, sizes, and the renamed gauge `hangar_bay_requests_inprogress`). Labels: `method`, `handler`, `status`.
- `app/backend/src/fastapi_app/core/logging.py` — structlog JSON logging to **stdout only** (`setup_logging`), per-request `request_id` contextvar, `log_key_event` helper.
- `app/backend/src/fastapi_app/core/config.py` — the single `Settings` class; `model_config` has `extra="ignore"` (ENV-4). `.env` lives at `app/backend/src/.env`; the committed example is `app/backend/.env.example`.
- Dev reality: the backend runs **on the host** (`pdm run dev`, port 8000), not in a container. Containers must reach it via `host.docker.internal`.

**Decisions locked in** (do not relitigate during execution):

- One Alloy container replaces both local services. No local Prometheus, no local Grafana, no Docker log driver plumbing.
- Metrics scrape interval is **60s** — Grafana Cloud billing counts data-points-per-minute; 1 DPM/series is the included rate, so 60s is the intended default ([DPM doc](https://grafana.com/docs/grafana-cloud/account-management/billing-and-usage/active-series-and-dpm/)).
- Log shipping via a **file sink** (`LOG_FILE` setting) tailed by Alloy — NOT by containerizing the backend or capturing stdout. The backend is a host process in dev; a tailed file is the cheapest correct seam.
- Alloy stamps log entries at read time (no `loki.process` timestamp stage) — sidesteps Loki's 1-hour out-of-order window entirely. `tail_from_end = true` skips pre-existing file content on first start.
- `local.file_match` + `loki.source.file` (classic idiom), not the new built-in `file_match` block — conservative choice, works on any recent Alloy.
- Dashboard provisioning via `POST /api/dashboards/db` with a stack service-account token. This API is "legacy" as of Grafana 13 but explicitly "fully accessible and operative" ([legacy API note](https://grafana.com/docs/grafana/latest/developer-resources/api-reference/http-api/api-legacy/)); the k8s-style `/apis` route, Terraform, and the grafanactl→gcx CLI churn are all overkill for a few committed JSONs.
- Secrets: canonical copy in 1Password (via `op` CLI, per Sam's instruction), runtime copy in gitignored `app/backend/docker/grafana-cloud.env`. Never in compose files, CLI flags, or committed files.
- **Out of scope** (deferred spec items, unchanged): OpenTelemetry tracing, frontend telemetry (Faro/web-vitals), Sentry-style error tracking, readiness/freshness endpoints and `/meta/status` integration (observability-spec §2.5), alerting rules, custom app metrics like `esi_api_calls_total`.

**Verified external facts** (research 2026-07-18, sources in the research report):

- Alloy latest stable: **v1.17.1**. Config mounts at `/etc/alloy/config.alloy`; run args `run --server.http.listen-addr=0.0.0.0:12345 --storage.path=/var/lib/alloy/data /etc/alloy/config.alloy`; debug UI on :12345. Persist `/var/lib/alloy/data` (WAL + tail positions).
- Env substitution in Alloy configs: `sys.env("VAR")` (bare `env()` is deprecated).
- Grafana Cloud push endpoints: Prometheus `https://prometheus-<cluster>.grafana.net/api/prom/push`, Loki `https://logs-prod-<nnn>.grafana.net/loki/api/v1/push`. Basic-auth usernames are **numeric instance IDs, different for metrics vs logs**; the password for both is one Cloud Access Policy token with scopes `metrics:write` + `logs:write` (create under grafana.com portal → Security → Access Policies). Exact values are read off the stack's Prometheus/Loki "Details" cards in Phase 0.
- Dashboard API auth: stack Grafana → Administration → Users and access → Service accounts → create with **Editor** role → generate token (`glsa_...`), used as `Authorization: Bearer`.
- Free tier: 10k metric series / 50 GB logs / 14-day retention — orders of magnitude above this project's needs.

---

## File structure (end state)

```
app/backend/
  .env.example                          # + LOG_FILE entry (Task 1.3)
  docker/
    compose.yml                         # header comment: monitoring net now = FastAPI + Alloy (Task 4.2)
    compose.observability.yml           # REWRITTEN: single alloy service (Task 2.1)
    alloy/
      config.alloy                      # NEW: scrape → remote_write; file tail → loki.write (Task 2.2)
    grafana-cloud.env.example           # NEW: committed template, placeholder values (Task 2.3)
    grafana-cloud.env                   # NEW: gitignored, real values (Phase 0; never committed)
    prometheus/                         # DELETED (Task 4.1)
    grafana/                            # DELETED (Task 4.1)
  observability/
    dashboards/
      hangar-bay-backend.json           # NEW: RED dashboard + Loki key-events panel (Task 3.1)
    provision_dashboards.py             # NEW: POST each JSON to the stack (Task 3.2)
  src/fastapi_app/core/config.py        # + LOG_FILE field (Task 1.2)
  src/fastapi_app/core/logging.py       # + file handler when LOG_FILE set (Task 1.2)
  src/fastapi_app/tests/core/test_logging.py  # NEW (Task 1.1)
  pyproject.toml                        # + provision-dashboards pdm script (Task 3.3)
.gitignore                              # + app/backend/docker/grafana-cloud.env (Task 2.3)
design/fastapi/guides/02-observability-guide.md  # §2 updated (Task 4.3)
design/specifications/observability-spec.md      # local-stack mentions updated (Task 4.3)
CLAUDE.md / AGENTS.md                   # layout line + sibling sync (Task 4.4)
```

Cross-task file conflicts: none — each file is owned by exactly one task above.

---

## Phase 0 — Grafana Cloud stack setup (browser + op CLI; orchestrator-only)

**Execution Status:** ✅ DONE 2026-07-19 (no committed files). Sam logged in via the app Browser pane + clicked the instance-wake reCAPTCHA (agent-prohibited action). Collected: Prometheus push `prometheus-prod-67-prod-us-west-0.grafana.net/api/prom/push` (user 3030558), Loki push `logs-prod-021.grafana.net/loki/api/v1/push` (user 1510954), stack `scarson.grafana.net`. Created: access policy `hangar-bay-dev` (ID 872a3ca6, realm stack-scarson, metrics:write+logs:write) + token `hangar-bay-dev-alloy`; service account `sa-1-hangar-bay-provisioner` (Editor) + token. Both tokens stored in 1Password (Private vault: "Grafana Cloud hangar-bay-dev (Alloy)", "Grafana Cloud hangar-bay-provisioner (dashboards)") via `op --template` with template cleanup; runtime copies in gitignored `grafana-cloud.env` (verified `git check-ignore`).

> **NOT subagent-dispatchable.** This phase needs the orchestrator's browser access (Claude in Chrome, where Sam's grafana.com session/1Password live) and the `op` CLI. No repo files change except the gitignored `grafana-cloud.env`. Sam has granted standing permission for Grafana Cloud actions (2026-07-18 session).

- [ ] **Step 0.1: Sign in / open the org.** In Chrome, open `https://grafana.com/orgs/scarson`. If not already signed in, use the 1Password Agentic Autofill flow (`request_credentials` for grafana.com before navigating; never type credentials).
- [ ] **Step 0.2: Identify the stack.** On the org page, note the stack slug and its Grafana URL (`https://<stack>.grafana.net`). If the org has no stack yet, create one (free tier, default region).
- [ ] **Step 0.3: Collect push endpoints.** Stack page → Prometheus card → **Details/Send Metrics**: record the remote_write URL (`…/api/prom/push`) and numeric username. Same on the Loki card: push URL (`…/loki/api/v1/push`) and numeric username.
- [ ] **Step 0.4: Create the access policy + token.** Portal → Security → Access Policies → create `hangar-bay-dev` scoped to this stack with `metrics:write` + `logs:write` → Add token `hangar-bay-dev-alloy`, no expiry (dev). Copy the token once.
- [ ] **Step 0.5: Create the dashboard service account + token.** Stack Grafana (`https://<stack>.grafana.net`) → Administration → Users and access → Service accounts → `hangar-bay-provisioner`, role **Editor** → Add token `hangar-bay-provisioner-token`. Copy once.
- [ ] **Step 0.6: Store in 1Password.** Save both tokens plus endpoint metadata via the `op` CLI (per Sam's instruction). **Do NOT pass token values as command-line arguments** — argv is visible in `ps` and shell history (CLAUDE.md §Universal Gotchas). Write an item-template JSON to the session scratchpad, create from it, then delete it:

```bash
# scratchpad/gc-alloy-item.json (fill real values; delete after):
# {"title": "Grafana Cloud hangar-bay-dev (Alloy)", "category": "API_CREDENTIAL",
#  "fields": [
#    {"id": "credential", "type": "CONCEALED", "value": "<ACCESS_POLICY_TOKEN>"},
#    {"label": "prom username", "type": "STRING", "value": "<PROM_INSTANCE_ID>"},
#    {"label": "loki username", "type": "STRING", "value": "<LOKI_INSTANCE_ID>"},
#    {"label": "prom url", "type": "STRING", "value": "https://prometheus-<cluster>.grafana.net/api/prom/push"},
#    {"label": "loki url", "type": "STRING", "value": "https://logs-prod-<nnn>.grafana.net/loki/api/v1/push"},
#    {"id": "notesPlain", "type": "STRING", "value": "Access policy hangar-bay-dev, scopes metrics:write+logs:write. Created 2026-07-18 for Hangar Bay Alloy."}
#  ]}
SCRATCH=/private/tmp/claude-501/-Users-sam-Code-hangar-bay--claude-worktrees-grafana-cloud-migration-5a5464/1951c8bd-454f-42cc-b5e1-4b158201ca0d/scratchpad
op item create --template "$SCRATCH/gc-alloy-item.json"
# second template for the provisioner token ("Grafana Cloud hangar-bay-provisioner (dashboards)",
# credential=<SA_TOKEN>, hostname=<stack>.grafana.net, note: Editor SA token for pdm run provision-dashboards)
op item create --template "$SCRATCH/gc-provisioner-item.json"
rm "$SCRATCH"/gc-*.json
```

(That is this session's scratchpad path; a different session substitutes its own scratchpad directory — any non-repo temp dir works, the point is: template file, never argv, delete after.)

If the installed `op` version rejects `--template`, fall back to `op item create` reading the same JSON on **stdin** (`op item create - < file` on op v2) — never argv. If `op` errors with a missing/ambiguous vault, add `--vault Private` (or Sam's default vault name from `op vault list`).

- [ ] **Step 0.7: Write the runtime env file** at `app/backend/docker/grafana-cloud.env`. **First** make sure it is ignored: if `.gitignore` does not yet contain `app/backend/docker/grafana-cloud.env` (Task 2.3 adds it; this phase may run first), add that line NOW, before creating the file — verify with `git check-ignore app/backend/docker/grafana-cloud.env`. Task 2.3's gitignore step is then a no-op check. Never `git add` the real env file:

```bash
# app/backend/docker/grafana-cloud.env  (real values; NEVER commit)
GRAFANA_CLOUD_PROM_URL=https://prometheus-<cluster>.grafana.net/api/prom/push
GRAFANA_CLOUD_PROM_USERNAME=<numeric metrics instance ID>
GRAFANA_CLOUD_LOKI_URL=https://logs-prod-<nnn>.grafana.net/loki/api/v1/push
GRAFANA_CLOUD_LOKI_USERNAME=<numeric logs instance ID>
GRAFANA_CLOUD_TOKEN=<access policy token>
GRAFANA_STACK_URL=https://<stack>.grafana.net
GRAFANA_SA_TOKEN=<service account token>
```

- [ ] **Step 0.8: Update this plan's banner** (🚧 → ✅ with date; no commit SHA — this phase produces no committed files).

---

## Phase 1 — Backend `LOG_FILE` sink (TDD)

**Execution Status:** ✅ SHIPPED at `906fdd2` on 2026-07-19 (inline by orchestrator — see Deviations; RED→GREEN verified, full suite 365 passed, lint green)

> BEFORE starting work:
> 1. Invoke /superpowers:test-driven-development
> 2. Read docs/pitfalls/testing-pitfalls.md
> Follow TDD: write failing test → implement → verify green.
>
> Pitfalls in play: **ENV-4** (new Settings field MUST also land in `app/backend/.env.example` in the same change), **ENV-2/ENV-3** (do NOT run `pdm run dev` for this phase — pytest only; the dev server wipes the DB on every reload), **TEST-2** (never weaken assertions to fix flakes). The backend pytest suite drops and recreates ONE shared database (`DATABASE_URL_TESTS`), so two concurrent suite runs corrupt each other with phantom IntegrityError/DROP TABLE failures — never run it while another agent/session is running it.

### Task 1.0: Bootstrap the worktree environment

> **Skip this task if the top-of-plan Discoveries subsection says it is already complete for your worktree** (it is, as of 2026-07-18, for `.claude/worktrees/grafana-cloud-migration-5a5464`). The steps are idempotent if re-run.

The worktree has no populated backend venv (verified 2026-07-18: `app/backend/.venv` absent here; the main checkout's `.venv` is an empty stub). All commands below run from the **repo root**.

- [ ] **Step 1:** `cd app/backend && pdm install` — expect a full dependency install into `.venv`. If pdm resolves to a central venv instead, that's fine; the `pdm run …` commands below work either way.
- [ ] **Step 2:** Dev env file: if `app/backend/src/.env` is missing in this worktree, copy the main checkout's `app/backend/src/.env` (real working values). The test suite additionally needs `DATABASE_URL_TESTS` — verified 2026-07-18: the main checkout's `src/.env` does NOT contain it, and `.env.example`'s example line uses `user:password` credentials that do NOT match the compose Postgres. Derive it from the file's own `DATABASE_URL` by replacing the database name with `hangar_bay_test` (keeping the real `hangar_bay_user:hangar_bay_password@localhost` credentials), and add `CACHE_URL_TESTS="redis://localhost:6379/1"`.
- [ ] **Step 3:** Confirm the test DB dependencies are up (repo root, same path style as every other compose command in this plan): `docker compose -f app/backend/docker/compose.yml -f app/backend/docker/compose.dependencies.yml up -d --wait postgres_db valkey_cache`

### Task 1.1: Failing tests for the file sink

**Files:**
- Test: `app/backend/src/fastapi_app/tests/core/test_logging.py` (new)

- [ ] **Step 1: Write the failing tests** (run from `app/backend/`):

```python
# ABOUTME: Tests for core/logging.py setup_logging — LOG_FILE file-sink behavior.
# ABOUTME: Verifies the sink is off by default and writes JSON lines when configured.
import json
import logging

import pytest
import structlog

from fastapi_app.core.config import Settings
from fastapi_app.core.logging import setup_logging


def _make_settings(**overrides):
    return Settings(
        ESI_USER_AGENT="pytest",
        DATABASE_URL="postgresql+asyncpg://unused:unused@localhost/unused",
        CACHE_URL="redis://localhost:6379/0",
        _env_file=None,
        **overrides,
    )


@pytest.fixture
def restore_logging():
    """setup_logging mutates process-global state; snapshot and restore ALL of it.

    The suite normally runs on structlog's DEFAULT config — conftest never calls
    setup_logging (it only runs inside main.py's lifespan, which ASGITransport
    bypasses; see testing-pitfalls TEST-10). test_observability.py depends on
    that default (its human-readable log parser). So this fixture must restore
    BOTH the root logger's handlers/level AND structlog's exact prior config,
    or every test collected after this file runs under a leaked JSON config.
    """
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    saved_structlog_config = structlog.get_config()
    yield
    for h in root.handlers:
        if h not in saved_handlers:
            h.close()
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)
    structlog.configure(**saved_structlog_config)


def test_log_file_defaults_to_disabled(restore_logging, tmp_path, monkeypatch):
    monkeypatch.delenv("LOG_FILE", raising=False)  # _env_file=None still reads OS env
    monkeypatch.chdir(tmp_path)  # any accidental relative file would land here
    setup_logging(_make_settings())
    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert not isinstance(root.handlers[0], logging.FileHandler)
    assert list(tmp_path.iterdir()) == []


def test_log_file_writes_json_lines(restore_logging, tmp_path, monkeypatch):
    monkeypatch.delenv("LOG_FILE", raising=False)
    log_path = tmp_path / "nested" / "backend.jsonl"
    setup_logging(_make_settings(LOG_FILE=str(log_path)))

    structlog.get_logger("test.sink").info("file_sink_smoke", marker="abc123")

    assert log_path.exists()  # parent dir auto-created
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    # Only structlog lines are JSON; a stray stdlib record (none expected here,
    # but possible from imported libraries) must not turn the test into a
    # JSONDecodeError instead of an assertion failure.
    payloads = [json.loads(line) for line in lines if line.startswith("{")]
    matching = [p for p in payloads if p.get("event") == "file_sink_smoke"]
    assert len(matching) == 1
    assert matching[0]["marker"] == "abc123"
    assert matching[0]["level"] == "info"


def test_log_file_and_stdout_both_attached(restore_logging, tmp_path, monkeypatch):
    monkeypatch.delenv("LOG_FILE", raising=False)
    setup_logging(_make_settings(LOG_FILE=str(tmp_path / "backend.jsonl")))
    root = logging.getLogger()
    kinds = [type(h) for h in root.handlers]
    assert kinds.count(logging.FileHandler) == 1
    # StreamHandler is FileHandler's base class; count exact stdout handler separately
    assert sum(1 for h in root.handlers if type(h) is logging.StreamHandler) == 1
```

- [ ] **Step 2: Run to verify they fail correctly**

Run: `cd app/backend && pdm run pytest src/fastapi_app/tests/core/test_logging.py -v`
Expected: `test_log_file_defaults_to_disabled` may already pass (current behavior); the other two FAIL — `test_log_file_writes_json_lines` with a Pydantic `ValidationError`-free failure: `LOG_FILE` is currently an **unknown** kwarg silently ignored (`extra="ignore"` applies to env sources, but direct kwargs to a model with extra="ignore" are dropped), so no `FileHandler` is attached and `log_path.exists()` is False. Confirm the failure is the assertion, not a collection error.

### Task 1.2: Implement the sink

**Files:**
- Modify: `app/backend/src/fastapi_app/core/config.py` (after the `LOG_LEVEL` line)
- Modify: `app/backend/src/fastapi_app/core/logging.py` (`setup_logging`)

- [ ] **Step 1: Add the setting** in `config.py` directly below `LOG_LEVEL: str = "INFO"`:

```python
    # When set, JSON logs are ALSO written to this file (one JSON object per line),
    # for shipping to Grafana Cloud Loki via the Alloy tailer (docker/alloy/config.alloy).
    LOG_FILE: str = ""
```

- [ ] **Step 2: Add the handler** in `logging.py`. Add `from pathlib import Path` to the imports, then in `setup_logging`, after the existing `root_logger.addHandler(handler)` and before the log-level block:

```python
    # Optional file sink for log shipping (Alloy tails this file into Loki).
    if settings.LOG_FILE:
        log_path = Path(settings.LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
```

Do NOT add rotation, size caps, or async handlers — YAGNI for a dev sink; Loki retention is the durable store. An unwritable `LOG_FILE` path raising `OSError` at startup is the intended fail-fast behavior; do not wrap it in try/except, and do not write a test for it (it would assert stdlib behavior).

- [ ] **Step 3: Run the tests**

Run: `cd app/backend && pdm run pytest src/fastapi_app/tests/core/test_logging.py -v`
Expected: 3 passed, pristine output.

- [ ] **Step 4: Run the full backend suite** (serialize with any other agent — shared DB):

Run: `cd app/backend && pdm run pytest`
Expected: all green. Also run `pdm run lint`.

### Task 1.3: Document the setting (ENV-4)

**Files:**
- Modify: `app/backend/.env.example` (below the `LOG_LEVEL="INFO"` line, line 5)

- [ ] **Step 1: Add:**

```bash
# Optional: also write JSON logs to this file so Alloy can ship them to Grafana Cloud Loki.
# Dev convention: logs/backend.jsonl (relative to app/backend/, where `pdm run dev` runs;
# the Alloy container bind-mounts app/backend/logs). Leave empty to disable.
LOG_FILE="logs/backend.jsonl"
```

Also correct the file's `DATABASE_URL_TESTS` example line while here: it currently shows `postgresql+asyncpg://user:password@localhost:5432/hangar_bay_test`, but the compose Postgres (`docker/compose.dependencies.yml`) creates `hangar_bay_user`/`hangar_bay_password` — an example nobody can copy-paste successfully. Change it to `postgresql+asyncpg://hangar_bay_user:hangar_bay_password@localhost:5432/hangar_bay_test`. (In-scope fix: this file is already being edited, and the wrong example bit this plan's own bootstrap.)

- [ ] **Step 2: Set it in the real dev env** `app/backend/src/.env` (gitignored): add `LOG_FILE="logs/backend.jsonl"`. Note: `.gitignore` already ignores any `logs` directory (root pattern `logs`), so `app/backend/logs/` needs no new ignore entry — verify with `git check-ignore app/backend/logs/x`.

- [ ] **Step 3: Commit**

```bash
git add app/backend/src/fastapi_app/tests/core/test_logging.py \
        app/backend/src/fastapi_app/core/config.py \
        app/backend/src/fastapi_app/core/logging.py \
        app/backend/.env.example
git commit -m "feat(api): add optional LOG_FILE JSON sink for Loki shipping"
```

> BEFORE marking Phase 1 complete:
> 1. Review tests against docs/pitfalls/testing-pitfalls.md
> 2. Verify coverage: default-off path, file-written path, both-handlers path — all present above
> 3. Run tests and confirm green, output pristine
> If any assertion races or flakes, fix with deterministic synchronization, NOT by weakening the assertion (TEST-2).

---

## Phase 2 — Alloy service + config

**Execution Status:** ✅ FILES SHIPPED at `39a1ced` on 2026-07-19; ⏸ Task 2.4 verification DEFERRED pending Phase 0 (Grafana Cloud credentials — see the Phase 0 banner for the unblock condition)

> Pitfalls in play: **ENV-3** (verification below starts the dev server — batch ALL backend edits first, clear the Valkey lock, one clean cycle), universal **no-secrets-in-flags** (credentials only via env_file), **ORCH-1** n/a (no parallel dispatch in this phase).
> Dependency: Phase 0 must be complete (real `grafana-cloud.env` exists) before the **verification steps**; the file edits can proceed without it.

### Task 2.1: Rewrite `compose.observability.yml`

**Files:**
- Modify (full rewrite): `app/backend/docker/compose.observability.yml`

- [ ] **Step 1: Replace the file's entire contents with:**

```yaml
# Hangar Bay - Observability Collection
#
# A single Grafana Alloy container ships backend telemetry to Grafana Cloud
# (org: scarson):
#   - scrapes the FastAPI /metrics endpoint on the HOST (dev runs the backend
#     as a host process on :8000, so the scrape target is host.docker.internal)
#   - tails the backend's JSON log file (app/backend/logs/, written when
#     LOG_FILE is set) and pushes it to Grafana Cloud Loki
#
# Visualization and storage live in Grafana Cloud; there is no local
# Prometheus or Grafana. Dashboards are committed JSON under
# app/backend/observability/dashboards/, provisioned with
# `pdm run provision-dashboards`.
#
# --- NETWORK CONNECTIONS ---
# In line with the Zero Trust principle of Microsegmentation, Alloy is
# isolated on `hb-monitoring-net`: it has no path to the data tier. Its only
# egress is the host scrape target and Grafana Cloud.
#
# --- CREDENTIALS ---
# ./grafana-cloud.env (gitignored; template: ./grafana-cloud.env.example).
# Canonical copies live in 1Password ("Grafana Cloud hangar-bay-*" items).

services:
  alloy:
    image: grafana/alloy:v1.17.1
    container_name: alloy
    ports:
      - "12345:12345"   # Alloy debug UI
    volumes:
      - ./alloy/config.alloy:/etc/alloy/config.alloy:ro
      - alloy_data:/var/lib/alloy/data
      - ../logs:/var/log/hangar-bay:ro
    env_file:
      - ./grafana-cloud.env
    command:
      - run
      - --server.http.listen-addr=0.0.0.0:12345
      - --storage.path=/var/lib/alloy/data
      - /etc/alloy/config.alloy
    extra_hosts:
      - "host.docker.internal:host-gateway"
    restart: unless-stopped
    networks:
      - hb-monitoring-net

volumes:
  alloy_data: {}
```

Notes for the implementer: `alloy_data` persists the remote_write WAL and file-tail positions across restarts (without it, restarts re-tail and can re-push). `extra_hosts` makes `host.docker.internal` work on Linux too (the old Prometheus config lacked this). `../logs` resolves to `app/backend/logs/` because compose paths are relative to this file's directory. `env_file` is deliberately **required** (fail-fast): any `docker compose` invocation that includes this overlay errors clearly if `grafana-cloud.env` is missing, instead of running Alloy with empty credentials — Task 4.2 documents the copy-the-example step in the compose usage comment. The canonical deps-only command (CLAUDE.md) does not include this overlay, so Postgres/Valkey bring-up is unaffected.

### Task 2.2: Alloy config

**Files:**
- Create: `app/backend/docker/alloy/config.alloy`

- [ ] **Step 1: Create the file:**

```alloy
// ABOUTME: Alloy pipeline config — scrapes the FastAPI backend on the host and
// ABOUTME: ships metrics + JSON logs to Grafana Cloud (creds from grafana-cloud.env).

// ---- Metrics: scrape FastAPI /metrics -> Grafana Cloud hosted Prometheus ----

prometheus.scrape "fastapi" {
  targets = [
    {"__address__" = "host.docker.internal:8000", "job" = "fastapi"},
  ]
  // 60s = 1 data-point-per-minute per series, Grafana Cloud's included rate.
  scrape_interval = "60s"
  forward_to      = [prometheus.remote_write.grafana_cloud.receiver]
}

prometheus.remote_write "grafana_cloud" {
  endpoint {
    url = sys.env("GRAFANA_CLOUD_PROM_URL")

    basic_auth {
      username = sys.env("GRAFANA_CLOUD_PROM_USERNAME")
      password = sys.env("GRAFANA_CLOUD_TOKEN")
    }
  }

  external_labels = {"env" = "dev"}
}

// ---- Logs: tail the backend's JSON log file -> Grafana Cloud Loki ----
// Entries are stamped at read time (no timestamp parsing stage), which keeps
// every push inside Loki's out-of-order acceptance window by construction.

local.file_match "backend_logs" {
  path_targets = [{
    "__path__" = "/var/log/hangar-bay/*.jsonl",
    "job"      = "fastapi",
    "app"      = "hangar-bay",
    "env"      = "dev",
  }]
  sync_period = "10s"
}

loki.source.file "backend_logs" {
  targets       = local.file_match.backend_logs.targets
  forward_to    = [loki.write.grafana_cloud.receiver]
  tail_from_end = true
}

loki.write "grafana_cloud" {
  endpoint {
    url = sys.env("GRAFANA_CLOUD_LOKI_URL")

    basic_auth {
      username = sys.env("GRAFANA_CLOUD_LOKI_USERNAME")
      password = sys.env("GRAFANA_CLOUD_TOKEN")
    }
  }
}
```

### Task 2.3: Credential template + gitignore

**Files:**
- Create: `app/backend/docker/grafana-cloud.env.example`
- Modify: `.gitignore`

- [ ] **Step 1: Create the committed template:**

```bash
# ABOUTME: Template for app/backend/docker/grafana-cloud.env (gitignored — copy, then fill).
# ABOUTME: Values come from the Grafana Cloud portal; canonical copies live in 1Password.
# Portal: https://grafana.com/orgs/scarson -> stack -> Prometheus/Loki card -> Details.
GRAFANA_CLOUD_PROM_URL=https://prometheus-REPLACE-cluster.grafana.net/api/prom/push
GRAFANA_CLOUD_PROM_USERNAME=REPLACE-numeric-metrics-instance-id
GRAFANA_CLOUD_LOKI_URL=https://logs-prod-REPLACE.grafana.net/loki/api/v1/push
GRAFANA_CLOUD_LOKI_USERNAME=REPLACE-numeric-logs-instance-id
# Cloud Access Policy token, scopes metrics:write + logs:write
# (portal -> Security -> Access Policies -> hangar-bay-dev).
GRAFANA_CLOUD_TOKEN=REPLACE-access-policy-token
# Stack Grafana URL + service-account token (Editor role) for `pdm run provision-dashboards`.
GRAFANA_STACK_URL=https://REPLACE-stack.grafana.net
GRAFANA_SA_TOKEN=REPLACE-glsa-service-account-token
```

- [ ] **Step 2: Gitignore the real file** (skip if Phase 0 Step 0.7 already added it). In `.gitignore`, next to the existing `app/backend/.env` entry (line ~145), add:

```
app/backend/docker/grafana-cloud.env
```

Verify: `git check-ignore app/backend/docker/grafana-cloud.env` prints the path; `git status` shows the example file as untracked but NOT the real one.

- [ ] **Step 3: Commit**

```bash
git add app/backend/docker/compose.observability.yml app/backend/docker/alloy/config.alloy \
        app/backend/docker/grafana-cloud.env.example .gitignore
git commit -m "feat(api): replace local Prometheus+Grafana with Alloy shipping to Grafana Cloud"
```

### Task 2.4: Verify the pipeline end-to-end

> **Orchestrator-only** (needs the browser session for cloud-side verification). Precondition: Phase 0 done (`grafana-cloud.env` filled); Phase 1 landed on this branch (LOG_FILE active in `app/backend/src/.env`).

- [ ] **Step 1: One clean backend cycle (ENV-3).** All backend edits are done at this point. Start deps + clear the aggregation lock, then start the backend as a tracked background task with visible logs:

```bash
docker compose -f app/backend/docker/compose.yml -f app/backend/docker/compose.dependencies.yml up -d --wait postgres_db valkey_cache
docker exec hangar_bay_valkey valkey-cli DEL "hangar-bay:aggregation:lock"
cd app/backend && pdm run dev   # background task, watch logs; ingestion takes minutes (ENV-2)
```

- [ ] **Step 2: Start Alloy** (create the log dir first so the bind mount starts from a host-owned directory):

```bash
mkdir -p app/backend/logs
docker compose -f app/backend/docker/compose.yml -f app/backend/docker/compose.observability.yml up -d alloy
```

- [ ] **Step 3: Check Alloy health.** `curl -s localhost:12345/-/ready` → `Alloy is ready.`; the debug UI at `http://localhost:12345` shows all five components healthy; `docker logs alloy` free of auth errors (a 401 here means the Phase 0 token/username pairing is wrong).
- [ ] **Step 4: Confirm metrics in the cloud.** In the stack's Grafana → Explore → Prometheus datasource: query `up{job="fastapi"}` (expect `1`) and `sum(rate(http_requests_total[5m]))`. Allow one or two 60s scrape cycles. Also confirm the latency histogram name the dashboard assumes: query `http_request_duration_seconds_bucket` — the repo's tests only pin `http_requests_total`, and this name comes from the instrumentator's default metric. If it doesn't exist, check `/metrics` output for the actual `*_duration_*_bucket` name and update dashboard panel 3 (Task 3.1) to match BEFORE provisioning.
- [ ] **Step 5: Confirm logs in the cloud.** Generate traffic (`curl -s localhost:8000/contracts/ >/dev/null`), then Explore → Loki datasource: `{app="hangar-bay"}` returns JSON lines; `{app="hangar-bay"} |= "event_name"` shows key events (e.g. `contract_search_executed`).
- [ ] **Step 6: Record evidence** (screenshots / query outputs) for the PR body, and update this plan's banner.

---

## Phase 3 — Dashboards as code

**Execution Status:** ✅ FILES SHIPPED on 2026-07-19 (dashboard JSON validated, script flake8/black-clean file-scoped); ⏸ Task 3.4 provisioning + verification DEFERRED pending Phase 0 (see the Phase 0 banner)

> TDD note: `provision_dashboards.py` is a script, and dashboard JSON is config — both outside the repo's TDD scope (CLAUDE.md §TDD Scope). Verification is by running against the real stack (Task 3.4). Do NOT add a mocked-HTTP unit test for the script — it would test the mock (testing-pitfalls §7).

### Task 3.1: The dashboard JSON

**Files:**
- Create: `app/backend/observability/dashboards/hangar-bay-backend.json`

- [ ] **Step 1: Create the dashboard.** Complete JSON (uid `hangar-bay-backend`; datasource template variables so it binds to whatever the stack's default Prometheus/Loki datasources are named):

```json
{
  "id": null,
  "uid": "hangar-bay-backend",
  "title": "Hangar Bay — Backend (RED)",
  "tags": ["hangar-bay", "provisioned"],
  "timezone": "browser",
  "schemaVersion": 39,
  "editable": true,
  "time": {"from": "now-6h", "to": "now"},
  "refresh": "1m",
  "templating": {
    "list": [
      {"name": "DS_PROM", "type": "datasource", "query": "prometheus", "label": "Prometheus", "current": {}},
      {"name": "DS_LOKI", "type": "datasource", "query": "loki", "label": "Loki", "current": {}}
    ]
  },
  "panels": [
    {
      "id": 1,
      "type": "timeseries",
      "title": "Request rate by handler",
      "datasource": {"type": "prometheus", "uid": "${DS_PROM}"},
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
      "fieldConfig": {"defaults": {"unit": "reqps"}, "overrides": []},
      "targets": [
        {
          "refId": "A",
          "expr": "sum by (handler) (rate(http_requests_total[$__rate_interval]))",
          "legendFormat": "{{handler}}"
        }
      ]
    },
    {
      "id": 2,
      "type": "timeseries",
      "title": "Error rate (4xx / 5xx)",
      "datasource": {"type": "prometheus", "uid": "${DS_PROM}"},
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
      "fieldConfig": {"defaults": {"unit": "reqps"}, "overrides": []},
      "targets": [
        {
          "refId": "A",
          "expr": "sum(rate(http_requests_total{status=~\"5..\"}[$__rate_interval]))",
          "legendFormat": "5xx"
        },
        {
          "refId": "B",
          "expr": "sum(rate(http_requests_total{status=~\"4..\"}[$__rate_interval]))",
          "legendFormat": "4xx"
        }
      ]
    },
    {
      "id": 3,
      "type": "timeseries",
      "title": "Latency quantiles (all handlers)",
      "datasource": {"type": "prometheus", "uid": "${DS_PROM}"},
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
      "fieldConfig": {"defaults": {"unit": "s"}, "overrides": []},
      "targets": [
        {
          "refId": "A",
          "expr": "histogram_quantile(0.50, sum by (le) (rate(http_request_duration_seconds_bucket[$__rate_interval])))",
          "legendFormat": "p50"
        },
        {
          "refId": "B",
          "expr": "histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[$__rate_interval])))",
          "legendFormat": "p95"
        },
        {
          "refId": "C",
          "expr": "histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket[$__rate_interval])))",
          "legendFormat": "p99"
        }
      ]
    },
    {
      "id": 4,
      "type": "stat",
      "title": "Requests in progress",
      "datasource": {"type": "prometheus", "uid": "${DS_PROM}"},
      "gridPos": {"h": 8, "w": 6, "x": 12, "y": 8},
      "targets": [
        {"refId": "A", "expr": "sum(hangar_bay_requests_inprogress)"}
      ]
    },
    {
      "id": 5,
      "type": "stat",
      "title": "Backend scrape up",
      "datasource": {"type": "prometheus", "uid": "${DS_PROM}"},
      "gridPos": {"h": 8, "w": 6, "x": 18, "y": 8},
      "fieldConfig": {
        "defaults": {
          "mappings": [
            {"type": "value", "options": {"1": {"text": "UP", "color": "green"}, "0": {"text": "DOWN", "color": "red"}}}
          ]
        },
        "overrides": []
      },
      "targets": [
        {"refId": "A", "expr": "max(up{job=\"fastapi\"})"}
      ]
    },
    {
      "id": 6,
      "type": "logs",
      "title": "Key events (structlog)",
      "datasource": {"type": "loki", "uid": "${DS_LOKI}"},
      "gridPos": {"h": 10, "w": 24, "x": 0, "y": 16},
      "options": {"showTime": true, "wrapLogMessage": true, "sortOrder": "Descending"},
      "targets": [
        {"refId": "A", "expr": "{app=\"hangar-bay\"} |= \"event_name\""}
      ]
    }
  ]
}
```

### Task 3.2: The provisioning script

**Files:**
- Create: `app/backend/observability/provision_dashboards.py`

- [ ] **Step 1: Create the script:**

```python
# ABOUTME: Provisions the committed dashboards under observability/dashboards/ to the
# ABOUTME: Grafana Cloud stack via POST /api/dashboards/db (service-account token auth).
import json
import sys
from pathlib import Path

import httpx
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]  # app/backend
DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboards"


class ProvisionSettings(BaseSettings):
    """Stack URL + service-account token, from docker/grafana-cloud.env or the environment."""

    GRAFANA_STACK_URL: str
    GRAFANA_SA_TOKEN: SecretStr

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / "docker" / "grafana-cloud.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def main() -> int:
    settings = ProvisionSettings()
    dashboards = sorted(DASHBOARD_DIR.glob("*.json"))
    if not dashboards:
        print(f"no dashboard JSON found in {DASHBOARD_DIR}", file=sys.stderr)
        return 1

    base_url = settings.GRAFANA_STACK_URL.rstrip("/")
    failures = 0
    for path in dashboards:
        payload = {
            "dashboard": json.loads(path.read_text(encoding="utf-8")),
            "overwrite": True,
            "message": f"provisioned from repo ({path.name})",
        }
        response = httpx.post(
            f"{base_url}/api/dashboards/db",
            json=payload,
            headers={"Authorization": f"Bearer {settings.GRAFANA_SA_TOKEN.get_secret_value()}"},
            timeout=30.0,
        )
        if response.status_code == 200:
            body = response.json()
            print(f"{path.name}: {body.get('status')} -> {base_url}{body.get('url', '')}")
        else:
            failures += 1
            print(f"{path.name}: HTTP {response.status_code}: {response.text[:300]}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### Task 3.3: pdm entry point

**Files:**
- Modify: `app/backend/pyproject.toml` (`[tool.pdm.scripts]`, after `export-openapi`)

- [ ] **Step 1: Add:**

```toml
provision-dashboards = "python observability/provision_dashboards.py"
```

### Task 3.4: Provision + verify

- [ ] **Step 1:** `cd app/backend && pdm run provision-dashboards`
Expected stdout: `hangar-bay-backend.json: success -> https://<stack>.grafana.net/d/hangar-bay-backend/...`
- [ ] **Step 2:** Open the dashboard in the stack Grafana; if the `DS_PROM`/`DS_LOKI` variable dropdowns come up unselected, pick the stack's default `grafanacloud-…-prom` / `grafanacloud-…-logs` datasources (variable selection is view-state, not dashboard content — re-provisioning won't fight it). With the Phase 2 pipeline running, panels 1/3/5 show data (error panels may legitimately be empty), and the logs panel streams key events. Re-run the script once more to confirm idempotent overwrite (`overwrite: true` → still `success`).
- [x] **Step 3:** Format/lint the NEW script only: `.venv/bin/black observability/provision_dashboards.py && .venv/bin/flake8 observability/provision_dashboards.py` (from `app/backend`). **Do NOT run `pdm run format`** — it is repo-wide `black .` and this codebase is NOT black-formatted (the 2026-07-18 lint-debt cleanup used autopep8); a repo-wide run reformats ~64 files and re-exposes noqa'd C901/E704 findings by moving their lines. (Deviation note: the original instruction here said `pdm run format`; executing it produced exactly that churn, which was fully reverted via `git restore app/backend/src` before the Phase 3 commit.)
- [ ] **Step 4: Commit**

```bash
git add app/backend/observability/dashboards/hangar-bay-backend.json \
        app/backend/observability/provision_dashboards.py app/backend/pyproject.toml
git commit -m "feat(api): commit backend RED dashboard and Grafana Cloud provisioning script"
```

---

## Phase 4 — Teardown + docs sweep

**Execution Status:** ⬜ NOT STARTED

> Sequencing: only start after Task 2.4 verified the cloud pipeline (don't delete the old stack before the new one demonstrably works).

### Task 4.1: Delete the local stack remnants

**Files:**
- Delete: `app/backend/docker/prometheus/` (entire directory)
- Delete: `app/backend/docker/grafana/` (entire directory)

- [ ] **Step 1:** `git rm -r app/backend/docker/prometheus app/backend/docker/grafana`
- [ ] **Step 2: Remove the dead local volumes/containers** (local Docker state only; the volumes hold scraped dev metrics + an empty Grafana — regenerable and being retired by this migration):

```bash
docker rm -f prometheus grafana 2>/dev/null || true
docker volume rm docker_prometheus_data docker_grafana_data 2>/dev/null || true
```

(Compose prefixes volumes with the project name — the directory name `docker`. Verify actual names with `docker volume ls | grep -E 'prometheus|grafana'` first; remove what matches.)

### Task 4.2: `compose.yml` header comment

**Files:**
- Modify: `app/backend/docker/compose.yml` (comment block only)

- [ ] **Step 1:** Update the `hb-monitoring-net` description lines (currently `#    - Purpose: A private network for the observability stack.` / `#    - Services: FastAPI App, Prometheus, Grafana.` / the scrape sentence) to:

```
# 3. hb-monitoring-net:
#    - Purpose: A private network for observability collection.
#    - Services: FastAPI App, Alloy (ships metrics/logs to Grafana Cloud).
#    - This lets the collector scrape the backend without gaining access to the data tier.
```

Also extend the `--- USAGE ---` comment block: after the existing 3-file `up` command line, add:

```
# The observability overlay requires ./grafana-cloud.env (copy
# grafana-cloud.env.example and fill from 1Password / the Grafana Cloud
# portal); compose fails fast with "env file ... not found" without it.
```

No YAML (non-comment) changes in this file.

### Task 4.3: Design-doc updates

**Files:**
- Modify: `design/fastapi/guides/02-observability-guide.md` §2 (the "Local Visualization" bullet) and any other local-stack references in that file
- Modify: `design/specifications/observability-spec.md` (only sentences describing the local Prometheus+Grafana stack as current state)

- [ ] **Step 1:** In the guide, replace the `Local Visualization: Prometheus & Grafana` bullet with:

```markdown
*   **Visualization & Storage:** `Grafana Cloud` (via `Grafana Alloy`)
    *   **Rationale:** Metrics and logs ship to the managed Grafana Cloud stack (org `scarson`) instead of a self-hosted Prometheus+Grafana pair — no local dashboard/storage containers to maintain. A single Alloy container (`app/backend/docker/compose.observability.yml`) scrapes the FastAPI `/metrics` endpoint and tails the backend's JSON log file (`LOG_FILE` setting). Dashboards are committed JSON under `app/backend/observability/dashboards/`, provisioned with `pdm run provision-dashboards`.
```

Also fix the stale `grafana.yml` sentence (that file never existed) as part of the same edit. Grep the file for `9090`, `3000`, `prometheus.yml`, `grafana` and update each hit to the cloud reality.
- [ ] **Step 2:** In the spec, `grep -n -i "prometheus\|grafana" design/specifications/observability-spec.md` and update only *current-state* claims (e.g. "metrics are scraped by the local Prometheus container") to name the Alloy→Grafana Cloud path. Do NOT touch the deferred-items sections (§2.5 etc.) beyond mechanical reference fixes — their deferral status is unchanged by this migration.

### Task 4.4: CLAUDE.md / AGENTS.md sibling sync

**Files:**
- Modify: `CLAUDE.md` (Project Layout line `docker/  # compose.yml + dependency/observability stacks`; Build & Dev Commands if the observability compose command is referenced)
- Modify: `AGENTS.md` (same lines — the two files MUST stay semantically identical)

- [ ] **Step 1:** Update the layout annotation to `docker/  # compose.yml + dependency stack + Alloy (ships to Grafana Cloud)` in BOTH files; grep both for `observability` and reconcile any other hits with the new reality.
- [ ] **Step 2: Commit the phase**

```bash
git add -u
git add CLAUDE.md AGENTS.md design/
git commit -m "docs: point observability docs at Grafana Cloud, drop local stack config"
```

> After completing this group (Phases 2-4 file changes):
> Review the batch from multiple perspectives (config correctness, secret hygiene, docs accuracy). Minimum 3 review rounds. If round 3 still finds issues, keep going until clean.

---

## Phase 5 — Verification + PR

**Execution Status:** ⬜ NOT STARTED

- [ ] **Step 1:** Invoke `/superpowers:verification-before-completion`. Evidence to gather: full backend pytest run (green, pristine), `pdm run lint`, Alloy `/-/ready`, cloud Explore screenshots (metrics + logs), dashboard URL rendering live data, `git check-ignore app/backend/docker/grafana-cloud.env`, and `git log --stat` confirming no secret file is committed (also grep the diff for `glsa_` and the token prefix).
- [ ] **Step 2:** Adversarial review per repo policy (`/codex review` — use effort `high`, not `xhigh`: xhigh has previously timed out on repo-scale reviews in this project). Address findings via `superpowers:receiving-code-review`.
- [ ] **Step 3:** PR via `commit-commands:commit-push-pr`, target `dev`. Body includes the evidence + `## Merge classification` = `Routine` (dev-tooling/infra swap; no auth/data-integrity/public-interface changes; the one backend code change is an additive, default-off logging sink). Also state in the body: Sam granted standing authorization and auto-merge authority for this migration in the 2026-07-18 working session (chat instruction: "You have authorization to do anything you need and auto-merge authority on everything related").
- [ ] **Step 4:** Wait for CI with a monitoring tool (not sleep-polling); on green, `gh pr merge --merge --delete-branch`. On CI failure: investigate and fix (up to 3 attempts on the same failure before escalating per git-strategy).
- [ ] **Step 5:** Update this plan (banners, Execution Status table, merge SHA), commit the plan update.
- [ ] **Step 6:** Reflection trigger (CLAUDE.md §Learning): capture operational surprises (Grafana UI navigation, Alloy config gotchas, op CLI behavior) in memory; add a pitfalls entry ONLY if a reusable trap actually bit during execution.

---

## Execution strategy recommendation

**Inline execution in this session (`superpowers:executing-plans`), with subagent dispatch for Phase 1 only.** Reasoning: Phases 0, 2.4, 3.4, and 5 need capabilities only the orchestrating session has (browser access to Grafana Cloud, 1Password `op` CLI, standing permissions, cloud UI verification). The phases are tightly sequential (0 → 2.4 → 3.4 → 4 → 5). Phase 1 is the one cleanly isolated code task — dispatch it to a fresh subagent per `superpowers:subagent-driven-development` discipline, then review its diff before Phase 2. Phase 0 runs whenever browser access is available (as of 2026-07-18 it is blocked — see Discoveries — so Phases 1-3 file work proceeds first and the cloud-dependent verification steps queue behind Sam's return). Do NOT run the backend pytest suite concurrently in two agents (one shared test database — see the Phase 1 banner).

## What the shortcut would defer (flagged per CLAUDE.md §Completeness)

- Alerting (no alert rules in cloud Grafana) — deferred with the spec's §2.4.
- Scheduler/job dashboards — blocked on the §2.5 freshness/readiness work (no metrics exist to chart yet).
- Production collection for the M4 Render deploy — the same Grafana Cloud stack can receive it later; M4's plan owns that wiring.
