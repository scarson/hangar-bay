<!-- ABOUTME: Records the independent cold round-four review of the contract-search remediation plan. -->
<!-- ABOUTME: Captures source-grounded substantive findings for the plan author's disposition. -->

# Contract-search remediation plan review, round 4

Substantive findings raised: **1**.

## 1. Page-correction ownership must use the same identity as the cached request

**Location:** Task 2.1, the proposed `pageOutOfRange` expression and navigation updater in [the contract-search remediation plan](../plans/2026-09-05-contract-search-bug-hunt-remediation-plan.md#task-21--protect-page-correction-and-readiness-transitions).

**Quoted text:** “reuse exported `sameSearch` and `data.countsSearch`; only compute an actionable out-of-range condition for matching requested state”; `sameSearch(data.countsSearch, search)` and `sameSearch(data.countsSearch, prev)`.

**Dimensions:** Implementation pitfalls (WEB-1), testing pitfalls (TEST-25), context gap in the cache-identity assumption.

**Claim:** The proposed predicate compares raw URL state, but `useContracts` keys its cache with `toApiQuery(effectiveSearch)`, which trims text and omits text below the minimum length. Distinct raw states can therefore share one request key and one cached response while failing `sameSearch`. For example, `{search: 'Rifter', page: 3}` and `{search: ' Rifter ', page: 3}` serialize identically. A cached response captured under the first spelling retains that spelling in `countsSearch` when the second spelling becomes the settled request; no replacement fetch is required. If the response has `total: 10`, `size: 50`, and an empty page 3, both proposed guards refuse to correct this genuinely out-of-range page even though the response belongs to the exact current API request. Waiting out the debounce does not resolve the mismatch. The same identity problem exists for different omitted one- or two-character inputs.

**Source evidence:** [useContracts.ts](../../app/frontend/web/src/features/contracts/hooks/useContracts.ts) stores raw `effectiveSearch` as `countsSearch` while keying by the serialized `query`; [filters.ts](../../app/frontend/web/src/features/contracts/filters.ts) trims and omits text in `toApiQuery`; [main.tsx](../../app/frontend/web/src/main.tsx) configures a 30-second fresh-query window. The existing `sameSearch` correctly implements raw-state equality for debounce ownership; changing its global semantics would affect that separate responsibility.

**Runtime evidence:** A temporary test used the real `useContracts`, `parseContractSearch`, `toApiQuery`, and `sameSearch`, a real QueryClient configured with the production `staleTime: 30_000`, and only a fetch-boundary stub. It fetched the unpadded page-3 search, rerendered with padded text, and completed the debounce interval. Assertions confirmed equal serialized queries, the same retained data object, exactly one contract-list request, a false raw `sameSearch` result, and a requested page exceeding the returned page count. Command: `npm.cmd test -- src/features/contracts/hooks/plan-review-cache.test.tsx --reporter=dot`; result: **1 test passed, 1 file passed**, with no unexpected output. This verifies the hook/cache mechanism; it is not an end-to-end browser reproduction. The temporary probe was removed after verification; no production or plan edits were made.

**Required plan clarification:** Define page-correction ownership by canonical request equivalence, consistent with the existing cache key, in both the outer predicate and queued updater. Keep raw URL text intact and preserve `sameSearch`'s debounce semantics. Add a cached-response regression for equivalent padded text and omitted short text, alongside the already-planned different-population and true-invalid-page tests, so preventing stale-population clamping does not disable legitimate clamping.
