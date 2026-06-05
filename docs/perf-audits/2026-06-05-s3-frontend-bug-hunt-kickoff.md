# Bug-hunt kickoff — suspected bugs from the 2026-06-05 performance audit (S3 frontend SPA)

Run: `bug-hunt-cycle` with the scope below. Noticed while auditing **performance** of a largely
**latent** SPA (routes=[]); NOT investigated. Treat as leads, not confirmed bugs.

**Scope:** `app/frontend/angular/src/app/features/contracts/**` + `shared/pipes/**` + `tsconfig.app.json`.

**Seed findings (verify, don't trust) — the top two would bite the moment the feature is wired:**
- **Response-shape mismatch** — `contract.api.ts:71-73` reads `response.total_items`/`total_pages`, but
  the backend returns `total`/`page`/`size`/`items` → those fields are always `undefined`.
- **Sort param name mismatch** — `contract-search.ts:76-78` sends `sort_order`, but the backend expects
  `sort_direction` → sorting is silently ignored. (Also sends `type`; backend filters on `type_ids`.)
- **Two divergent contracts services + two model files** (`contract-search.ts`/`contract.models.ts` vs
  `contract.api.ts`/`contract.model.ts`) for one endpoint — pick one.
- **Base-URL inconsistency** — relative `/api/v1/contracts/` vs `environment.apiUrl` → 404 risk under a
  prod origin/CDN split.
- **Resolver drops filters** — `contract-filter.resolver.ts:18-26` parses only page/size/search, losing
  `type`/`sort_by`/`sort_order` on deep-link load.
- **`timeLeft` never updates after first render** — pure pipe over `new Date()`; fix preserving purity
  via a shared ticking timebase (NOT `pure:false`).
- **Error path leaves stale `data`** and silently drops the `catchError` `null` (`contract-search.ts:84,90-94`).
- **`.bak` files compiled** — `tsconfig.app.json:13` includes three `.bak` files; stray `.bak` files in `src`.
