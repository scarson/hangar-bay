# Bug-hunt kickoff — suspected bugs from the 2026-06-05 performance audit (S2 ESI ingestion)

Run: `bug-hunt-cycle` with the scope below. Noticed while auditing **performance**; NOT investigated.
Treat as leads, not confirmed bugs.

**Scope:** `app/backend/src/fastapi_app/services/background_aggregation.py`,
`core/esi_client_class.py`, `services/db_upsert.py`.

**Seed findings (verify, don't trust) — ordered by likely severity:**
- **Item pages beyond page 1 silently dropped** — `esi_client_class.py:187-190`: `get_contract_items`
  calls the ETag helper WITHOUT `all_pages=True`, so multi-page item lists are under-ingested (data loss).
- **`record_id` primary-key collision across contracts** — `ContractItem.record_id` is an
  autoincrement PK, but ingestion supplies ESI's `record_id` (unique only *within* a contract);
  `bulk_upsert` keys ON CONFLICT on the PK, so items from different contracts sharing a `record_id`
  can collide/clobber. (`models/contracts.py:89` + `background_aggregation.py:264-276` + `db_upsert.py`.)
- **`item_processing_status` clobbered to `PENDING_ITEMS` every run** — the ON CONFLICT SET rewrites
  all non-PK columns (`db_upsert.py:33-39`), resetting an indexed progress column each cycle.
- **ON CONFLICT references columns absent from INSERT VALUES** — `items_last_fetched_at`,
  `contract_esi_etag`, `start_location_system_id/region_id` may be overwritten to NULL/default each
  upsert; verify SQLAlchemy `excluded` behavior and narrow the SET.
- **Silent incomplete upserts** — broad `except Exception` on per-region/per-contract fetches
  (`background_aggregation.py:136-137, 279-280`) reports failures as "no data."
- **Possibly-unbound `response`** on a first-iteration network failure (`esi_client_class.py:103, 128`).
- **Dead `get_cache` import** (`background_aggregation.py:12`).
