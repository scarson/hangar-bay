<!-- ABOUTME: Tracks the contract-search bug hunt, audit scope, and verification evidence. -->
<!-- ABOUTME: Preserves phase status and operational decisions for continuation. -->

# Contract search bug-hunt progress

## Checklist

- [x] Research and freeze the audit scope.
- [x] Run exploratory, holistic, multipass, and differential hunters.
- [x] Enumerate and cross-validate every raw finding; reconcile dispositions.
- [x] Inspect test gaps and update generalizable testing guidance where warranted.
- [x] Resolve any material product or architecture decisions with Sam.
- [ ] Write and independently review a remediation plan.
- [x] Independently check the consolidated report and verify reconciliation.
- [x] Commit the available audit artifacts.

## Scope and method

Audit commit: `d43da7c`, fetched `origin/dev` on September 5, 2026. Full cycle: the contract-search flow spans SQL filtering/counting/pagination, URL normalization, delayed requests, displayed result metadata, and saved-search persistence/replay. The cross-layer state transitions justify four independent methods even after the recent frontend coverage campaign.

Primary backend files under `app/backend/src/fastapi_app/`: `api/contracts.py`, `api/saved_searches.py`, `services/contract_service.py`, `services/saved_search_service.py`, `schemas/contracts.py`, the saved-search portions of `schemas/account.py` and `models/account.py`, and `models/contracts.py`.

Primary frontend files under `app/frontend/web/src/`: production files in `features/contracts/` and `features/saved-searches/`, `routes/contracts.index.tsx`, and `routes/contracts.$contractId.tsx`. Associated tests inform cross-validation and test-gap analysis; individual hunter methods may deliberately avoid tests. Adjacent context includes the API client, query/router setup, debounce utility, resolved account identity, and ingestion metadata that defines liveness/readiness. Ingestion writers, authentication internals, dependency maintenance, and reward-per-jump architecture are outside primary scope.

Authoritative context: [product purpose and URL-state principles](../../PRODUCT.md), [F008 prior bug-hunt findings and accepted decisions](2026-08-08-f008-prerelease-consolidated.md), [frontend coverage handoff](../superpowers/handoffs/2026-09-05-frontend-coverage-handoff.md), and project feature specs, decision logs, and pitfalls.

All dispatched agents use `gpt-6-astra` with `high` reasoning effort, as Sam requested and the hunt skill recommends. The harness has four total active slots including the coordinator, so three hunters run concurrently and the fourth starts when a slot opens. This is a disclosed scheduling adaptation; all four methods and full reconciliation remain required.

## Workspace and verification notes

- Root checkout began on `dev` with only untracked `.codex/config.toml`. Sam was asked about handling it under AGENTS.md; that decision remains pending. Audit work is isolated in `.claude/worktrees/bug-hunt-contract-search-2026-09-05`, leaving the file untouched. No answer is inferred from elapsed time.
- Git's ownership guard is handled with command-scoped `safe.directory`, without global configuration changes. Fetch and worktree metadata required normal host permissions because `.git` is read-only in the sandbox.
- The worktree began without installed dependencies; frontend dependencies were subsequently restored for the observations below. No application server or database lifecycle was started by this audit.
- Existing known decisions and residuals must be rechecked against current source before being treated as fresh bugs.

## Hunter status

All four hunters completed. Exploratory, holistic and multipass overlapped; differential started when exploratory completed. Two additional Astra/high verifiers assessed saved-search UI behavior and boundary/storage policy. A further Astra/high reviewer confirmed consolidation and reconciliation; the review's two corrections and optional ordering clarification are incorporated.

## Findings and verification

- Six confirmed bugs are recorded in the [consolidated findings and reconciliation](2026-09-05-contract-search-consolidated.md). All labelled raw hunter entries and descriptive cleared concerns have dispositions.
- Frontend dependencies were restored from the unchanged committed lockfile. Baseline: 509 tests passed across 33 files, but six notification-query warnings make the output non-pristine. The report records the fixture root cause separately.
- Four runtime observation probes confirmed history/page overwrite, invisible rename error, readiness retained after failed refresh on a later list response, and overlong payload/API-bound disagreement. The final observation run passed all four with clean output. The first run's one failure was an observation-helper assumption about unfetched cache entries; correcting that assumption and rerunning settled it.
- Exact probe source is archived as a `.tsx.txt` evidence file outside the regression suite. No application changes remain; a generated route file's line-ending rewrite from the test runner was restored from git.
- First-wave evidence is committed in `74667ca`; final audit reports and testing guidance are committed alongside this record. A mechanical check verified all 35 labelled entries have exactly one reconciliation row, every local report link resolves, and every audit file has its required header. Independent review also checked unlabelled dispositions and verified both requested report corrections. No review correction remains open.

## Approved decisions

Sam explicitly approved both recommendations on September 5, 2026: preserve existing overlong saved text/readability while rejecting new overlong saves and showing local validation on Apply; sort Name by the displayed contract headline. The established saved-price ceiling remains unchanged with clearer feedback. The remediation plan and its independent reviews are in progress. The root checkout's unrelated config remains untouched in the separate checkout.

## Operational learning

Use the existing Vitest environment for router/component checks; a standalone JSDOM loader also has to reproduce browser globals and conditional exports. The differential hunter stopped its standalone setup after three unsuccessful attempts; the coordinator's existing-environment observation succeeded. Reuse actual application hooks/components and intercept only fetch; cache status and rendered state give stronger evidence than request counters.
