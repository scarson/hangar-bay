# ABOUTME: Systematic test-coverage review of the backend READ path (contract_service.py + api/contracts.py).
# ABOUTME: Per-function path maps with coverage verdicts; every GAP carries a severity. Research-only artifact.

# Backend READ path — test coverage review (2026-08-08)

**Sources reviewed:**
- `app/backend/src/fastapi_app/services/contract_service.py` (1185 lines)
- `app/backend/src/fastapi_app/api/contracts.py` (81 lines)

**Test files reviewed:**
- `app/backend/src/fastapi_app/tests/api/test_contract_filters.py` (2525 lines)
- `app/backend/src/fastapi_app/tests/api/test_contracts.py` (192 lines)
- `app/backend/src/fastapi_app/tests/services/test_contract_service.py` (1324 lines)
- Supporting: `tests/conftest.py` (setup_contracts fixture), `tests/test_db_engine.py` (SQLA-4 engine scrub)

**Intent sources consulted:** `design/features/F008-Type-Aware-Contract-Browsing.md` (via decision logs), `docs/pitfalls/testing-pitfalls.md`, `docs/pitfalls/implementation-pitfalls.md` (SQLA-4), `docs/superpowers/plans/2026-08-06-f008-decision-log.md` (D12), `docs/superpowers/plans/2026-08-08-overnight-followups-decision-log.md` (OD3, OD4).

**Rules applied:** no "covered indirectly" — a path with no dedicated assertion is a GAP. API-level tests that directly assert on a path count as Covered (integration). Enum/operator siblings are separate rows. Severity when in doubt: escalated.

**Depth check:** contract_service.py at 1185 lines requires ≥ 48 mapped paths (1 per 25 lines). This review maps **90+ paths** across the two files. Depth check passes.

---

## 1. `contract_service.py`

### 1.1 `_needs_item_join` (lines 78–88)

| # | Path (lines) | Coverage | Verdict |
|---|---|---|---|
| 1 | `filters.search` truthy → True (84) | `test_expired_exclusion_also_applies_on_the_item_joined_path`, `test_pagination_with_search_returns_full_distinct_pages`, equivalence case `search-joins-items` | Covered |
| 2 | `filters.type_ids` truthy → True (85) | `test_filter_by_type_id`, equivalence case `type-ids-joins-items` | Covered |
| 3 | `sort_by == ship_name` → True (87) | `test_pagination_sorted_by_ship_name_no_duplicates`, `test_ship_name_sorts_both_ways_and_leaves_item_less_contracts_last` | Covered |
| 4 | none → False (unjoined path) | Every default-filters test; equivalence case `unfiltered` uses `_needs_item_join` itself as the reference discriminator | Covered |
| 5 | is_bpc / ranges / taxonomy deliberately do NOT set the join (comment 89–93) | `test_pagination_with_is_bpc_returns_full_distinct_pages` (proves is_bpc works without row multiplication); taxonomy/range tests pass through the EXISTS path | Covered |

### 1.2 `still_listed_by_esi` (96–168) + `_newest_in` (171–183)

| # | Path (lines) | Coverage | Verdict |
|---|---|---|---|
| 6 | Empty `AGGREGATION_REGION_IDS` → correlated-only predicate (147–148) | `liveness_branch` param `region-not-configured` across `test_contracts_missing_from_the_latest_run_are_excluded`, `test_a_region_whose_run_failed_keeps_all_its_contracts`, `test_never_stamped_contracts_stay_visible`, plus all 13 derived-total equivalence cases | Covered |
| 7 | Configured region, row at its region's watermark → visible (150–158, fast/uncorrelated branch) | Same three tests under `liveness_branch` param `region-configured` | Covered |
| 8 | Configured region, row below watermark → hidden (fast branch) | `test_contracts_missing_from_the_latest_run_are_excluded` (`region-configured`), `segment_corpus` 962007 | Covered |
| 9 | `last_seen_at IS NULL` → visible, under both config states (143, 160) | `test_never_stamped_contracts_stay_visible` (both params) | Covered |
| 10 | Per-region isolation: a stalled region keeps its own watermark (both branches) | `test_a_region_whose_run_failed_keeps_all_its_contracts` (both params) | Covered |
| 11 | **`case` else_ fallback with a NON-empty config** (166): row whose region is absent from a non-empty `AGGREGATION_REGION_IDS` is judged by the correlated subquery | No test seeds a row in a region outside a non-empty configured set and asserts its visibility both at and below its own region's watermark. `liveness_branch` flips config between `[A,B]` (rows all inside) and `[]` (branch 6). The docstring claims a both-way EXCEPT verification against production under a deliberately-wrong config (perf audit 2026-08-02), but that is a one-time manual check, not a regression test. Config drift is the exact scenario the comment calls out. | **GAP — correctness** |

### 1.3 `_has_blueprint_copy_item` (186–214)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 12 | EXISTS true branch (is_bpc=true) | `test_filter_by_is_bpc` (service + API), `test_is_bpc_is_a_contract_level_predicate_on_a_mixed_bundle` | Covered |
| 13 | Negated branch (is_bpc=false), exact complement | `test_is_bpc_is_a_contract_level_predicate_on_a_mixed_bundle` (totals sum to unfiltered), `test_is_bpc_false_matches_items_esi_left_unmarked` | Covered |
| 14 | NULL `is_blueprint_copy` reads as "not a copy" (ESI-3, 208–210) | `test_is_bpc_false_matches_items_esi_left_unmarked` | Covered |
| 15 | Offered-only (`is_included IS TRUE`, 208): want-to-buy copy does not match | `test_is_bpc_is_a_contract_level_predicate_on_a_mixed_bundle` (954003) | Covered |

### 1.4 `_offered_item_range_exists` (217–248)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 16 | runs: min only / max only / both-bounds-on-one-item (242–245) | `test_runs_filter_is_a_contract_level_predicate_with_a_three_way_identity` (low, high, [10,12] window) | Covered |
| 17 | ME: min only / max only / window | `test_me_filter_..._three_way_identity` | Covered |
| 18 | TE: min only / max only / window | `test_te_filter_..._three_way_identity` | Covered |
| 19 | NULL column satisfies neither direction (BPO with runs=None) | runs identity test (963003 in neither branch) | Covered |
| 20 | Offered-only: requested-side item never matches | all three identity tests (963004 / 964004 / 964104) | Covered |
| 21 | Families are independent EXISTS (different items satisfy different families) | `test_range_families_are_independent_of_each_other` | Covered |

### 1.5 `_apply_contract_filters` (251–320)

| # | Path (lines) | Coverage | Verdict |
|---|---|---|---|
| 22 | Expiry predicate on count + simple fetch (263) | `test_expired_contracts_are_excluded_from_the_list` (asserts total AND page) | Covered |
| 23 | Expiry predicate on joined fetch | `test_expired_exclusion_also_applies_on_the_item_joined_path` | Covered |
| 24 | Expiry predicate across page boundaries (TEST-4) | `test_expired_exclusion_holds_across_page_boundaries` | Covered |
| 25 | Delisting predicate (268) | §1.2 rows above | Covered |
| 26 | search: title ILIKE branch (276) | `test_filter_contracts_by_search` ("Special") | Covered |
| 27 | search: item type_name ILIKE branch (277) | `test_filter_contracts_by_search` ("Beta") | Covered |
| 28 | min_price (282–283) | `test_filter_by_min_price`, API `test_filter_contracts_by_price` | Covered |
| 29 | max_price (284–285) | `test_filter_by_max_price`, API `test_filter_contracts_by_price` (incl. both-bounds) | Covered |
| 30 | **min_collateral (286–287)** | No test anywhere sets `min_collateral`. Grep confirms the only collateral filter use is `max_collateral` (combined with `min_price` in `test_filter_by_price_and_collateral`). An inverted operator (`<=` for `>=`) or a copy-paste against the wrong column would ship undetected. | **GAP — correctness** |
| 31 | max_collateral (288–289) | `test_filter_by_price_and_collateral` (only in combination — but it has its own assertion discriminating on collateral 1M vs 100M) | Covered |
| 32 | is_ship_contract true / false / absent (292–293) | `test_filter_by_is_ship_contract` (all three) | Covered |
| 33 | contract_type: single, multiple (297–299) | `test_filter_by_contract_type` | Covered |
| 34 | contract_type includes `unknown` → `not_in(known)` folding (300–307) | `test_a_contract_type_outside_the_enum_stays_counted_and_reachable` (selected total==2, both rows returned) | Covered |
| 35 | is_bpc true / false / absent (313–315) | §1.3 rows | Covered |

### 1.6 `_apply_location_filters` (323–339)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 36 | region_ids single / multiple (332–333) | `test_filter_by_region_ids_repeated_query_params`, `test_filter_by_multiple_region_ids` | Covered |
| 37 | system_ids single / multiple (334–335) | `test_filter_by_system_ids_repeated_query_params`, `test_filter_by_multiple_system_ids` | Covered |
| 38 | station_ids single / multiple (336–337) | `test_filter_by_station_ids_repeated_query_params`, `test_filter_by_multiple_station_ids` | Covered |

### 1.7 `_apply_item_filters` (342–390)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 39 | type_ids IN (344–345) | `test_filter_by_type_id`, API repeated-param test | Covered |
| 40 | runs / ME / TE family gating (`min is not None or max is not None`, 349/355/361) | three-way identity tests | Covered |
| 41 | taxonomy: category only (379–380) | `test_category_filter_is_a_contract_level_predicate_on_a_mixed_bundle`, repeated categories in `test_group_filter_stands_alone_and_repeats` | Covered |
| 42 | taxonomy: group only, single + repeated (381–382) | `test_group_filter_stands_alone_and_repeats` | Covered |
| 43 | taxonomy: category AND group must land on the SAME offered item (374–388) | `test_category_and_group_must_be_satisfied_by_the_same_offered_item` (0-match pairing + 1-match pairing) | Covered |
| 44 | taxonomy offered-only | `taxonomy_corpus` 965003 asserted absent | Covered |
| 45 | Unrepresented category → empty page, not error | `test_a_category_absent_from_the_corpus_returns_an_empty_page` | Covered |

### 1.8 `_count_distinct_contracts` (393–403)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 46 | DISTINCT contract count over duplicated joined rows | `test_the_residual_holds_on_the_item_joined_path` (3-item contract counts once); used as the reference oracle in the 13 derived-total equivalence cases | Covered |

### 1.9 `_count_under_ships_filter` (429–441)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 47 | `is_ship_contract is None` → all (437–438) | unfiltered segment tests | Covered |
| 48 | True → ships aggregate (439–440) | `test_an_item_less_segment_reports_its_true_count_under_ships_only` | Covered |
| 49 | False → complement (441) | `test_an_item_bearing_segment_reports_the_complement_under_ships_excluded` | Covered |

### 1.10 `_segment_counts_and_total` (444–534)

| # | Path (lines) | Coverage | Verdict |
|---|---|---|---|
| 50 | contract_type + is_ship_contract lifted for counts (470–471) | `test_segment_counts_read_every_type_with_the_type_filter_lifted` | Covered |
| 51 | Item-less segments read ships flag lifted; item-bearing respect it (507–514, Criterion 1.8) | the two Criterion-1.8 tests (both flag values). Non-lifting of offered-item filters ratified as designed — OD4 (2026-08-08 overnight decision log): no code change; served zero is honest. NOT flagged as a gap. | Covered |
| 52 | Other filters still narrow counts (§6.2) | `test_segment_counts_respect_the_other_filters` | Covered |
| 53 | DISTINCT aggregate iff joined (482–486) | `test_segment_counts_count_contracts_not_joined_item_rows` (joined); unjoined via every default test + equivalence `unfiltered` | Covered |
| 54 | Out-of-enum stored type folds into `unknown` (497–505) | `test_a_contract_type_outside_the_enum_stays_counted_and_reachable`, `test_a_stored_type_outside_the_enum_is_counted_under_unknown` | Covered |
| 55 | Zero-fill over every enum type (495) | `test_segment_counts_are_zero_filled_over_every_contract_type` | Covered |
| 56 | total: selected=None sums everything (520–532) | `sum(segment_counts.values()) == total` assertion; equivalence `unfiltered` | Covered |
| 57 | total: membership judged on FOLDED segment (528–531) | unknown-selection test (total==2 with one folded row) | Covered |
| 58 | total under each ships-flag value / combined with contract_type | equivalence cases `ships-only`, `ships-excluded`, `contract-type-with-ships-only` | Covered |
| 59 | Whole-function equivalence vs flat count, both liveness branches | `test_the_derived_total_equals_the_flat_count_for_the_same_filters` × 13 cases × 2 branches, vacuity-guarded | Covered |

### 1.11 `_observed_coverage` + `_OBSERVED_REGIONS_SQL` (541–572)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 60 | Multi-region walk, ascending ids, as_of = newest across all (569–572) | `test_coverage_reports_every_region_the_corpus_holds` | Covered |
| 61 | Empty corpus → `[]` + `as_of=None` (571 default) | `test_coverage_on_an_empty_corpus_is_empty_rather_than_absent` | Covered |
| 62 | Region with only NULL stamps stays listed, contributes no as_of candidate | `test_a_region_whose_rows_are_all_unstamped_still_counts_as_covered` | Covered |
| 63 | Observed-not-configured semantics | `test_a_configured_but_uningested_region_is_absent_from_coverage` | Covered |
| 64 | Coverage carried onto the empty page | `test_coverage_is_carried_onto_an_empty_page` | Covered |

### 1.12 `_count_unknown_system_excluded` (575–596)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 65 | Residual = same query minus system predicate plus IS NULL | `test_system_ids_matches_resolved_contracts_and_reports_the_residual` | Covered |
| 66 | Absent (None, not 0) when system_ids unset | `test_the_residual_is_absent_when_system_ids_is_not_applied`, wire test | Covered |
| 67 | Counts only rows the OTHER filters kept | `test_the_residual_counts_only_rows_the_other_filters_kept` | Covered |
| 68 | Reported on the empty page (measured before short-circuit) | `test_the_residual_is_still_reported_when_nothing_matched` | Covered |
| 69 | DISTINCT on joined path | `test_the_residual_holds_on_the_item_joined_path` | Covered |

### 1.13 `_fetch_page_joined` (599–638)

| # | Path (lines) | Coverage | Verdict |
|---|---|---|---|
| 70 | min aggregate asc / max aggregate desc as the direction-appropriate representative (614) | `volume_and_ship_name_sort_contracts` 972013 ("Bantam"/"Zealot" straddle "Merlin") — both directions asserted | Covered |
| 71 | nulls_last on joined path for NULLABLE sort (616–617) | ship_name (both directions), reward_per_volume desc (`test_a_new_sort_survives_the_grouped_joined_pagination_path`) | Covered for those two |
| 72 | **nulls_last on joined path for the other four NULLABLE sorts** (buyout, days_to_complete, volume, price under a join) | Simple path covers all six; joined path exercises only ship_name + reward_per_volume. Mechanism is one shared branch, exercised twice with order assertions, so residual risk is low. | GAP — nice-to-have |
| 73 | Non-nullable sort on joined path (price asc + search) | `test_pagination_with_search_returns_full_distinct_pages` (exact order) | Covered |
| 74 | Pagination over grouped ids, no dup/skip across boundaries (618–624) | search, ship_name, and is_bpc pagination tests (SQLA-1/TEST-4) | Covered |
| 75 | contract_id ASC tiebreaker at equal aggregate keys (621) | `test_joined_pagination_tiebreaks_equal_sort_keys_by_contract_id` (service; scope limit candidly documented) + `test_pagination_sorted_by_ship_name_no_duplicates` (plan-level) | Covered |
| 76 | Python-side reorder to id_query order (636–637) | Exact-order assertions on joined-path tests fail without it | Covered (integration) |
| 77 | **Page beyond the last page on the joined path** (page_ids == [] → `IN ()` data query → empty items with total > 0) | No test requests a page past the end while total > 0 on the joined path (nor on the simple path). Response shape for an out-of-range page is unpinned. | GAP — nice-to-have |

### 1.14 `_fetch_page_simple` (641–658) + sort matrix

Per instruction 7, each `SortableContractFields` value × direction is a separate path. NULLABLE_SORTS membership (68–75): buyout, days_to_complete, reward_per_volume, volume, ship_name, price.

| # | Sort × direction | Coverage | Verdict |
|---|---|---|---|
| 78 | price asc / desc + nulls_last both ways | `test_price_sorts_both_ways_and_leaves_unpriced_contracts_last`, `test_sort_by_price_asc`, `test_sorting_by_price_asc` | Covered |
| 79 | buyout asc / desc + nulls_last | `test_buyout_sorts_both_ways_and_leaves_auctions_without_one_last` | Covered |
| 80 | days_to_complete asc / desc + nulls_last | `test_days_to_complete_sorts_both_ways_and_leaves_non_couriers_last` | Covered |
| 81 | reward_per_volume asc / desc + nulls_last; SQL expression ordered differently from both operand columns; zero-volume NULL | `test_reward_per_volume_sorts_both_ways...`, `test_a_zero_volume_courier_sorts_as_unpriced...` | Covered |
| 82 | volume asc / desc + nulls_last | `test_volume_sorts_both_ways_and_leaves_contracts_without_one_last` (OD3 fix evidence) | Covered |
| 83 | ship_name asc / desc + nulls_last (joined) | `test_ship_name_sorts_both_ways_and_leaves_item_less_contracts_last`, API `test_sort_contracts` desc | Covered |
| 84 | date_issued desc (default) | `test_unmapped_sort_falls_back_to_date_issued` asserts exact desc order + tiebreak (via the fallback, which maps to the same column/direction) | Covered |
| 85 | **date_issued asc (explicit)** | No test sends `sort_by=date_issued&sort_direction=asc` and asserts order. | **GAP — correctness** |
| 86 | **date_expired asc / desc** | Zero tests sort by date_expired. This is the "Time left" sort the liveness comment (257–259) names as the default-ascending UI sort — the sort whose interaction with expired rows motivated the expiry predicate. A silent no-op here is exactly the defect class §6.2 acceptance evidence exists for; the newer sorts each got both-direction evidence, this pre-existing one has none. | **GAP — correctness** |
| 87 | **collateral asc / desc** | Zero tests sort by collateral (non-null column, simple order). A courier browser sorting by collateral is a primary use case per `test_contract_response_exposes_collateral`'s own docstring ("filterable and sortable"), yet the sort itself is unasserted. | **GAP — correctness** |
| 88 | Non-NULLABLE sort skips nulls_last (649–650 false branch) | date_issued fallback test (order asserted on non-null column) | Covered |
| 89 | Pagination offset/limit on simple path (652–654) | `test_paginate_contracts` (page 2, size 3, exact ids), `test_pagination` (service) | Covered |

### 1.15 `_category_names` (661–674)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 90 | kind=="category" name map; consumed by list AND detail | `derived_field_contracts` composition name assertions; `test_detail_response_carries_every_item_and_its_blueprint_terms` ("Blueprint" name on detail) | Covered |

### 1.16 `_offered_items` (677–687)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 91 | is_included filter (offered only) | requested-item exclusion asserted in composition (961001: 2 rows not 3) and blueprint tests (954003) | Covered |
| 92 | record_id ordering ("first item" determinism) | Consumed by `_primary_label` named[0]; see row 96 — the ordering itself is only observable when record insertion order differs from record_id order, which no fixture arranges | GAP folded into row 96 |

### 1.17 `_reward_per_volume` (690–698)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 93 | reward None → None; volume 0 → None; volume None → None (696–697) | `test_reward_per_volume_is_null_when_the_division_is_undefined` (all three) | Covered |
| 94 | Normal division (698) | courier row asserts 80_000.0 | Covered |

### 1.18 `_primary_label` (701–724)

| # | Path (lines) | Coverage | Verdict |
|---|---|---|---|
| 95 | Offered ship headline (711–714) | 961001 asserts "Rokh" — **but** the Rokh is also the lowest-record_id named item, so the ship branch and the named[0] fallback give identical answers there | Weak — see row 96 |
| 96 | **Ship OUTRANKS an earlier-record non-ship item** — the reason the branch exists ("an offered ship outranks whatever module happens to come first") | No fixture places a named non-ship item at a lower record_id than the offered ship (`category=="ship"`). Deleting the `ship = next(...)` line and always taking `named[0]` passes every current test. | **GAP — correctness** |
| 97 | named[0] fallback when no item carries `category=="ship"` (713) | `test_complex_filter_api` asserts "Tristan" on an item without category | Covered |
| 98 | Title fallback when nothing named offered (716–717) | 954003 asserts "Wanted: Caracal Blueprint Copy" | Covered |
| 99 | **Blank-string title counts as absent** (`title.strip()`, 716) | Comment says real ESI titles are frequently `""`; no fixture has `title="   "` or `""` falling through to the courier/contract-id branches. | GAP — nice-to-have |
| 100 | Courier with end_location_name (719–721) | 961003 asserts "Courier to Amarr VIII..." | Covered |
| 101 | **Courier without end_location_name → "Courier"** (722) | Executes in `test_reward_per_volume_is_null...` (961101/961102 are title-less couriers with no end name) but no assertion reads their `primary_label`. | GAP — nice-to-have |
| 102 | **Final fallback `f"Contract {id}"`** (724) | 961103 (title=None, item_exchange, no items) exercises it; no assertion reads it. | GAP — nice-to-have |

### 1.19 `_composition` (727–770)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 103 | < 2 offered rows → None (737–738) | single-item, courier, requested-only tests | Covered |
| 104 | Row counts (not quantities), per category incl. None bucket | 961005 / 962401 | Covered |
| 105 | Unnamed known category serves NULL name (749) | 961005 category 42 | Covered |
| 106 | Ordering: count desc for EVERY entry incl. NULL bucket; name asc at ties; unnamed after named (758–764) | `test_composition_orders_every_entry_by_share_then_name`, `test_a_dominant_uncategorized_bucket_leads_the_composition` | Covered |
| 107 | total_volume from contract (769) | 961001 asserts 1500.0 | Covered |
| 108 | **total_volume None branch** (769, volume is None) | 961005 has no volume; test asserts categories + total_item_rows but never `total_volume is None` | GAP — nice-to-have |

### 1.20 `_blueprint_summary` (773–792)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 109 | No copies → None (781–782) | single-item + requested-only tests | Covered |
| 110 | >1 copies → count only (783–784) | `test_auction_row_carries_its_buyout_and_counts_its_copies` (exact null terms + count 2) | Covered |
| 111 | Single copy → full terms (786–792) | 961001 assertion; `test_filter_by_bpc_runs` | Covered |

### 1.21 `_contract_fields` / `_list_item` / `_detail_item` (795–853)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 112 | is_blueprint_copy_contract offered-only derivation (827–829) | mixed-bundle + want-to-buy tests | Covered |
| 113 | Field allowlist: authenticated-route fields never serialize (status, date_completed, is_singleton, raw_quantity) | the three omits-fields tests, swept across all fixture items | Covered |
| 114 | List rows carry no item array | `test_list_rows_carry_no_item_array` | Covered |
| 115 | Detail = row + full item array incl. requested items | `test_detail_response_carries_every_item_and_its_blueprint_terms` | Covered |
| 116 | **Detail items sorted by record_id** (850–852) | Test builds a dict keyed by record_id and asserts the SET; wire order is unasserted ("renders identically on every request" is the stated contract) | GAP — nice-to-have |
| 117 | last_seen_at on the wire | derived-fields test asserts round-trip equality | Covered |

### 1.22 `_live_item_bearing_contracts` (856–870)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 118 | Delisted rows out of readiness population | `test_a_delisted_contract_does_not_drag_the_readiness_ratio` | Covered |
| 119 | Item-less types (courier/loan) out; auction in | `test_only_item_bearing_contract_types_count_in_the_denominator` (both directions — auction degradation asserted) | Covered |
| 120 | **Expired rows out of readiness population** (`date_expired > func.now()`, 867) | No taxonomy-readiness test seeds an EXPIRED stale-version contract and asserts it does not drag the ratio. The delisted sibling is tested; the expiry criterion of the same tuple is not. | **GAP — correctness** |

### 1.23 `_enrichment_is_current` (873–897)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 121 | Ratio threshold, both sides of 0.99 (897) | parametrized `0.995-clears` / `0.95-does-not` | Covered |
| 122 | Denominator includes PENDING and ENRICHMENT_INCOMPLETE rows | `test_contracts_still_awaiting_or_failing_enrichment_stay_in_the_denominator` | Covered |
| 123 | Numerator requires status AND version (889–891) | same test (failed rows deliberately keep the current version) | Covered |
| 124 | Empty corpus → not ready (`live > 0`) | `test_taxonomy_on_a_cold_cache_...` (partial on empty) | Covered (integration) |

### 1.24 `_live_category_ids` (900–917) / `_taxonomy_coverage` (920–939)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 125 | Ratio not current → partial (935–936) | ratio tests | Covered |
| 126 | Live category missing from name cache → partial; fixed → complete (937–938) | `test_a_category_the_name_cache_is_missing_holds_the_signal_at_partial` (both states) | Covered |
| 127 | Category on delisted rows only does not hold the signal | `test_a_category_seen_only_on_delisted_rows_does_not_hold_the_signal` | Covered |
| 128 | NULL category_id excluded from sweep (914) | Implicit in fixtures without taxonomy ids alongside `complete` verdicts (e.g. ratio tests use item-less enriched contracts and still reach `complete`) | Covered |
| 129 | **Short-circuit order: ratio settles before the category sweep runs** (932–934) | Behavioral outcome covered; the cost-motivated ordering itself has no call-order assertion. Reordering is invisible to tests (and harmless to correctness). | GAP — nice-to-have |

### 1.25 `get_taxonomy` (942–982)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 130 | kind split; flat groups each naming their category; name-sorted (reverse-seeded per TEST-12) | `test_taxonomy_serves_name_sorted_flat_lists_...` | Covered |
| 131 | Cold cache → empty lists + partial, no error; route matched ahead of /{contract_id} | `test_taxonomy_on_a_cold_cache_...` | Covered |
| 132 | Coverage measured against the SERVED category list (979–981) | missing-name test asserts `categories == [6]` alongside `partial` | Covered |
| 133 | **Sort tie-break by id at equal names** (959, 971) | No fixture seeds two categories or groups with identical names | GAP — nice-to-have |

### 1.26 `_error_without_bound_parameters` (985–1005)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 134 | Non-StatementError → plain str (998–999) | `test_db_error_logs_failure_and_reraises` (RuntimeError message asserted) | Covered |
| 135 | StatementError → scrubbed render, diagnosis retained (1000–1004) | `test_a_failing_statement_does_not_log_its_bound_search_text` — vacuity-guarded, whole-record assertion (SQLA-4/D12 discipline followed exactly as the pitfall prescribes) | Covered |
| 136 | **`finally` restores prior `hide_parameters`** (1004–1005) | No assertion that `exc.hide_parameters` returns to its prior value after logging (matters if the exception is re-rendered downstream expecting original behavior). | GAP — nice-to-have |

### 1.27 `get_contracts` (1008–1185)

| # | Path (lines) | Coverage | Verdict |
|---|---|---|---|
| 137 | Start log emits length-only search dimension (1024–1041) | `test_no_search_log_site_echoes_the_raw_query_text` (all four sites, whole-record repr scan) | Covered |
| 138 | Full-dimension payload carries type + taxonomy ids (1026–1040 / 1145–1159) | `test_full_dimension_logs_carry_the_type_and_taxonomy_filters` (exact key sets) | Covered |
| 139 | join vs no-join query construction (1047–1052) | §1.1 | Covered |
| 140 | unknown_system_excluded computed iff system_ids, BEFORE short-circuit (1069–1073) | §1.12 rows 66, 68 | Covered |
| 141 | Coverage computed once per request (1077) | §1.11 | Covered |
| 142 | total==0 short-circuit: distinct branch pinned by 4-key vs 11-key log payload (1079–1107) | `test_zero_results_returns_empty_page` — the strongest branch-discrimination test in the suite | Covered |
| 143 | Empty page carries segment_counts + coverage | `test_the_empty_page_still_carries_the_full_segment_counts`, `test_coverage_is_carried_onto_an_empty_page` | Covered |
| 144 | SORT_MAP fallback to date_issued on unmapped key (1111–1114) | `test_unmapped_sort_falls_back_to_date_issued` (model_construct bypass; defensive branch, exact order asserted) | Covered |
| 145 | descending = (sort_direction == desc) (1116) | every both-direction sort test | Covered |
| 146 | joined vs simple fetch dispatch (1118–1121) | §1.13/§1.14 | Covered |
| 147 | Success log key event (1139–1160) | log tests (site 3 of 4) | Covered |
| 148 | Exception path: failure event, scrubbed error, bare re-raise of the ORIGINAL object (1164–1185) | `test_db_error_logs_failure_and_reraises` (`excinfo.value is boom_error`), StatementError scrub test | Covered |

---

## 2. `api/contracts.py`

### 2.1 `list_public_contracts` (33–44)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 149 | `Annotated[ContractFilters, Query()]` binding: id lists as repeated query params, never body (FASTAPI-1) | repeated-param tests for region/system/station/type/group/category + `test_id_list_filters_are_query_params_in_openapi_schema` | Covered |
| 150 | Delegation to service | every API test | Covered (integration) |
| 151 | 422: unknown `contract_type` value (closed enum, §17.8) | `test_filter_by_contract_type` (`barter` → 422) | Covered |
| 152 | **422: `size` bounds (`ge=1, le=100`) — size=0, size=101, size=-1** | No test. This is the ONLY resource cap on an anonymous, corpus-scale query endpoint; if the `le=100` constraint were dropped, `size=100000` would page the whole corpus per request and no test would notice. Note the saved-searches 422 tests validate a DIFFERENT model (SavedSearch payload), not this endpoint's Query binding. | **GAP — security-critical** |
| 153 | **422: `search` min_length=3 — and no max_length exists at all** | No endpoint test sends `search=ab`. Worse (code observation surfaced by the coverage sweep): `ContractFilters.search` declares `min_length=3` but NO `max_length`, so an anonymous caller can bind an arbitrarily long string into the un-indexed double-wildcard ILIKE (`%...%`) across title AND item name — a query-cost lever with no cap and no test that would catch one being added/removed. The short-search 422 is also the only guard against 1-char full-corpus ILIKE scans. | **GAP — security-critical** |
| 154 | **422: `page` `ge=1` — page=0, page=-1** | No test. If the constraint were removed, page=0 produces a negative OFFSET → database error → 500 on trivially malformed anonymous input. | **GAP — correctness** |
| 155 | **422: negative numeric bounds across the six range families** (min/max_price `ge=0`, min/max_collateral `ge=0`, min/max_me `ge=0`, min/max_te `ge=0`, min/max_runs `ge=-1`) | No endpoint tests. (saved-searches covers `min_price=-1` and `min_me=-1` on its own model only.) | **GAP — correctness** |
| 156 | **422: malformed value types — non-integer id-list members (`region_ids=abc`), non-boolean `is_bpc=maybe`, non-numeric prices** | No endpoint tests pin the fail-closed 422 for type-mismatched query values. | **GAP — correctness** |
| 157 | **422: unknown `sort_by` / `sort_direction` values** | No test sends `sort_by=issuer_id` or `sort_direction=sideways`. The enum 422 is the FIRST layer of the arbitrary-column-sort defense; SORT_MAP + fallback (the second layer) IS tested, which is why this is correctness rather than security-critical — but the layer the wire actually exercises is the untested one. | **GAP — correctness** |
| 158 | **Wire-visible error body on an induced read-path 500** | `main.py`'s `generic_exception_handler` returns a constant `{"detail": "An unexpected server error occurred."}` and logs `str(exc)` (scrubbed only because the engine sets `hide_parameters=True` — pinned by `test_db_engine.py` at the RENDER layer). No API-level test drives a failure through `/contracts/` and asserts the response body carries no internals (statement text, bind values, traceback). The repo's parameter-scrubbing rule (SQLA-4/D12) is tested at the log layer; the HTTP surface — the one an anonymous attacker actually sees — has no assertion. | **GAP — security-critical** |

### 2.2 `list_contract_taxonomy` (49–57)

| # | Path | Coverage | Verdict |
|---|---|---|---|
| 159 | Route order ahead of /{contract_id} (would 422 otherwise) | `test_taxonomy_on_a_cold_cache_...` (docstring names this as the proof; a 422 would fail the 200 assertion) | Covered |
| 160 | Delegation + response shape | all taxonomy tests | Covered |

### 2.3 `get_contract` (60–81)

| # | Path (lines) | Coverage | Verdict |
|---|---|---|---|
| 161 | Found → `_detail_item` with category names (79–81) | detail tests (fields, items, derived names) | Covered |
| 162 | Expired contract still served (list/detail asymmetry pinned) | `test_detail_still_serves_an_expired_contract` | Covered |
| 163 | **Not found → 404** (76–77) | **Zero tests.** Grep across the entire test tree finds no request for a nonexistent contract id and no 404 assertion on `/contracts/{id}`. The only user-visible error branch in this file is completely unexercised — the `scalar_one_or_none` / `HTTPException(404)` pair could regress to `scalar_one` (→ 500) or to serving a null body and nothing would fail. | **GAP — correctness** |
| 164 | **Non-integer path param → 422** (`/contracts/abc`) | No test. The taxonomy test's docstring reasons about this behavior but nothing sends a non-integer id. | **GAP — correctness** |
| 165 | **int64-overflow id** (`/contracts/99999999999999999999` — passes Python int parsing, overflows PG BIGINT → DBAPIError → 500) | No test pins whether this returns 404, 422, or a 500; currently it is a driver-error 500 on malformed anonymous input. Fail-closed behavior unpinned. | **GAP — correctness** |
| 166 | Delisted-but-unexpired contract still served by detail (list hides via watermark; detail applies neither predicate) | No dedicated test (the expired sibling is pinned; the delisted asymmetry — same design rationale — is not). | GAP — nice-to-have |

---

## 3. Gap register (summary with severities)

### Security-critical (3)

| ID | Gap | Where |
|----|-----|-------|
| SC-1 | `size` (and implicitly the whole pagination cost cap) has zero 422 tests on the anonymous list endpoint; `le=100` is the only thing standing between a caller and corpus-per-request pages, and its removal is test-invisible. | `schemas/contracts.py:456`, `api/contracts.py:33` (row 152) |
| SC-2 | `search` min_length 422 untested at the endpoint, and the field has NO max_length — unbounded user text binds into a double-wildcard ILIKE over two columns on an anonymous endpoint. Coverage gap + code observation. | `schemas/contracts.py:332–336` (row 153) |
| SC-3 | No API-level test asserts the wire-visible 500 body on a read-path failure contains no internals; the SQLA-4/D12 scrub is pinned at the engine/log layers only, never at the HTTP surface an attacker sees. | `main.py:88–104`, `api/contracts.py` (row 158) |

### Correctness (13)

| ID | Gap | Where |
|----|-----|-------|
| C-1 | `GET /contracts/{id}` 404 branch has zero tests anywhere. | `api/contracts.py:76–77` (row 163) |
| C-2 | Non-integer `/contracts/{id}` 422 untested. | `api/contracts.py:60–63` (row 164) |
| C-3 | int64-overflow contract id → currently a driver 500; behavior unpinned. | `api/contracts.py:60–74` (row 165) |
| C-4 | `min_collateral` filter has zero assertions anywhere (only `max_collateral`, and only in combination). | `contract_service.py:286–287` (row 30) |
| C-5 | `sort_by=date_expired` ("Time left") — both directions untested; the silent-no-op-sort defect class F008 §6.2 names. | `contract_service.py:43`, SORT_MAP (row 86) |
| C-6 | `sort_by=collateral` — both directions untested. | `contract_service.py:45` (row 87) |
| C-7 | `sort_by=date_issued&sort_direction=asc` untested (desc pinned only via the fallback test). | row 85 |
| C-8 | `still_listed_by_esi` case-`else_` correlated fallback under a NON-empty config (config-drift path) has no row-level regression test; verified once manually per the 2026-08-02 perf audit. | `contract_service.py:159–168` (row 11) |
| C-9 | `_primary_label` ship-priority branch not distinguishably tested — no fixture where the offered ship has a higher record_id than a named non-ship item; `named[0]` alone passes every test. | `contract_service.py:710–714` (row 96) |
| C-10 | Expiry criterion of `_live_item_bearing_contracts` (readiness denominator) untested — delisted sibling pinned, expired one not. | `contract_service.py:867` (row 120) |
| C-11 | `page=0` / negative page 422 untested (constraint removal → negative OFFSET → 500). | `schemas/contracts.py:455` (row 154) |
| C-12 | Negative-bound 422s untested across all six numeric range families at the endpoint. | `schemas/contracts.py:338–398` (row 155) |
| C-13 | Malformed value types (non-int id-list members, non-bool `is_bpc`) and unknown `sort_by`/`sort_direction` 422s untested at the endpoint. | rows 156–157 |

### Nice-to-have (10)

| ID | Gap | Where |
|----|-----|-------|
| N-1 | Out-of-range page (beyond last) with total > 0 — empty-`IN` joined branch and simple branch both unpinned. | row 77 |
| N-2 | Joined-path `nulls_last` exercised for only 2 of 6 NULLABLE sorts (shared branch, low residual risk). | rows 71–72 |
| N-3 | `_composition.total_volume is None` branch unasserted. | row 108 |
| N-4 | `_primary_label` "Courier" (no destination) and `Contract {id}` fallbacks execute in fixtures but are never read. | rows 101–102 |
| N-5 | Blank-string title (`"  "`) treated as absent — untested despite the comment calling it the common ESI shape. | row 99 |
| N-6 | Detail item array record_id ORDER unasserted (set-only assertion). | row 116 |
| N-7 | Taxonomy sort tie-break by id at equal names unasserted. | row 133 |
| N-8 | `_taxonomy_coverage` short-circuit ordering (cost property) unasserted. | row 129 |
| N-9 | `_error_without_bound_parameters` restore-after-render (`finally`) unasserted. | row 136 |
| N-10 | Delisted-but-unexpired contract reachable via detail (asymmetry sibling of the pinned expired case) unasserted; also `min_runs=-1` boundary admission (`ge=-1` vs ESI-3 "never sends -1") unasserted. | rows 166, `schemas/contracts.py:351–366` |

---

## 4. What is demonstrably strong (for calibration)

The F008-era surface is exceptionally well covered: both liveness branches parametrized over every delisting case; the derived-total equivalence matrix (13 filter shapes × 2 watermark branches, vacuity-guarded); three-way partition identities for every range family; both directions asserted for all six nullable sorts with NULL placement; log scrubbing pinned at four sites with whole-record assertions and a vacuity guard; the empty-page short-circuit discriminated by log-payload shape rather than response shape. The gaps concentrate in (a) the pre-F008 legacy surface (detail 404, collateral/date sorts, min_collateral) and (b) endpoint-level input validation, where exactly one of ~20 constraint paths (contract_type) has a wire-level 422 test.
