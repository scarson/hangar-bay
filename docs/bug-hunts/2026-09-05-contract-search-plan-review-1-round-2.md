<!-- ABOUTME: Records the independent cold review findings for the contract-search remediation plan. -->
<!-- ABOUTME: Preserves source-verified execution gaps from cycle 1, round 2. -->

# Contract-search plan review — cycle 1, round 2

**Substantive findings raised: 2.** Independent cold whole-plan review using GPT-6 Astra at high reasoning effort. No plan history or prior review artifacts were consulted. No rejection rationales were pending.

## 1. Database preflight does not cover the full suite's second destructive target

**Location:** [Runtime and database preflight](../plans/2026-09-05-contract-search-bug-hunt-remediation-plan.md), line 144: “Confirm that the configured target is a disposable test database distinct from application/production databases before any backend test or measurement.” Task 6.1, line 330: “From backend run `python -m pdm run lint`, `python -m pdm run pytest`”.

**Dimension:** Context gaps; implementation pitfalls; cross-task dependencies.

**Claim:** Verifying only `DATABASE_URL_TESTS` does not establish that the required full-suite command is safe. The real [backend test fixture](../../app/backend/src/fastapi_app/tests/conftest.py), `blank_migrated_sync_connection` at lines 264–293, replaces that URL's database with the fixed name `m4_equiv_check`, connects to the same server's `postgres` database, and executes `DROP DATABASE IF EXISTS m4_equiv_check WITH (FORCE)` before setup and during teardown. [Migration tests](../../app/backend/src/fastapi_app/tests/test_migrations.py) consume that fixture in normal full-suite discovery. Two executors using different disposable `DATABASE_URL_TESTS` names on one server therefore still collide on this fixed target; a disposable primary target alone also does not authorize deleting an existing database of that name. Include the derived database in the preflight and serialize all consumers sharing its server, or require an isolated disposable PostgreSQL instance before Task 6.1. No database operation was run during this review.

## 2. The prescribed generic 422 message incorrectly identifies valid search criteria as the problem

**Location:** [Task 3.2 — saved-create error mapping](../plans/2026-09-05-contract-search-bug-hunt-remediation-plan.md), line 272: “map 422 to ‘Some search criteria are invalid. Review them and save again’” and “server 422 fallback is honest for unrecognized criteria.”

**Dimension:** Implementation pitfalls; testing pitfalls; ambiguity.

**Claim:** A normal form submission can receive a 422 because of the saved-search **name** while every search criterion is valid. [SavedSearchCreate](../../app/backend/src/fastapi_app/schemas/account.py), line 54, caps `name` at 100 code points. The actual [SaveSearchControl form](../../app/frontend/web/src/features/saved-searches/components/SaveSearchControl.tsx), lines 70–97, checks only that the trimmed name is nonempty and imposes no maximum. Task 3.2 adds criteria validation without closing that name path. Because the proposed hook deliberately discards array-shaped validation detail, a 101-character name will reach the exact generic message, directing the user to change valid criteria and leaving the actual correction unidentified. Make the generic fallback cover the name as well as criteria (as the linked boundary investigation already recommends for unknown 422 responses), and include an actual name-field 422 payload in the form regression. This requires neither a broader global error contract nor structured error parsing.
