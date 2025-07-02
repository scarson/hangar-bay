import asyncio
import time
from typing import Optional, Dict, Any, List
from sqlalchemy import func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from ..core.logging import get_logger, log_key_event

# Initialize logger for this module
logger = get_logger(__name__)

from ..models.contracts import Contract, ContractItem
from ..models.common_models import EsiTypeCache
from ..schemas.common import PaginatedResponse
from ..schemas.contracts import (
    ContractFilters,
    SortDirection,
    ContractSchema,
    SortableContractFields,
)
from .esi_type_service import ESITypeService

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


async def get_contracts(
    db: AsyncSession, filters: ContractFilters
) -> PaginatedResponse[ContractSchema]:
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

        # Determine if a JOIN on the ContractItem table is necessary. A join is
        # required if we need to filter or sort on item attributes.
        needs_item_join = (
            filters.search
            or filters.type_ids
            or filters.is_bpc is not None
            or filters.min_runs is not None
            or filters.max_runs is not None
            # Add sorting by ship name to the condition
            or filters.sort_by == SortableContractFields.ship_name
        )

        if needs_item_join:
            # Use an outer join to ensure contracts without items are not excluded
            # unless specifically filtered out.
            query = query.outerjoin(ContractItem)

        # --- Apply Filters ---
        # Each filter is applied to the query object, narrowing the results.

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

        # 3. Location filters
        if filters.region_ids:
            query = query.filter(Contract.start_location_region_id.in_(filters.region_ids))
        if filters.system_ids:
            query = query.filter(Contract.start_location_system_id.in_(filters.system_ids))
        if filters.station_ids:
            query = query.filter(Contract.start_location_id.in_(filters.station_ids))

        # 4. Contract Item specific filters
        if filters.type_ids:
            query = query.filter(ContractItem.type_id.in_(filters.type_ids))
        if filters.is_bpc is not None:
            query = query.filter(ContractItem.is_blueprint_copy == filters.is_bpc)
        # BPC Run filters (Note: ME/TE not implemented as data is not in model)
        if filters.min_runs is not None:
            query = query.filter(ContractItem.raw_quantity >= filters.min_runs)
        if filters.max_runs is not None:
            query = query.filter(ContractItem.raw_quantity <= filters.max_runs)

        # --- Count Query ---
        # To get an accurate total count of matching *contracts* (not items),
        # we must count the distinct contract_ids from our filtered query.
        # This is crucial because the join can create duplicate contract rows.
        count_subquery = select(query.subquery().c.contract_id).distinct().subquery()
        count_query = select(func.count()).select_from(count_subquery)
        
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

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
            return PaginatedResponse(total=0, page=filters.page, size=filters.size, items=[])

        # --- Data Query ---
        # Now, apply sorting and pagination to the filtered query to get the
        # specific page of results.
        sort_column = SORT_MAP.get(filters.sort_by)
        if sort_column is None:
            # Fallback to default or raise an error for an unsupported sort key
            sort_column = Contract.date_issued

        if filters.sort_direction == SortDirection.desc:
            sort_column = sort_column.desc()
        else:
            sort_column = sort_column.asc()

        data_query = (
            query
            .order_by(sort_column)
            .offset((filters.page - 1) * filters.size)
            .limit(filters.size)
            .options(selectinload(Contract.items))
        )

        result = await db.execute(data_query)
        # .unique() is needed here because of the join, to ensure we get unique Contract objects
        contracts = result.scalars().unique().all()

        # Calculate duration and log successful completion
        duration_ms = (time.time() - start_time) * 1000
        
        response = PaginatedResponse(
            total=total,
            page=filters.page,
            size=filters.size,
            items=[ContractSchema.model_validate(c) for c in contracts],
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


async def get_contract_details(
    db: AsyncSession, 
    contract_id: int, 
    esi_type_service: ESITypeService
) -> Optional[Dict[str, Any]]:
    """
    Retrieve detailed information for a single contract including ship attributes,
    images, and comprehensive ESI data.
    
    Args:
        db: Database session
        contract_id: The contract ID to fetch details for
        esi_type_service: Service for fetching ESI type information
        
    Returns:
        Dictionary with comprehensive contract details, or None if not found
    """
    start_time = time.time()
    
    try:
        # Fetch the contract with all its items
        query = (
            select(Contract)
            .options(selectinload(Contract.items))
            .where(Contract.contract_id == contract_id)
        )
        
        result = await db.execute(query)
        contract = result.scalar_one_or_none()
        
        if not contract:
            logger.warning(f"Contract {contract_id} not found")
            return None
        
        # Build the base contract response
        contract_details = {
            "contract_id": contract.contract_id,
            "title": contract.title,
            "type": contract.type,
            "status": contract.status,
            "price": float(contract.price) if contract.price else 0.0,
            "collateral": float(contract.collateral) if contract.collateral else 0.0,
            "reward": contract.reward,
            "volume": contract.volume,
            "date_issued": contract.date_issued.isoformat() if contract.date_issued else None,
            "date_expired": contract.date_expired.isoformat() if contract.date_expired else None,
            "date_completed": contract.date_completed.isoformat() if contract.date_completed else None,
            "issuer_id": contract.issuer_id,
            "issuer_name": contract.issuer_name,
            "issuer_corporation_id": contract.issuer_corporation_id,
            "issuer_corporation_name": contract.issuer_corporation_name,
            "start_location_id": contract.start_location_id,
            "start_location_name": contract.start_location_name,
            "start_location_system_id": contract.start_location_system_id,
            "start_location_region_id": contract.start_location_region_id,
            "end_location_id": contract.end_location_id,
            "for_corporation": contract.for_corporation,
            "is_ship_contract": contract.is_ship_contract,
            "items": [],
            "ship_details": None
        }
        
        # Process contract items and gather type IDs for ESI lookup
        type_ids_to_fetch = set()
        items_data = []
        
        for item in contract.items:
            item_data = {
                "record_id": item.record_id,
                "type_id": item.type_id,
                "type_name": item.type_name,
                "category": item.category,
                "quantity": item.quantity,
                "is_included": item.is_included,
                "is_singleton": item.is_singleton,
                "is_blueprint_copy": item.is_blueprint_copy,
                "raw_quantity": item.raw_quantity,
                "market_group_id": item.market_group_id
            }
            items_data.append(item_data)
            type_ids_to_fetch.add(item.type_id)
        
        # Fetch ESI type information for all items
        type_info_map = {}
        if type_ids_to_fetch:
            type_info_map = await esi_type_service.get_multiple_types(list(type_ids_to_fetch))
        
        # Enhance items with ESI data and identify ships
        ship_items = []
        enhanced_items = []
        
        for item_data in items_data:
            type_id = item_data["type_id"]
            type_info = type_info_map.get(type_id)
            
            if type_info:
                # Add ESI type information
                item_data.update({
                    "description": type_info.description,
                    "mass": type_info.mass,
                    "volume": type_info.volume,
                    "capacity": type_info.capacity,
                    "icon_url": await esi_type_service.get_ship_icon_url(type_id, "64"),
                    "image_url": await esi_type_service.get_ship_image_url(type_id, "128"),
                })
                
                # Check if this is a ship (category_id 6)
                if type_info.category_id == 6:
                    ship_attributes = await esi_type_service.get_ship_attributes(type_id)
                    item_data["ship_attributes"] = ship_attributes
                    ship_items.append(item_data)
            
            enhanced_items.append(item_data)
        
        contract_details["items"] = enhanced_items
        
        # If this is a ship contract, add detailed ship information
        if contract.is_ship_contract and ship_items:
            # For ship contracts, typically there's one main ship
            primary_ship = ship_items[0]  # Take the first ship found
            
            contract_details["ship_details"] = {
                "type_id": primary_ship["type_id"],
                "type_name": primary_ship["type_name"],
                "description": primary_ship.get("description", ""),
                "attributes": primary_ship.get("ship_attributes", {}),
                "icon_url": primary_ship.get("icon_url"),
                "image_url": primary_ship.get("image_url"),
                "render_url": await esi_type_service.get_ship_image_url(primary_ship["type_id"], "512"),
                "mass": primary_ship.get("mass"),
                "volume": primary_ship.get("volume"),
                "capacity": primary_ship.get("capacity"),
            }
        
        # Calculate duration and log success
        duration_ms = (time.time() - start_time) * 1000
        
        log_key_event(
            logger=logger,
            event="contract_details_fetched",
            success=True,
            duration_ms=duration_ms,
            contract_id=contract_id,
            is_ship_contract=contract.is_ship_contract,
            items_count=len(contract.items),
            ship_items_count=len(ship_items)
        )
        
        return contract_details
        
    except Exception as e:
        # Calculate duration and log failure
        duration_ms = (time.time() - start_time) * 1000
        
        log_key_event(
            logger=logger,
            event="contract_details_fetched",
            success=False,
            duration_ms=duration_ms,
            contract_id=contract_id,
            error_message=str(e)
        )
        
        logger.error(f"Failed to fetch contract details for {contract_id}: {e}")
        raise
