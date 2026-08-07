# ABOUTME: The explicit manifest of ESI endpoints and response fields Hangar Bay consumes,
# ABOUTME: each field annotated with the code that reads it so a drift report names the consumer.
"""What Hangar Bay actually depends on in EVE's ESI API.

This is the projection lens. The monitor compares only what is listed here, so the
full 182-path spec's constant churn in areas we do not consume produces no noise.

Two path spaces exist and they are not the same:

*   **Call path** — what `ESIClient` puts on the wire, version-prefixed (`/v1/...`,
    `/v3/...`) per the pinning rule in docs/pitfalls/implementation-pitfalls.md ESI-1.
*   **Spec path** — the key under `paths` in `https://esi.evetech.net/meta/openapi.json`,
    which is **unversioned**. ESI replaced route versioning with the
    `X-Compatibility-Date` header, so the meta spec documents one shape per route and
    selects between historical shapes by date rather than by URL segment.

`spec_path` is therefore the lookup key and `call_path` is what a failure message
should quote back, because that is the string a reader will grep for.

`consumed_fields` lists only fields our code actually reads, each mapped to the reader.
Fields the spec carries that we ignore are still captured by the projection (so their
arrival or departure is visible) but a change to them is not attributed to a consumer.

`known_absent_fields` records fields our code reads that the spec does **not** carry —
the ESI-3 family of traps. They are declared rather than silently tolerated so that
(a) nobody re-derives the same discovery by hand, and (b) if ESI ever starts sending
one, the monitor says so, because a dead filter suddenly becoming implementable is
news worth having.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class KnownAbsentField:
    """A field our code reads that the public spec does not document.

    `consequence` states what the code silently does today, so a reader deciding
    whether to care does not have to go and work it out again.
    """

    name: str
    consumer: str
    consequence: str


@dataclass(frozen=True)
class Endpoint:
    """One ESI operation Hangar Bay calls, and what it depends on inside it."""

    spec_path: str
    method: str
    call_path: str
    caller: str
    consumed_fields: dict[str, str] = field(default_factory=dict)
    known_absent_fields: tuple[KnownAbsentField, ...] = ()

    @property
    def key(self) -> str:
        """Stable snapshot key: `GET /contracts/public/{region_id}`."""
        return f"{self.method.upper()} {self.spec_path}"


MANIFEST: tuple[Endpoint, ...] = (
    Endpoint(
        spec_path="/contracts/public/{region_id}",
        method="get",
        call_path="/v1/contracts/public/{region_id}/",
        caller="core/esi_client_class.py ESIClient.get_public_contracts",
        consumed_fields={
            "contract_id": "background_aggregation._build_contract_rows -> Contract.contract_id (primary key)",
            "issuer_id": "background_aggregation._build_contract_rows -> Contract.issuer_id, and name resolution",
            "issuer_corporation_id": "background_aggregation._build_contract_rows -> Contract.issuer_corporation_id",
            "type": "background_aggregation._build_contract_rows -> Contract.type; _fetch_item_rows gates item enrichment on item_exchange/auction",
            "date_issued": "background_aggregation._build_contract_rows -> Contract.date_issued",
            "date_expired": "background_aggregation._build_contract_rows -> Contract.date_expired",
            "start_location_id": "background_aggregation._build_contract_rows -> Contract.start_location_id, and name resolution",
            "end_location_id": "background_aggregation._build_contract_rows -> Contract.end_location_id, and the destination half of both name and system resolution (Contract.end_location_name, Contract.end_location_system_id)",
            "title": "background_aggregation._build_contract_rows -> Contract.title",
            "for_corporation": "background_aggregation._build_contract_rows -> Contract.for_corporation",
            "price": "background_aggregation._build_contract_rows -> Contract.price (sortable, filterable)",
            "collateral": "background_aggregation._build_contract_rows -> Contract.collateral",
            "reward": "background_aggregation._build_contract_rows -> Contract.reward",
            "volume": "background_aggregation._build_contract_rows -> Contract.volume",
            "buyout": "background_aggregation._build_contract_rows -> Contract.buyout; the auction-segment column and the buyout sort (F008)",
            "days_to_complete": "background_aggregation._build_contract_rows -> Contract.days_to_complete; the courier-segment column and the days_to_complete sort (F008)",
        },
        known_absent_fields=(
            KnownAbsentField(
                name="status",
                consumer="background_aggregation._build_contract_rows -> Contract.status (non-null column, indexed by ix_contracts_type_status); no longer on the wire",
                consequence="defaults to the literal 'unknown' on every row, so the column and its index carry one constant value; dropped from ContractSchema in PR #115 and re-fills only when a user's own authenticated contracts are ingested",
            ),
            KnownAbsentField(
                name="date_completed",
                consumer="background_aggregation._build_contract_rows -> Contract.date_completed; no longer on the wire",
                consequence="always NULL — a public contract is by definition outstanding; dropped from ContractSchema in PR #115 and re-fills only under authenticated ingestion",
            ),
        ),
    ),
    Endpoint(
        spec_path="/contracts/public/items/{contract_id}",
        method="get",
        call_path="/v1/contracts/public/items/{contract_id}/",
        caller="core/esi_client_class.py ESIClient.get_contract_items",
        consumed_fields={
            "record_id": "background_aggregation._fetch_item_rows -> ContractItem.record_id (primary key)",
            "type_id": "background_aggregation._fetch_item_rows -> ContractItem.type_id; drives the /universe/types enrichment fan-out",
            "quantity": "background_aggregation._fetch_item_rows -> ContractItem.quantity",
            "is_included": "background_aggregation._fetch_item_rows -> ContractItem.is_included; _enrich_items_and_find_ships lets only included items set the ship flag, and every item-level filter is an offered-items EXISTS",
            "is_blueprint_copy": "background_aggregation._fetch_item_rows -> ContractItem.is_blueprint_copy; contract_service._has_blueprint_copy_item backs the is_bpc filter",
            "runs": "background_aggregation._fetch_item_rows -> ContractItem.runs; blueprint-copy display and the min_runs/max_runs filter (F008)",
            "material_efficiency": "background_aggregation._fetch_item_rows -> ContractItem.material_efficiency; blueprint display and the min_me/max_me filter (F008)",
            "time_efficiency": "background_aggregation._fetch_item_rows -> ContractItem.time_efficiency; blueprint display and the min_te/max_te filter (F008)",
            "item_id": "background_aggregation._fetch_item_rows -> ContractItem.item_id; the dynamic-item join key, absent on requested items (F008)",
        },
        known_absent_fields=(
            KnownAbsentField(
                name="raw_quantity",
                consumer="background_aggregation._fetch_item_rows -> ContractItem.raw_quantity; read by the min_runs/max_runs filter in contract_service",
                consequence="always NULL, so min_runs/max_runs match zero rows — this field is on the AUTHENTICATED character/corporation item routes only (ESI-3)",
            ),
            KnownAbsentField(
                name="is_singleton",
                consumer="background_aggregation._fetch_item_rows -> ContractItem.is_singleton (non-null column, exposed as ContractItemSchema.is_singleton)",
                consequence="defaults to False on every row — same authenticated-route confusion as raw_quantity",
            ),
        ),
    ),
    Endpoint(
        spec_path="/universe/types/{type_id}",
        method="get",
        call_path="/v3/universe/types/{type_id}/",
        caller="core/esi_client_class.py ESIClient.get_universe_type",
        consumed_fields={
            "name": "background_aggregation._enrich_items_and_find_ships -> ContractItem.type_name (the searchable ship name)",
            "group_id": "background_aggregation._enrich_items_and_find_ships -> the /universe/groups fan-out that decides the ship flag, and ContractItem.group_id, which backs the group filter and the taxonomy option list",
            "market_group_id": "background_aggregation._enrich_items_and_find_ships -> ContractItem.market_group_id",
        },
    ),
    Endpoint(
        spec_path="/universe/groups/{group_id}",
        method="get",
        call_path="/v1/universe/groups/{group_id}/",
        caller="core/esi_client_class.py ESIClient.get_universe_group",
        consumed_fields={
            "category_id": "background_aggregation._enrich_items_and_find_ships -> compared against SHIP_CATEGORY_ID, which decides whether a contract is a ship contract (the product's default view), and ContractItem.category_id, which backs the category filter; _upsert_taxonomy_names also stores it as EsiTaxonomyCache.parent_category_id and drives the /universe/categories fan-out",
            "name": "background_aggregation._upsert_taxonomy_names -> EsiTaxonomyCache row for kind='group'; the label of every group option in the taxonomy list",
        },
    ),
    Endpoint(
        spec_path="/universe/categories/{category_id}",
        method="get",
        call_path="/v1/universe/categories/{category_id}/",
        caller="core/esi_client_class.py ESIClient.get_universe_category",
        consumed_fields={
            "name": "background_aggregation._upsert_taxonomy_names -> EsiTaxonomyCache row for kind='category'; the label of every category option in the taxonomy list, fetched cache-first so steady state calls this route zero times",
        },
    ),
    Endpoint(
        spec_path="/universe/names",
        method="post",
        call_path="/v3/universe/names/",
        caller="core/esi_client_class.py ESIClient.resolve_ids_to_names",
        consumed_fields={
            "id": "esi_client_class.resolve_ids_to_names -> the id->name map key",
            "name": "esi_client_class.resolve_ids_to_names -> Contract.issuer_name / issuer_corporation_name / start_location_name / end_location_name",
        },
    ),
    Endpoint(
        spec_path="/universe/ids",
        method="post",
        call_path="/v1/universe/ids/",
        caller="core/esi_client_class.py ESIClient.resolve_names",
        consumed_fields={
            "inventory_types": "watchlist_service resolves a watched ship name to a type id through this category; an unmatched name yields 200 with the category absent",
        },
    ),
    Endpoint(
        spec_path="/universe/stations/{station_id}",
        method="get",
        call_path="/v2/universe/stations/{station_id}/",
        caller="core/esi_client_class.py ESIClient.get_universe_station",
        consumed_fields={
            # The whole reason the route is called. ESI's public contract payload
            # carries a location id and no system id, so without this the system_ids
            # filter has nothing to match — its disappearance would leave every
            # start_location_system_id NULL while the ingestion kept reporting success.
            "system_id": "background_aggregation._resolve_station_systems -> Contract.start_location_system_id, which backs the system_ids filter, and Contract.end_location_system_id, the courier destination",
        },
    ),
    Endpoint(
        spec_path="/universe/regions",
        method="get",
        call_path="/v1/universe/regions/",
        caller="app/frontend/web/scripts/generate-regions.mjs (build-time codegen for the region filter)",
        consumed_fields={},
    ),
    Endpoint(
        spec_path="/universe/regions/{region_id}",
        method="get",
        call_path="/v1/universe/regions/{region_id}/",
        caller="app/frontend/web/scripts/generate-regions.mjs (build-time codegen for the region filter)",
        consumed_fields={
            "region_id": "generate-regions.mjs -> the value of each option in src/features/contracts/regions.ts",
            "name": "generate-regions.mjs -> the label of each option in src/features/contracts/regions.ts",
        },
    ),
)

# Not here, and deliberately: /universe/structures/{structure_id}. Contracts started at
# player-owned structures keep a NULL system, because that route requires the
# esi-universe.read_structures.v1 scope and 403s for structures the token's character
# cannot dock at — there is no tokenless equivalent. If it is ever added, note that it
# names the field `solar_system_id`, NOT the `system_id` the station route sends. Copying
# the station entry unchanged would read an absent key, write NULL, and look like it
# worked — the ESI-3 shape exactly.
