<!-- ABOUTME: Tracks the contract-search bug hunt, audit scope, and verification evidence. -->
<!-- ABOUTME: Preserves phase status and operational decisions for continuation. -->

# Contract search bug-hunt progress

## Checklist

- [x] Research and freeze the audit scope.
- [ ] Run exploratory, holistic, multipass, and differential hunters.
- [ ] Enumerate and cross-validate every raw finding; reconcile dispositions.
- [ ] Inspect test gaps and update generalizable testing guidance where warranted.
- [ ] Resolve any material product or architecture decisions with Sam.
- [ ] Write and independently review a remediation plan.
- [ ] Verify and commit the completed audit artifacts.

## Scope and method

Audit commit: `d43da7c`, fetched `origin/dev` on September 5, 2026. Full cycle: the contract-search flow spans SQL filtering/counting/pagination, URL normalization, delayed requests, displayed result metadata, and saved-search persistence/replay. The cross-layer state transitions justify four independent methods even after the recent frontend coverage campaign.

Primary backend files under `app/backend/src/fastapi_app/`: `api/contracts.py`, `api/saved_searches.py`, `services/contract_service.py`, `services/saved_search_service.py`, `schemas/contracts.py`, the saved-search portions of `schemas/account.py` and `models/account.py`, and `models/contracts.py`.

Primary frontend files under `app/frontend/web/src/`: production files in `features/contracts/` and `features/saved-searches/`, `routes/contracts.index.tsx`, and `routes/contracts.$contractId.tsx`. Associated tests inform cross-validation and test-gap analysis; individual hunter methods may deliberately avoid tests. Adjacent context includes the API client, query/router setup, debounce utility, resolved account identity, and ingestion metadata that defines liveness/readiness. Ingestion writers, authentication internals, dependency maintenance, and reward-per-jump architecture are outside primary scope.

Authoritative context: [product purpose and URL-state principles](../../PRODUCT.md), [F008 prior bug-hunt findings and accepted decisions](2026-08-08-f008-prerelease-consolidated.md), [frontend coverage handoff](../superpowers/handoffs/2026-09-05-frontend-coverage-handoff.md), and project feature specs, decision logs, and pitfalls.

All dispatched agents use `gpt-6-astra` with `high` reasoning effort, as Sam requested and the hunt skill recommends. The harness has four total active slots including the coordinator, so three hunters run concurrently and the fourth starts when a slot opens. This is a disclosed scheduling adaptation; all four methods and full reconciliation remain required.

## Workspace and verification notes

- Root checkout began on `dev` with only untracked `.codex/config.toml`. Sam was asked about handling it under AGENTS.md; that decision remains pending. Audit work is isolated in `.claude/worktrees/bug-hunt-contract-search-2026-09-05`, leaving the file untouched. No answer is inferred from elapsed time.
- Git's ownership guard is handled with command-scoped `safe.directory`, without global configuration changes. Fetch and worktree metadata required normal host permissions because `.git` is read-only in the sandbox.
- The fresh worktree has no installed frontend/backend dependencies. No application server or database lifecycle is started by this audit.
- Existing known decisions and residuals must be rechecked against current source before being treated as fresh bugs.

## Hunter status

Exploratory, holistic, and multipass hunters started against the frozen source revision before worktree creation. Their assigned report paths now point into this isolated checkout. Differential dispatch is pending an available slot.
