import asyncio
import time
from sqlalchemy import and_, case, func, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import aliased, selectinload

from ..core.config import get_settings
from ..core.logging import get_logger, log_key_event
from ..models.contracts import Contract, ContractItem, EsiTaxonomyCache
from ..schemas.contracts import (
    BlueprintSummary,
    CompositionCategory,
    CompositionSummary,
    ContractDetailSchema,
    ContractFilters,
    ContractItemSchema,
    ContractListItemSchema,
    ContractListResponse,
    ContractType,
    CoverageInfo,
    SortDirection,
    SortableContractFields,
)

# Initialize logger for this module
logger = get_logger(__name__)

# Distinct alias so the per-region watermark subquery can reference the contracts table
# without colliding with the outer query's own reference to it.
_ContractWatermark = aliased(Contract)

# This SORT_MAP is a critical security feature. It prevents arbitrary column sorting
# by mapping API-facing sort keys to the actual, safe SQLAlchemy model columns.
SORT_MAP = {
    SortableContractFields.date_issued: Contract.date_issued,
    SortableContractFields.date_expired: Contract.date_expired,
    SortableContractFields.price: Contract.price,
    SortableContractFields.collateral: Contract.collateral,
    SortableContractFields.volume: Contract.volume,
    # Note: Sorting by ship_name joins the items table.
    SortableContractFields.ship_name: ContractItem.type_name,
}


def _needs_item_join(filters: ContractFilters) -> bool:
    """
    Determine if a JOIN on the ContractItem table is necessary. A join is
    required if we need to filter or sort on item attributes.
    """
    return bool(
        filters.search
        or filters.type_ids
        # Add sorting by ship name to the condition
        or filters.sort_by == SortableContractFields.ship_name
    )
    # is_bpc and the runs/ME/TE ranges are deliberately absent: each asks a question
    # about the contract as a whole ("does it hold an item like this?"), which a
    # correlated EXISTS answers without multiplying rows. See
    # _has_blueprint_copy_item and _offered_item_range_exists.


def still_listed_by_esi():
    """Is this contract still present in ESI's public list?

    Expiry only catches contracts that ran out of time; a contract that was ACCEPTED
    disappears from ESI's public list while keeping a future date_expired, so it survives
    the expiry predicate and would go on being offered for up to two weeks. Ingestion
    restamps last_seen_at on every sighting, so a contract is present when its stamp
    equals the newest stamp IN ITS OWN REGION.

    Per-region rather than global, deliberately: if one region's ESI fetch fails, nothing in
    it is restamped, and judging it against another region's fresher watermark would erase
    every contract that region holds in one go. A stalled region simply keeps its own
    watermark. If ingestion stops entirely, no watermark advances and everything stays
    visible — stale data with a staleness signal beats an empty site.

    NULL is visible: rows predating this column have no stamp, and hiding them would blank
    the site between the migration and the first run. The migration backfills them anyway.

    Shared with the watchlist matcher so "still on offer" has one definition. The tradeoff
    the shared definition accepts: a contract that momentarily drops out of an ESI page —
    an ingestion gap, a partial fetch that still restamped part of its region — reads as
    gone, so a watchlist alert for it can be missed. That is the better failure. The
    alternative is alerting on a contract someone already bought for as long as two weeks,
    which sends the reader to a dead listing over and over and teaches them the alerts are
    noise; a missed alert costs one opportunity and leaves the feature trustworthy.

    The watermark written correlated to each row is the same value for every row of a
    region, and PostgreSQL re-derives it once per candidate row: 61,874 index probes for
    one unfiltered list request, ~5s of a 6s query on the production instance. Since the
    regions ingestion refreshes are known up front, their watermarks are emitted as
    UNCORRELATED subqueries — one index probe each, evaluated once for the whole query —
    and the correlated form is kept as the fallback for any other region.

    AGGREGATION_REGION_IDS is therefore an OPTIMIZATION HINT, never a semantic input: the
    `case` guarantees a row whose region is not configured is judged by exactly the
    predicate it is judged by today. Config drift changes which rows take the fast path,
    never which rows are visible — verified against the production corpus by a both-way
    EXCEPT under a deliberately wrong configuration. See
    docs/perf-audits/2026-08-02-contract-list-watermark-subquery.md.
    """
    newest_in_region = (
        select(func.max(_ContractWatermark.last_seen_at))
        .where(_ContractWatermark.start_location_region_id == Contract.start_location_region_id)
        .correlate(Contract)
        .scalar_subquery()
    )
    unstamped_or_current = or_(
        Contract.last_seen_at.is_(None), Contract.last_seen_at >= newest_in_region
    )

    ingested_region_ids = get_settings().AGGREGATION_REGION_IDS
    if not ingested_region_ids:
        return unstamped_or_current

    at_a_known_regions_watermark = or_(
        *[
            and_(
                Contract.start_location_region_id == region_id,
                Contract.last_seen_at >= _newest_in(region_id),
            )
            for region_id in ingested_region_ids
        ]
    )
    return or_(
        Contract.last_seen_at.is_(None),
        case(
            (
                Contract.start_location_region_id.in_(ingested_region_ids),
                at_a_known_regions_watermark,
            ),
            else_=Contract.last_seen_at >= newest_in_region,
        ),
    )


def _newest_in(region_id: int):
    """The newest ingestion stamp in one named region, as an uncorrelated subquery.

    Uncorrelated is the whole point: with the region a literal rather than a reference to
    the outer row, PostgreSQL hoists this to an InitPlan and runs it once per query — an
    index-only probe on ix_contracts_region_last_seen — instead of once per candidate row.
    """
    watermark_source = aliased(Contract)
    return (
        select(func.max(watermark_source.last_seen_at))
        .where(watermark_source.start_location_region_id == region_id)
        .scalar_subquery()
    )


def _has_blueprint_copy_item():
    """Correlated EXISTS: does this contract carry an item that is a blueprint copy?

    is_bpc classifies CONTRACTS, so it has to be evaluated per contract rather than
    per joined item row. Applied to a joined row, "true" and "not true" are both
    satisfiable by the same contract — a bundle holding a copy alongside an ordinary
    item has an item matching each — so the two branches would overlap instead of
    partitioning the corpus.

    Expressed once and negated for the false branch, so the branches are exact
    complements by construction rather than by two predicates kept in agreement.

    Offered items only (§3.1): a want-to-buy ad asking for a copy offers none, and
    matching it here would put it in front of every buyer browsing copies for sale.
    This is the same rule the served is_blueprint_copy_contract flag applies, so the
    filter and the flag agree by construction.
    """
    return (
        select(ContractItem.record_id)
        .where(
            ContractItem.contract_id == Contract.contract_id,
            ContractItem.is_included.is_(True),
            # ESI sends is_blueprint_copy only for actual copies, so the column is
            # True-or-NULL and NULL means "not a copy" (pitfall ESI-3).
            ContractItem.is_blueprint_copy.is_(True),
        )
        .correlate(Contract)
        .exists()
    )


def _offered_item_range_exists(column, minimum, maximum):
    """Contract-level classification: at least one OFFERED item whose `column`
    satisfies every supplied bound (§3.1).

    One EXISTS per filter family, holding both of that family's bounds, so the
    bounds compose per ITEM rather than per contract: a contract offering a copy at
    ME 5 and another at ME 15 does not satisfy min_me=10&max_me=12, because no
    single copy sits inside that window. Two separate EXISTS would match it and
    hand a buyer looking for one copy in a band a contract that holds none.

    Separate families stay separate expressions, deliberately: different families
    may be satisfied by different items, so ME and runs bounds can land on two
    different copies of the same contract.

    Offered items only, the same rule the boolean is_bpc family applies: a
    want-to-buy ad asking for a 20-run copy offers nobody a 20-run copy.

    NULL satisfies nothing in either direction. ESI omits `runs` entirely on a
    blueprint original rather than sending -1 (ESI-3), so an original is absent
    from both min_runs and max_runs results — absence is not zero.
    """
    conditions = [
        ContractItem.contract_id == Contract.contract_id,
        ContractItem.is_included.is_(True),
    ]
    if minimum is not None:
        conditions.append(column >= minimum)
    if maximum is not None:
        conditions.append(column <= maximum)
    return (
        select(ContractItem.record_id).where(*conditions).correlate(Contract).exists()
    )


def _apply_contract_filters(query, filters: ContractFilters):
    """Apply the contract-level filters, narrowing the results."""
    # 0. Liveness. A contract past date_expired cannot be accepted in game, so listing
    # it wastes a result slot — and because "Time left" sorts ascending by default, every
    # dead contract lands ahead of every live one, filling the first page with rows nobody
    # can act on. Applied HERE, not at a call site, so the predicate reaches the count query
    # and both fetch paths alike; on only one of them, `total` disagrees with the pages
    # (SQLA-1's failure shape). func.now() evaluates on the database clock, so the cutoff
    # cannot drift with application/container clock skew — it is NOT about index usability,
    # since a bound timezone-aware parameter would be equally indexable.
    # The detail endpoint deliberately does NOT filter this way: a shared link outlives the
    # contract it points at, and 404-ing yesterday's link reads as a broken site.
    query = query.filter(Contract.date_expired > func.now())

    # 0b. Delisted contracts — a contract accepted or withdrawn keeps a future date_expired
    # and survives the expiry predicate above. See still_listed_by_esi for the per-region
    # watermark and why it is per-region.
    query = query.filter(still_listed_by_esi())

    # 1. Text search (on contract title or item name)
    if filters.search:
        search_term = f"%{filters.search}%"
        # This OR condition requires the join to be present.
        query = query.filter(
            or_(
                Contract.title.ilike(search_term),
                ContractItem.type_name.ilike(search_term),
            )
        )

    # 2. Price and Collateral filters
    if filters.min_price is not None:
        query = query.filter(Contract.price >= filters.min_price)
    if filters.max_price is not None:
        query = query.filter(Contract.price <= filters.max_price)
    if filters.min_collateral is not None:
        query = query.filter(Contract.collateral >= filters.min_collateral)
    if filters.max_collateral is not None:
        query = query.filter(Contract.collateral <= filters.max_collateral)

    # 2b. Contract-level flags (indexed column; no item join required)
    if filters.is_ship_contract is not None:
        query = query.filter(Contract.is_ship_contract == filters.is_ship_contract)

    # Contract.type leads ix_contracts_type_status, so the composite serves a
    # type-only predicate as a prefix; no companion index is needed.
    if filters.contract_type:
        query = query.filter(
            Contract.type.in_([t.value for t in filters.contract_type])
        )

    # 2c. Blueprint-copy classification. "Contains a copy" and its negation, so a
    # contract bundling a copy with ordinary items counts as a BPC contract and
    # appears in exactly one of the two branches.
    if filters.is_bpc is not None:
        has_copy = _has_blueprint_copy_item()
        query = query.filter(has_copy if filters.is_bpc else ~has_copy)

    # 3. Location filters
    query = _apply_location_filters(query, filters)

    return query


def _apply_location_filters(query, filters: ContractFilters):
    """Narrow to the requested regions, solar systems, and stations.

    system_ids has partial coverage: ingestion resolves start_location_system_id for
    NPC stations through the public /universe/stations/ route, but player-owned
    structures have no tokenless location→system route and keep a NULL system, so
    their contracts can never match. _count_unknown_system_excluded measures exactly
    that shortfall per query, so callers can report it rather than absorb it.
    """
    if filters.region_ids:
        query = query.filter(Contract.start_location_region_id.in_(filters.region_ids))
    if filters.system_ids:
        query = query.filter(Contract.start_location_system_id.in_(filters.system_ids))
    if filters.station_ids:
        query = query.filter(Contract.start_location_id.in_(filters.station_ids))

    return query


def _apply_item_filters(query, filters: ContractFilters):
    """Apply the Contract Item specific filters."""
    if filters.type_ids:
        query = query.filter(ContractItem.type_id.in_(filters.type_ids))
    # Blueprint attribute ranges. Each family is one correlated EXISTS over the
    # contract's offered items, so it asks a question about the CONTRACT and its
    # own bounds land on a single item (§3.1, SQLA-3).
    if filters.min_runs is not None or filters.max_runs is not None:
        query = query.filter(
            _offered_item_range_exists(
                ContractItem.runs, filters.min_runs, filters.max_runs
            )
        )
    if filters.min_me is not None or filters.max_me is not None:
        query = query.filter(
            _offered_item_range_exists(
                ContractItem.material_efficiency, filters.min_me, filters.max_me
            )
        )
    if filters.min_te is not None or filters.max_te is not None:
        query = query.filter(
            _offered_item_range_exists(
                ContractItem.time_efficiency, filters.min_te, filters.max_te
            )
        )

    return query


async def _count_distinct_contracts(db: AsyncSession, query) -> int:
    """
    To get an accurate total count of matching *contracts* (not items),
    we must count the distinct contract_ids from our filtered query.
    This is crucial because the join can create duplicate contract rows.
    """
    count_subquery = select(query.subquery().c.contract_id).distinct().subquery()
    count_query = select(func.count()).select_from(count_subquery)

    total_result = await db.execute(count_query)
    return total_result.scalar_one()


# Contract types ESI never returns items for. The ship flag is derived from items,
# so a contract of one of these types is never a ship contract — which is why their
# segment counts are read with the ships-only filter lifted (Criterion 1.8).
_ITEMLESS_CONTRACT_TYPES = frozenset({
    ContractType.courier.value,
    ContractType.loan.value,
    ContractType.unknown.value,
})


def _count_under_ships_filter(
    all_matching: int, ships_matching: int, is_ship_contract: bool | None
) -> int:
    """Pick the aggregate the ships-only filter selects.

    is_ship_contract is NOT NULL on the model, so the two aggregates partition the
    group and the false branch is the complement rather than a third count.
    """
    if is_ship_contract is None:
        return all_matching
    if is_ship_contract:
        return ships_matching
    return all_matching - ships_matching


async def _segment_counts_and_total(
    db: AsyncSession, filters: ContractFilters, needs_item_join: bool
) -> tuple[dict[str, int], int]:
    """Per-type contract counts and the page total, from one grouped statement.

    The counts label the segment controls, so they answer a different question from
    the page: "how many would I see over there", not "how many am I seeing". That
    means contract_type is lifted (a segment must report its own population while
    the reader stands on another one) and, per Criterion 1.8, so is the ships-only
    flag for the types ESI returns no items for — a Courier (0) that becomes
    Courier (115) the instant it is clicked is the silent-filter-no-op defect
    wearing a numeral. Every OTHER filter still applies (§6.2), or the labels
    advertise results the list cannot show.

    `total` is derived from the same rows rather than fetched by a second aggregate:
    at corpus scale the flat count is the expensive part of a list request, and
    running it alongside a grouped count would double the worst path. It sums only
    the types the caller actually selected, under the aggregate their actual
    ships-only filter selects — the total is never lifted.

    The query is rebuilt from scratch the way _count_unknown_system_excluded rebuilds
    its residual, so every filter reaches it through _apply_contract_filters /
    _apply_item_filters and a filter added to neither cannot silently desynchronize
    the counts from the page. The join need is computed from the ORIGINAL filters;
    lifting two contract-level predicates cannot change it.
    """
    lifted = filters.model_copy(
        update={"contract_type": None, "is_ship_contract": None}
    )
    query = select(Contract)
    if needs_item_join:
        query = query.outerjoin(ContractItem)
    query = _apply_contract_filters(query, lifted)
    query = _apply_item_filters(query, lifted)

    # DISTINCT only where the join can spread one contract over several rows
    # (SQLA-1). Without it the primary key already gives one row per contract, and
    # the DISTINCT sort is pure cost on the unjoined path every default request takes.
    matched = (
        func.count(func.distinct(Contract.contract_id))
        if needs_item_join
        else func.count(Contract.contract_id)
    )
    grouped = query.with_only_columns(
        Contract.type,
        matched,
        matched.filter(Contract.is_ship_contract.is_(True)),
    ).group_by(Contract.type)

    rows = (await db.execute(grouped)).all()

    all_by_segment = {contract_type.value: 0 for contract_type in ContractType}
    ships_by_segment = dict.fromkeys(all_by_segment, 0)
    for stored_type, all_matching, ships_matching in rows:
        # Contract.type is an unconstrained string written straight from ESI, so a
        # type added after this enum was written is storable. It folds into
        # "unknown" rather than dropping out of the sum: Criterion 1.1 requires such
        # a contract to stay counted and reachable, and a total short of the corpus
        # would also fire the empty-page short-circuit while rows exist.
        segment = stored_type if stored_type in all_by_segment else ContractType.unknown.value
        all_by_segment[segment] += all_matching
        ships_by_segment[segment] += ships_matching

    segment_counts = {
        segment: _count_under_ships_filter(
            all_by_segment[segment],
            ships_by_segment[segment],
            None if segment in _ITEMLESS_CONTRACT_TYPES else filters.is_ship_contract,
        )
        for segment in all_by_segment
    }

    # Summed over the raw stored types, not the folded segments: the page query
    # matches contract_type against the stored string, so a type outside the enum is
    # included when nothing was selected and excluded when "unknown" was.
    selected = (
        {contract_type.value for contract_type in filters.contract_type}
        if filters.contract_type
        else None
    )
    total = sum(
        _count_under_ships_filter(all_matching, ships_matching, filters.is_ship_contract)
        for stored_type, all_matching, ships_matching in rows
        if selected is None or stored_type in selected
    )

    return segment_counts, total


# Loose index scan: SELECT DISTINCT over start_location_region_id is a 600ms
# full index scan on the production corpus (perf audit 2026-08-02 §4 — PG18's
# btree skip scan does not engage). The recursive CTE walks one index probe per
# distinct region instead. as_of is the newest ingestion stamp across them.
_OBSERVED_REGIONS_SQL = text("""
    WITH RECURSIVE regions(region_id) AS (
        SELECT min(start_location_region_id) FROM contracts
        UNION ALL
        SELECT (SELECT min(start_location_region_id) FROM contracts
                WHERE start_location_region_id > regions.region_id)
        FROM regions WHERE regions.region_id IS NOT NULL
    )
    SELECT r.region_id,
           (SELECT max(c.last_seen_at) FROM contracts c
             WHERE c.start_location_region_id = r.region_id) AS newest
    FROM regions r WHERE r.region_id IS NOT NULL
""")


async def _observed_coverage(db: AsyncSession) -> CoverageInfo:
    """Which regions the corpus holds, read off the rows themselves.

    Never from Settings.AGGREGATION_REGION_IDS: that states what we mean to ingest,
    and for the whole ingestion window after a coverage change it names a region
    holding nothing — a reader told that region is covered and shown an empty page
    learns the wrong thing about both.

    A region with rows but no stamps yet contributes no candidate for as_of, so the
    freshest real stamp still wins and a corpus with none reports None rather than
    claiming freshness it cannot support.
    """
    rows = (await db.execute(_OBSERVED_REGIONS_SQL)).all()
    return CoverageInfo(
        ingested_region_ids=sorted(region_id for region_id, _ in rows),
        as_of=max((newest for _, newest in rows if newest is not None), default=None),
    )


async def _count_unknown_system_excluded(
    db: AsyncSession, filters: ContractFilters, needs_item_join: bool
) -> int:
    """How many contracts the system_ids filter dropped for want of a known system.

    The same query the caller ran, minus the system predicate and plus "the system is
    unknown" — so the figure counts exactly the rows the user's OTHER criteria selected
    and only the system filter removed. Counting every system-less contract in the
    corpus instead would answer a question nobody asked.

    Costs one additional COUNT, and only when system_ids is applied. It reuses
    _count_distinct_contracts, so the joined path counts contracts rather than
    duplicated joined rows (SQLA-1).
    """
    residual_filters = filters.model_copy(update={"system_ids": None})
    query = select(Contract)
    if needs_item_join:
        query = query.outerjoin(ContractItem)
    query = _apply_contract_filters(query, residual_filters)
    query = _apply_item_filters(query, residual_filters)
    query = query.filter(Contract.start_location_system_id.is_(None))
    return await _count_distinct_contracts(db, query)


async def _fetch_page_joined(
    db: AsyncSession,
    query,
    filters: ContractFilters,
    sort_column,
    descending: bool,
) -> list[Contract]:
    # Paginating the joined query directly would offset/limit over
    # joined (duplicated) rows, producing short pages and contracts
    # skipped or repeated across page boundaries. Paginate over
    # distinct contract IDs first, then load that page's contracts.
    # Ordering uses an aggregate of the sort column (min/max picks
    # the sort-direction-appropriate representative when a contract
    # has multiple items) with contract_id as a deterministic
    # tiebreaker.
    sort_aggregate = func.max(sort_column) if descending else func.min(sort_column)
    order_expr = sort_aggregate.desc() if descending else sort_aggregate.asc()
    id_query = (
        query.with_only_columns(Contract.contract_id)
        .group_by(Contract.contract_id)
        .order_by(order_expr, Contract.contract_id.asc())
        .offset((filters.page - 1) * filters.size)
        .limit(filters.size)
    )
    id_result = await db.execute(id_query)
    page_ids = [row[0] for row in id_result.all()]

    data_query = (
        select(Contract)
        .where(Contract.contract_id.in_(page_ids))
        .options(selectinload(Contract.items))
    )
    result = await db.execute(data_query)
    contracts = list(result.scalars().unique().all())
    # Restore the page order computed by id_query.
    position = {cid: index for index, cid in enumerate(page_ids)}
    contracts.sort(key=lambda contract: position[contract.contract_id])
    return contracts


async def _fetch_page_simple(
    db: AsyncSession,
    query,
    filters: ContractFilters,
    sort_column,
    descending: bool,
) -> list[Contract]:
    order_expr = sort_column.desc() if descending else sort_column.asc()
    data_query = (
        query.order_by(order_expr, Contract.contract_id.asc())
        .offset((filters.page - 1) * filters.size)
        .limit(filters.size)
        .options(selectinload(Contract.items))
    )
    result = await db.execute(data_query)
    return result.scalars().unique().all()


async def _category_names(db: AsyncSession) -> dict[int, str]:
    """Display names for every cached Dogma category, keyed by id.

    One small SELECT per request over a table holding a few dozen rows. Both the list
    and the detail path call it: composition carries category names, and a detail
    response built without this lookup serves a null name for every category while
    the list row beside it shows them.
    """
    result = await db.execute(
        select(EsiTaxonomyCache.esi_id, EsiTaxonomyCache.name).where(
            EsiTaxonomyCache.kind == "category"
        )
    )
    return {esi_id: name for esi_id, name in result.all()}


def _offered_items(contract: Contract) -> list[ContractItem]:
    """The items the contract puts up, oldest record first.

    is_included=False marks the items the issuer is ASKING FOR, so every derived
    figure counts only the offered side (§3.1). Ordering by record_id makes "the
    first item" a fact about the data rather than about row-return order.
    """
    return sorted(
        (item for item in contract.items if item.is_included),
        key=lambda item: item.record_id,
    )


def _reward_per_volume(contract: Contract) -> float | None:
    """Reward per m3, the figure haulers compare offers on.

    Undefined without both sides, and a zero volume gives nothing to divide by — so
    both cases serve NULL rather than a number that reads as free hauling (§9).
    """
    if contract.reward is None or not contract.volume:
        return None
    return float(contract.reward) / float(contract.volume)


def _primary_label(contract: Contract, offered: list[ContractItem]) -> str:
    """The row's headline.

    The hull is the headline on a ship marketplace, so an offered ship outranks
    whatever module happens to come first in a fitted-hull contract. Real ESI titles
    are frequently "" rather than NULL, so blank counts as absent. Computed here
    rather than per client so the list row, the detail page, and any future consumer
    name a contract the same way.
    """
    named = [item for item in offered if item.type_name]
    ship = next((item for item in named if item.category == "ship"), None)
    headline = ship or (named[0] if named else None)
    if headline is not None:
        return headline.type_name

    if contract.title and contract.title.strip():
        return contract.title.strip()

    if contract.type == ContractType.courier.value:
        if contract.end_location_name:
            return f"Courier to {contract.end_location_name}"
        return "Courier"

    return f"Contract {contract.contract_id}"


def _composition(
    contract: Contract, offered: list[ContractItem], names: dict[int, str]
) -> CompositionSummary | None:
    """What a multi-item contract is made of, by category.

    One offered row is not a breakdown — the row already names it — so composition is
    NULL below two. Counts are item ROWS rather than summed quantities (Criterion
    6.1). total_volume is the contract's own volume: the model holds no per-item
    volume, so there is nothing to sum.
    """
    if len(offered) < 2:
        return None

    row_counts: dict[int | None, int] = {}
    for item in offered:
        row_counts[item.category_id] = row_counts.get(item.category_id, 0) + 1

    categories = [
        CompositionCategory(
            category_id=category_id,
            # A category the name cache has not resolved serves NULL rather than a
            # fabricated string — the client can say "unnamed", we cannot invent.
            name=names.get(category_id) if category_id is not None else None,
            item_row_count=count,
        )
        for category_id, count in row_counts.items()
    ]
    # Rows whose category could not be determined are the "other" bucket and sit
    # last however many there are; the rest sort by share, then name, with unnamed
    # categories after named ones so the order is total rather than merely stable.
    categories.sort(
        key=lambda entry: (
            entry.category_id is None,
            -entry.item_row_count,
            entry.name is None,
            entry.name or "",
        )
    )

    return CompositionSummary(
        categories=categories,
        total_item_rows=len(offered),
        total_volume=float(contract.volume) if contract.volume is not None else None,
    )


def _blueprint_summary(offered: list[ContractItem]) -> BlueprintSummary | None:
    """The blueprint terms of a contract offering copies.

    With more than one copy the terms belong to individual copies, so reporting one
    copy's runs would misdescribe the others: the count goes out alone and the client
    sends the reader to the detail page for the rest (§17.3).
    """
    copies = [item for item in offered if item.is_blueprint_copy is True]
    if not copies:
        return None
    if len(copies) > 1:
        return BlueprintSummary(copy_count=len(copies))

    copy = copies[0]
    return BlueprintSummary(
        runs=copy.runs,
        material_efficiency=copy.material_efficiency,
        time_efficiency=copy.time_efficiency,
        copy_count=1,
    )


def _contract_fields(contract: Contract, names: dict[int, str]) -> dict:
    """The fields shared by the list row and the detail response.

    Written out rather than validated off the ORM object, so a column added to the
    model does not silently become a wire field.
    """
    offered = _offered_items(contract)
    return {
        "contract_id": contract.contract_id,
        "issuer_id": contract.issuer_id,
        "issuer_corporation_id": contract.issuer_corporation_id,
        "start_location_id": contract.start_location_id,
        "start_location_system_id": contract.start_location_system_id,
        "end_location_id": contract.end_location_id,
        "type": contract.type,
        "title": contract.title,
        "for_corporation": contract.for_corporation,
        "date_issued": contract.date_issued,
        "date_expired": contract.date_expired,
        "price": contract.price,
        "collateral": contract.collateral,
        "reward": contract.reward,
        "volume": contract.volume,
        "buyout": contract.buyout,
        "days_to_complete": contract.days_to_complete,
        "reward_per_volume": _reward_per_volume(contract),
        "start_location_name": contract.start_location_name,
        "end_location_name": contract.end_location_name,
        "issuer_name": contract.issuer_name,
        "issuer_corporation_name": contract.issuer_corporation_name,
        "last_seen_at": contract.last_seen_at,
        "is_ship_contract": contract.is_ship_contract,
        "is_blueprint_copy_contract": any(
            item.is_blueprint_copy is True for item in offered
        ),
        "primary_label": _primary_label(contract, offered),
        "composition": _composition(contract, offered, names),
        "blueprint_summary": _blueprint_summary(offered),
    }


def _list_item(contract: Contract, names: dict[int, str]) -> ContractListItemSchema:
    """Build one list row."""
    return ContractListItemSchema(**_contract_fields(contract, names))


def _detail_item(contract: Contract, names: dict[int, str]) -> ContractDetailSchema:
    """Build a detail response: the row plus the contract's full item array.

    Ordered by record_id, the same order the derived fields treat as canonical, so
    the item table renders identically on every request.
    """
    return ContractDetailSchema(
        **_contract_fields(contract, names),
        items=[
            ContractItemSchema.model_validate(item)
            for item in sorted(contract.items, key=lambda item: item.record_id)
        ],
    )


async def get_contracts(
    db: AsyncSession, filters: ContractFilters
) -> ContractListResponse:
    """
    Retrieves a paginated list of contracts based on specified filters.

    This function constructs a single, dynamic query to handle searching,
    filtering, sorting, and pagination. It addresses the complexity of
    conditionally joining the ContractItem table and ensuring correct counts
    when one-to-many relationships are involved.
    """
    start_time = time.time()

    # Log the start of the contract search operation
    logger.info(
        "Starting contract search",
        search_terms={
            "search": filters.search,
            "type_ids": filters.type_ids,
            "min_price": filters.min_price,
            "max_price": filters.max_price,
            "page": filters.page,
            "size": filters.size,
            "sort_by": filters.sort_by.value if filters.sort_by else None,
            "sort_direction": filters.sort_direction.value if filters.sort_direction else None,
        }
    )

    try:
        # Start with the base query for the Contract model.
        query = select(Contract)

        needs_item_join = _needs_item_join(filters)

        if needs_item_join:
            # Use an outer join to ensure contracts without items are not excluded
            # unless specifically filtered out.
            query = query.outerjoin(ContractItem)

        # --- Apply Filters ---
        # Each filter is applied to the query object, narrowing the results.
        query = _apply_contract_filters(query, filters)
        query = _apply_item_filters(query, filters)

        # --- Count Query ---
        # One grouped aggregate serves both the segment labels and the page total,
        # so a request costs the same one corpus-scale count it always did.
        segment_counts, total = await _segment_counts_and_total(
            db, filters, needs_item_join
        )

        # Measured before the empty-result short-circuit: an empty page is where the
        # figure matters most, since a system holding only structure-hosted contracts
        # is otherwise indistinguishable from an empty one.
        unknown_system_excluded = (
            await _count_unknown_system_excluded(db, filters, needs_item_join)
            if filters.system_ids
            else None
        )

        # Describes the dataset rather than the page, so it is computed once per
        # request beside the counts and is the same figure whatever was filtered.
        coverage = await _observed_coverage(db)

        if total == 0:
            duration_ms = (time.time() - start_time) * 1000
            log_key_event(
                logger=logger,
                event="contract_search_executed",
                success=True,
                duration_ms=duration_ms,
                results_count=0,
                search_terms={
                    "search": filters.search,
                    "type_ids": filters.type_ids,
                    "page": filters.page,
                    "size": filters.size,
                }
            )
            return ContractListResponse(
                total=0,
                page=filters.page,
                size=filters.size,
                items=[],
                unknown_system_excluded=unknown_system_excluded,
                # Carried onto the empty page deliberately: the counts are the only
                # thing telling a reader who filtered into an empty segment that the
                # corpus around it is not empty.
                segment_counts=segment_counts,
                # Likewise: an empty page is precisely where a reader needs to know
                # whether the region they picked is ingested at all.
                coverage=coverage,
            )

        # --- Data Query ---
        # Apply sorting and pagination to get the specific page of results.
        sort_column = SORT_MAP.get(filters.sort_by)
        if sort_column is None:
            # Fallback to default or raise an error for an unsupported sort key
            sort_column = Contract.date_issued

        descending = filters.sort_direction == SortDirection.desc

        if needs_item_join:
            contracts = await _fetch_page_joined(db, query, filters, sort_column, descending)
        else:
            contracts = await _fetch_page_simple(db, query, filters, sort_column, descending)

        names = await _category_names(db)

        # Calculate duration and log successful completion
        duration_ms = (time.time() - start_time) * 1000

        response = ContractListResponse(
            total=total,
            page=filters.page,
            size=filters.size,
            items=[_list_item(c, names) for c in contracts],
            unknown_system_excluded=unknown_system_excluded,
            segment_counts=segment_counts,
            coverage=coverage,
        )

        # Log successful contract search with key event schema
        log_key_event(
            logger=logger,
            event="contract_search_executed",
            success=True,
            duration_ms=duration_ms,
            results_count=len(contracts),
            search_terms={
                "search": filters.search,
                "type_ids": filters.type_ids,
                "min_price": filters.min_price,
                "max_price": filters.max_price,
                "page": filters.page,
                "size": filters.size,
                "sort_by": filters.sort_by.value if filters.sort_by else None,
                "sort_direction": filters.sort_direction.value if filters.sort_direction else None,
            }
        )

        return response

    except Exception as e:
        # Calculate duration and log failure
        duration_ms = (time.time() - start_time) * 1000

        log_key_event(
            logger=logger,
            event="contract_search_executed",
            success=False,
            duration_ms=duration_ms,
            error_message=str(e),
            search_terms={
                "search": filters.search,
                "type_ids": filters.type_ids,
                "min_price": filters.min_price,
                "max_price": filters.max_price,
                "page": filters.page,
                "size": filters.size,
            }
        )

        # Re-raise the exception to maintain existing error handling behavior
        raise
