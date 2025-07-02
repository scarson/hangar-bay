"""
Detailed Contract Service for comprehensive contract retrieval with ESI data.

This service provides enhanced contract information including ship attributes,
EVE image server URLs, and comprehensive ESI type data joins.
"""

import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from ..models.contracts import Contract, ContractItem
from ..models.common_models import EsiTypeCache
from ..schemas.contracts import (
    ContractDetailsSchema, 
    ContractDetailsItemSchema,
    ShipDetailsSchema,
    ShipAttributeSchema,
    ShipAttributeGroupSchema,
    EsiTypeSchema
)
from .esi_type_service import ESITypeService


logger = logging.getLogger(__name__)


class ContractDetailsService:
    """Service for retrieving contract details with ESI data joins.
    
    Follows the service construction pattern with dependency injection for
    database session and ESI type service.
    """
    
    def __init__(self, db_session: AsyncSession, esi_type_service: ESITypeService):
        self.db_session = db_session
        self.esi_type_service = esi_type_service
    
    async def get_contract_details(
        self,
        contract_id: int,
        include_ship_attributes: bool = True,
        attribute_detail_level: str = "key_attributes"
    ) -> Optional[ContractDetailsSchema]:
        """
        Retrieve comprehensive contract details with ESI data enhancement.
        
        Args:
            contract_id: The contract ID to retrieve
            include_ship_attributes: Whether to include detailed ship attributes
            attribute_detail_level: "key_attributes" or "all_attributes"
            
        Returns:
            ContractDetailsSchema with enhanced data or None if not found
        """
        logger.info(
            "Retrieving detailed contract",
            extra={
                "contract_id": contract_id,
                "include_ship_attributes": include_ship_attributes,
                "attribute_detail_level": attribute_detail_level,
                "event": "contract_detail_request"
            }
        )
        
        try:
            # Retrieve contract with items
            contract = await self._get_contract_with_items(contract_id)
            if not contract:
                logger.warning(
                    "Contract not found",
                    extra={
                        "contract_id": contract_id,
                        "event": "contract_not_found"
                    }
                )
                return None
            
            # Enhance items with ESI data
            enhanced_items = await self._enhance_contract_items(contract.items)
            
            # Process ship details if this is a ship contract
            ship_details = None
            if contract.is_ship_contract and include_ship_attributes:
                ship_details = await self._process_ship_details(
                    contract.items, 
                    attribute_detail_level
                )
            
            # Build contract details response
            contract_details = ContractDetailsSchema(
                contract_id=contract.contract_id,
                title=contract.title,
                type=contract.type,
                status=contract.status,
                price=contract.price or 0.0,
                collateral=0.0,  # TODO: Calculate from contract data
                reward=contract.reward,
                volume=contract.volume,
                date_issued=contract.date_issued.isoformat() if contract.date_issued else None,
                date_expired=contract.date_expired.isoformat() if contract.date_expired else None,
                date_completed=contract.date_completed.isoformat() if contract.date_completed else None,
                issuer_id=contract.issuer_id,
                issuer_name=contract.issuer_name,
                issuer_corporation_id=contract.issuer_corporation_id,
                issuer_corporation_name=contract.issuer_corporation_name,
                start_location_id=contract.start_location_id,
                start_location_name=contract.start_location_name,
                end_location_id=contract.end_location_id,
                for_corporation=contract.for_corporation,
                is_ship_contract=contract.is_ship_contract,
                items=enhanced_items,
                ship_details=ship_details
            )
            
            logger.info(
                "Contract details retrieved successfully",
                extra={
                    "contract_id": contract_id,
                    "item_count": len(enhanced_items),
                    "has_ship_details": ship_details is not None,
                    "event": "contract_detail_success"
                }
            )
            
            return contract_details
            
        except Exception as e:
            logger.error(
                "Failed to retrieve contract details",
                extra={
                    "contract_id": contract_id,
                    "error": str(e),
                    "event": "contract_detail_error"
                },
                exc_info=True
            )
            raise
    
    async def _get_contract_with_items(self, contract_id: int) -> Optional[Contract]:
        """Retrieve contract with eagerly loaded items."""
        query = (
            select(Contract)
            .where(Contract.contract_id == contract_id)
            .options(selectinload(Contract.items))
        )
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()
    
    async def _enhance_contract_items(
        self, 
        items: List[ContractItem]
    ) -> List[ContractDetailsItemSchema]:
        """Enhance contract items with ESI type data."""
        if not items:
            return []
        
        # Get unique type IDs
        type_ids = list(set(item.type_id for item in items))
        
        # Fetch ESI type data for all items
        type_data_map = await self.esi_type_service.get_multiple_types(type_ids)
        
        enhanced_items = []
        for item in items:
            type_data = type_data_map.get(item.type_id)
            
            # Create enhanced item schema
            enhanced_item = ContractDetailsItemSchema(
                record_id=item.record_id,
                type_id=item.type_id,
                type_name=item.type_name or (type_data.name if type_data else None),
                category=item.category,
                quantity=item.quantity,
                is_included=item.is_included,
                is_singleton=item.is_singleton,
                is_blueprint_copy=item.is_blueprint_copy,
                raw_quantity=item.raw_quantity,
                market_group_id=item.market_group_id or (type_data.market_group_id if type_data else None),
                # ESI-enhanced fields
                description=type_data.description if type_data else None,
                mass=type_data.mass if type_data else None,
                volume=type_data.volume if type_data else None,
                capacity=type_data.capacity if type_data else None,
                icon_url=f"https://images.evetech.net/types/{item.type_id}/icon?size=64",
                image_url=f"https://images.evetech.net/types/{item.type_id}/render?size=512"
            )
            
            # Add ship attributes if this is a ship
            if type_data and await self._is_ship_type(type_data):
                enhanced_item.ship_attributes = await self._process_ship_attributes(
                    type_data, "key_attributes"
                )
            
            enhanced_items.append(enhanced_item)
        
        return enhanced_items
    
    async def _process_ship_details(
        self, 
        items: List[ContractItem], 
        attribute_detail_level: str
    ) -> Optional[ShipDetailsSchema]:
        """Process ship details for ship contracts."""
        # Find the primary ship item (usually the first singleton ship)
        ship_item = None
        for item in items:
            if item.is_singleton and item.type_name:
                # Check if this is a ship type
                type_data = await self.esi_type_service.get_type_info(item.type_id)
                if type_data and await self._is_ship_type(type_data):
                    ship_item = item
                    break
        
        if not ship_item:
            return None
        
        # Get ship type data
        ship_type_data = await self.esi_type_service.get_type_info(ship_item.type_id)
        if not ship_type_data:
            return None
        
        # Process ship attributes
        ship_attributes = await self._process_ship_attributes(
            ship_type_data, attribute_detail_level
        )
        
        return ShipDetailsSchema(
            type_id=ship_item.type_id,
            type_name=ship_item.type_name,
            description=ship_type_data.description,
            attributes=ship_attributes or {},
            icon_url=f"https://images.evetech.net/types/{ship_item.type_id}/icon?size=64",
            image_url=f"https://images.evetech.net/types/{ship_item.type_id}/render?size=512",
            render_url=f"https://images.evetech.net/types/{ship_item.type_id}/render?size=512",
            mass=ship_type_data.mass,
            volume=ship_type_data.volume,
            capacity=ship_type_data.capacity
        )
    
    async def _process_ship_attributes(
        self, 
        type_data: EsiTypeCache, 
        detail_level: str
    ) -> Optional[Dict[str, Any]]:
        """Process dogma attributes into organized attribute groups."""
        if not type_data.dogma_attributes:
            return None
        
        # Define key attributes for ships (most important for quick overview)
        key_attribute_ids = {
            # Tank/Defense
            263: "shield_capacity",
            264: "armor_hp", 
            265: "structure_hp",
            # Capacitor
            210: "capacitor_capacity",
            # Targeting
            76: "max_targets",
            78: "sensor_strength",
            # Speed
            9: "max_velocity",
            # Slots
            14: "high_slots",
            13: "med_slots", 
            12: "low_slots",
            1137: "rig_slots"
        }
        
        # Process attributes based on detail level
        if detail_level == "key_attributes":
            processed_attributes = {}
            for attr_id, attr_name in key_attribute_ids.items():
                if str(attr_id) in type_data.dogma_attributes:
                    attr_data = type_data.dogma_attributes[str(attr_id)]
                    processed_attributes[attr_name] = attr_data.get("value", 0)
            return processed_attributes
        else:
            # Return all attributes organized by groups
            return self._organize_attributes_by_groups(type_data.dogma_attributes)
    
    def _organize_attributes_by_groups(self, dogma_attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Organize all dogma attributes into logical groups."""
        # This is a simplified version - in practice, you'd have comprehensive
        # attribute categorization based on EVE's attribute taxonomy
        groups = {
            "tank": {},
            "capacitor": {},
            "targeting": {},
            "navigation": {},
            "fitting": {},
            "other": {}
        }
        
        # Map known attribute IDs to groups
        tank_attrs = ["263", "264", "265"]  # Shield, Armor, Structure
        cap_attrs = ["210", "55"]  # Capacitor capacity, recharge rate
        targeting_attrs = ["76", "78", "79"]  # Max targets, sensor strength
        nav_attrs = ["9", "10"]  # Max velocity, inertia
        fitting_attrs = ["14", "13", "12", "1137"]  # Slots
        
        for attr_id, attr_data in dogma_attributes.items():
            if attr_id in tank_attrs:
                groups["tank"][attr_id] = attr_data
            elif attr_id in cap_attrs:
                groups["capacitor"][attr_id] = attr_data
            elif attr_id in targeting_attrs:
                groups["targeting"][attr_id] = attr_data
            elif attr_id in nav_attrs:
                groups["navigation"][attr_id] = attr_data
            elif attr_id in fitting_attrs:
                groups["fitting"][attr_id] = attr_data
            else:
                groups["other"][attr_id] = attr_data
        
        return groups
    
    async def _is_ship_type(self, type_data: EsiTypeCache) -> bool:
        """Check if a type is a ship based on category/group."""
        # Ship category ID is 6 in EVE Online
        return type_data.category_id == 6 if type_data.category_id else False
