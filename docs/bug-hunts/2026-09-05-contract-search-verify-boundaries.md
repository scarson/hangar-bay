<!-- ABOUTME: Independently cross-validates saved-search text, price, and cap-error boundaries at source d43da7c. -->
<!-- ABOUTME: Separates confirmed defects from deliberate policy and documents persistence-safe remediation choices. -->

# Saved-search boundary cross-validation

Status: DONE_WITH_CONCERNS. Source: `d43da7c`; review date: 2026-09-05. This is a source and local-history review, not a backend runtime or database verification. No source, configuration, tests, git state, server, or database was changed; this report is the only authored file. The dispatch reports a separate successful frontend serializer probe with 101-character text and a generated OpenAPI `maxLength: 100` check. Those are parent evidence, not independently executed checks in this review. Backend Python dependencies were unavailable; no installation was attempted.

## Work checklist

- [x] Trace write, storage, response validation, and replay boundaries.
- [x] Check F005, M3, F008 decisions, relevant implementation/testing pitfalls, and existing tests.
- [x] Distinguish documented policies, confirmed defects, and unresolved remediation choices.
- [x] Persist findings before returning to the parent.

## Results

| Candidate | Classification | Severity | Conclusion |
| --- | --- | --- | --- |
| Search text longer than 100 characters can be saved and replayed into a rejected request | Confirmed | P2 / medium | Browse validation was tightened without corresponding UI and saved-write validation. |
| Browse accepts a finite price above the saved-search ceiling | Design consistency concern; mismatch confirmed | P3 / low | The saved ceiling is deliberate and tested. A universal price-domain change is not already decided. |
| Save-at-cap discards the server's actionable explanation | Confirmed | P3 / low | The backend rejects correctly; frontend replaces the reason with an ineffective retry instruction. |
| Best-effort count cap can overshoot under concurrency | False positive as a new defect | None | Explicitly accepted by M3 design section 3.5; not part of either confirmed defect. |

## Overlong saved text

### Evidence and root cause

`app/backend/src/fastapi_app/schemas/contracts.py:351-358` accepts search strings from 3 through 100 characters. The nearby comment explains that the maximum bounds text entering wildcard matching on the anonymous endpoint. Local commit `bc4cbc8b5280e89324c50d9673717c2b62bee584` (`fix(api): bound the search text at 100 characters`, 2026-08-08) added this maximum, its HTTP test, and generated OpenAPI. Its changed-file list does not include the saved-search schema or frontend controls. The current HTTP test at `tests/api/test_contracts.py:243-251` asserts that 101 characters return 422 and 100 return 200.

In contrast, `schemas/account.py:25` gives `SavedSearchParameters.search` only `min_length=3`. `SavedSearchCreate.search_parameters` uses that model at line 55. The normal save service serializes this model unchanged (`services/saved_search_service.py:54-58`), and the column is JSON (`models/account.py:35`), with no text-length constraint on a value inside that JSON. Thus the save validation path accepts overlong text, assuming the independent name, ownership, and capacity requirements are satisfied.

The frontend search input has no `maxLength` (`app/frontend/web/src/features/contracts/components/FilterRail.tsx:63-70`). `parseContractSearch` retains every nonempty string (`features/contracts/filters.ts:273`); `toApiQuery` trims and checks only the three-character minimum (`:327`). `toSavedSearchParameters` does the same (`features/saved-searches/components/SaveSearchControl.tsx:15,38`). Applying a saved search runs that same permissive parser and navigates to `/contracts` (`SavedSearchesPage.tsx:122-129`). A user can paste 101 ordinary characters into Search, save that state, and apply it again; every browse request using it is invalid under the existing endpoint contract.

This conflicts with [F005 saved-search acceptance criteria](../../design/features/F005-Saved-Searches.md), criteria 1.3 and 3.1-3.2: store the current criteria and re-execute them. The M3 account design section 4.5 listed only the minimum because it predates the later browse limit. The later browse limit is intentional; removing it is not the appropriate default fix. The `SavedSearchParameters` docstring's statement that bounds match `ContractFilters` specifically introduces the type, taxonomy, and blueprint fields; it is supporting context, not the sole basis for claiming every schema field was specified identically.

### Persistence hazard and remediation choices

`SavedSearchSchema.search_parameters` reuses `SavedSearchParameters` (`schemas/account.py:66-69`). The GET list and POST/PUT responses use `SavedSearchSchema` (`api/saved_searches.py:21,31,45`). Adding `max_length=100` directly to the shared model therefore also narrows reads. If any stored row contains longer text, it can fail validation of the entire list response; a rename returning the same stored parameters is also exposed. This is a conditional remediation hazard, not evidence that today's saved-search GET already fails or that production contains such rows.

The [F008 saved-parameter widening decision](../superpowers/plans/2026-08-06-f008-decision-log.md), section D4, lines 63-73, explicitly documents this read-validation hazard: later narrowing can break stored searches. [Implementation pitfall FASTAPI-3](../pitfalls/implementation-pitfalls.md#fastapi-3-a-response-schema-stricter-than-its-own-column-500s-the-whole-page) explains the analogous whole-page blast radius when response validation rejects data the writer or store permits.

The smallest complete direction is to keep the documented browse limit, prevent future invalid writes, and handle invalid frontend state consistently across typing, URL parsing, serialization, and replay. That direction does not decide what to do with already-stored text. Safe choices for Sam to consider are:

1. **Preserve stored text and permissive reads; reject overlong text on creation.** Place the write-only check on the create request, or use distinct request and stored-response parameter models. On replay, retain the visible text and show a clear local validation message so the user can shorten it before querying/saving. Existing rows remain readable, renameable, and deletable; no data is silently rewritten. Retaining support for those stored values while tightening writes is a compatibility choice and requires the explicit approval called for by AGENTS.md before implementation.
2. **Use a common strict stored/write model after establishing data state and agreeing on handling.** A later authorized read-only inventory can determine whether overlong rows exist. If none exist, there is no data conversion to perform; writes must be protected during rollout so the inventory does not become stale. If rows do exist, choose a reviewed migration or user-mediated replacement policy before tightening reads. Do not infer permission to truncate, delete, or rewrite them. The current MVP update endpoint changes names only; adding criteria editing would extend its public contract.

A UI-only maximum prevents the ordinary typing path but leaves direct saved-create requests and existing deep links/replay unresolved, so it is only a partial remedy. Silently truncating text changes the term; dropping it widens the search. Neither transformation should be disguised as validation. F005 section 15 already allows silently ignoring filter options that later become invalid, but does not explicitly choose truncation of free-text terms. An invalid-text policy still needs a concrete decision; the 100-character browse limit itself does not.

### Test gap

The browse HTTP boundary test already exists. Saved schema and HTTP tests cover short search text, negative prices, and unknown fields (`tests/api/test_account_schemas.py:74-96`; `tests/api/test_saved_searches.py:143-151`), but do not cover 100/101-character saved text. Frontend save tests cover short-term omission, filter preservation, and a 409 name conflict; no maximum-length case was found in the inspected parser/save/replay tests.

Add tests for 100 and 101 characters at saved creation and the chosen frontend behavior; exercise typing and URL/replay paths, and verify the emitted request or absence of a request as well as the rendered feedback. Include whitespace and non-BMP Unicode so JavaScript UTF-16 length and backend character counting do not quietly diverge. If permissive reads are chosen, a real persisted overlong row plus an ordinary sibling must remain listable and renameable. If a migration is chosen, test that specific data policy and rollout ordering. These checks were not run here.

## Price ceiling asymmetry

`ContractFilters.min_price/max_price` have `ge=0` and no upper bound (`schemas/contracts.py:361-362`). The frontend's finite-number parser likewise has no ceiling (`filters.ts:169-179,207-209,274-275`) and both serializers carry those numbers unchanged. `SavedSearchParameters.min_price/max_price` instead enforce `le=1_000_000_000_000_000` and `allow_inf_nan=False` (`schemas/account.py:10-13,26-27`). A finite value such as 1,000,000,000,000,001 is in the browse schema domain and outside the save domain. No database-backed browse request for that value was executed in this review.

The ceiling is intentional, not an accidental missing or extra constraint: commit `576647b3807bfb16a89885ddb4409d792c4ea778` (`fix(api): bound price fields against non-finite and overflow values`, 2026-07-18) explicitly applies it to saved-search and watchlist prices, describes preventing persistence-time failures, and includes regenerated OpenAPI. Current schema tests cover all four fields, reject non-finite values and 1e20, and accept exactly 1e15 (`tests/api/test_account_schemas.py:14-32,115-128`). Saved-search HTTP tests pin rejection and boundary acceptance (`tests/api/test_saved_searches.py:154-176`). These are existing deliberate tests, not tests to remove as allegedly incorrect.

The rationale needs precision: saved parameters are JSON (`models/account.py:35`), while the watchlist `max_price` column is `Numeric(20,2)` (`models/account.py:55`). The common comment's storage-width justification directly applies to the latter. It does not demonstrate that a finite saved price just above 1e15 cannot be stored as JSON or queried. The historical fix deliberately used one conservative guard across both kinds of fields. No reviewed F005, M3, or F008 decision establishes that the anonymous browse API must share that maximum. F008's exact-bound decision concerns its added type/taxonomy/blueprint fields, and the F008 implementation plan (`docs/superpowers/plans/2026-08-06-f008-type-aware-contract-browsing.md:77`) even records a deliberate positive-ID asymmetry.

**Classification:** a confirmed domain mismatch with low practical severity and a product-design decision for remediation. It is not a broken replay case: accepted saved prices are a subset of accepted browse prices. It prevents saving an otherwise schema-valid extreme-price view. The likely complete choice is either a documented common price limit across browsing and saving, or a save-specific finite-number policy justified by actual storage constraints. Changing either API's accepted range requires deciding that contract; do not remove `allow_inf_nan=False`, weaken the watchlist guard, or silently clamp/drop a price while claiming to save the same criteria. A smaller behavior-preserving remedy is a clear save validation message for the already-established ceiling; changing the numeric ceiling is unnecessary for that feedback improvement.

Test the chosen rule at exactly 1e15 and one representable value above it through browse/save/replay, retaining the existing finite-value checks. Current tests compare 1e15 with 1e20, so they do not pin the immediate next-above boundary or cross-flow consistency.

## Cap explanation lost in the frontend

`services/saved_search_service.py:48-52` returns HTTP 400 with `Saved search limit reached (maximum <configured limit>).` `api/saved_searches.py:18,33` declares that body in the route's error contract. M3 section 3.5 explicitly chooses capped plain lists and a clear cap-breach detail; F005's final implementation-deviation note records the 100-search cap overriding its earlier no-limit wording. The cap policy and benign concurrency overshoot are already documented; they do not need to be reopened to fix feedback.

`useCreateSavedSearch` destructures only `data` and `response` and calls `raiseApiError` with status alone (`features/saved-searches/hooks/useSavedSearches.ts:31-32`). `ApiError` supports an optional detail, `extractDetail` already extracts a string, and `raiseApiError` already accepts it (`lib/api/client.ts:19-30,37-44,50-54`). The save form only special-cases 409; all other errors render `Could not save the search. Try again.` (`SaveSearchControl.tsx:65,94-102`). Thus a deterministic cap rejection loses its cause, and retry cannot help until a saved search is removed.

The working sibling is watchlist creation: `features/watchlists/hooks/useWatchlist.ts:34-35` carries `extractDetail(error)`, and `components/WatchlistPage.tsx:31-43` translates the cap into a remove-before-adding message. The smallest remedy is to carry detail in the saved-create hook using the existing helper and render a clear limit/recovery message in the existing alert, preserving the separate duplicate and generic/network cases. This is routine follow-through on the documented cap/error policy, with no new product or compatibility decision required.

The backend test already asserts HTTP 400 and a detail containing `limit` (`tests/api/test_saved_searches.py:130-138`). Frontend hook tests only pin status and invalidation for 409 (`useSavedSearches.test.tsx:105-121`); the save component tests end with the 409 case (`SaveSearchControl.test.tsx:125-137`). Add a fetch-seam 400 test proving detail survives into `ApiError` and that the real form announces a useful removal-before-retry message. A status-only assertion would miss this defect again. Preserve the test for generic failures and failed-request cache behavior.

## Verification limits and policy summary

The source checks and local git history succeeded. An initial git history read hit Windows ownership protection; a subsequent read used a process-local `safe.directory` setting for this known worktree without modifying git configuration. One guessed decision-log path did not exist; file discovery located and the review read the actual plan-directory decision log. No error was treated as successful evidence.

[Testing pitfalls](../pitfalls/testing-pitfalls.md), sections 3-4 and TEST-1/TEST-5, support checking exact error messages, oversized inputs, real HTTP binding, and real frontend code with the network stubbed at fetch. FASTAPI-3 and the F008 widening decision require considering persisted response data before narrowing shared schemas. They do not authorize a data rewrite, impose a generic approval gate on every error-message fix, or require reopening an already-documented cap.

The two confirmed defects are ready for remediation planning. The overlong-text persistence choice and any changed numeric domain need Sam's decision; the cap-feedback fix does not. Runtime/backend evidence and actual persisted-row inventory remain unverified, so this report makes no claim about production prevalence or passing tests.
