# Bug-hunt kickoff — suspected bugs from the 2026-06-05 performance audit (S1 backend read path)

Run: `bug-hunt-cycle` with the scope below. These were noticed while auditing **performance** and
were NOT investigated — treat them as leads for the hunters, not confirmed bugs.

**Scope:** `app/backend/src/fastapi_app/` — the read path (`services/contract_service.py`,
`api/contracts.py`, `schemas/contracts.py`, `models/contracts.py`, `db.py`, `main.py`,
`config.py` + `core/config.py`).

**Seed findings (verify, don't trust):**
- **Short pages under item filters** — `contract_service.py:167-177`: `LIMIT` is applied to the
  join's fan-out rows *before* Python `.unique()` dedups, so a page can return < `size` distinct
  contracts and pagination can split/duplicate contracts across pages; disagrees with the DISTINCT
  count. (Co-located with perf findings P4/P5 — will be touched by their fix.)
- **Destructive startup** — `main.py:128-137` (`create_db_tables`, called at `:45`): `drop_all` +
  `create_all` runs unconditionally on **every** startup → data loss on any non-empty DB. Highest
  severity. Should be migration-gated / environment-guarded.
- **Response validation crash on courier contracts** — `schemas/contracts.py:31`
  `start_location_id: int` (required) vs `models/contracts.py:48` nullable column → null start
  location fails `response_model` validation (500).
- **Duplicate definitions in `db.py`** — `Base = declarative_base()` at `:6` and `:27` (second
  discards the first; import-order sensitive); `get_db_session_factory` defined twice (`:30`, `:37`).
- **Two divergent `Settings`** — `config.py` vs `core/config.py`, imported by different layers.
- **Silent no-op filters** — `min_me/max_me/min_te/max_te` accepted+validated but never applied.
- **Nondeterministic `ship_name` sort** — orders on an outer-joined nullable item column over the fan-out.
- **Leftover import-time `print()` debug** — `config.py`, `core/config.py`, `main.py:9`.
