"""
ESI Type Service for fetching and caching comprehensive ship and item type data.

This service handles fetching type information from ESI, including ship attributes,
descriptions, and visual data needed for detailed contract views.

# AI Guidance: This file is over 300 lines long. Make sure to read the entire file when necessary.
"""

import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert

from ..models.common_models import EsiTypeCache
from ..core.esi_client_class import ESIClient

logger = logging.getLogger(__name__)


class ESITypeService:
    """Service for fetching and caching ESI type information."""
    
    def __init__(self, db_session: AsyncSession, esi_client: ESIClient):
        self.db_session = db_session
        self.esi_client = esi_client
    
    async def get_type_info(self, type_id: int) -> Optional[EsiTypeCache]:
        """
        Get comprehensive type information for a given type_id.
        
        First checks cache, then fetches from ESI if not found.
        
        Args:
            type_id: The EVE type ID to fetch information for
            
        Returns:
            EsiTypeCache object with comprehensive type data, or None if not found
        """
        # First check cache
        cached_type = await self._get_cached_type(type_id)
        if cached_type:
            logger.debug(f"Found cached type data for type_id={type_id}")
            return cached_type
        
        # If not cached, fetch from ESI
        logger.info(f"Fetching type data from ESI for type_id={type_id}")
        return await self._fetch_and_cache_type(type_id)
    
    async def get_multiple_types(self, type_ids: List[int]) -> Dict[int, EsiTypeCache]:
        """
        Get type information for multiple type IDs efficiently.
        
        Args:
            type_ids: List of type IDs to fetch
            
        Returns:
            Dictionary mapping type_id to EsiTypeCache objects
        """
        if not type_ids:
            return {}
        
        # Get cached types first
        cached_types = await self._get_cached_types(type_ids)
        result = {t.type_id: t for t in cached_types}
        
        # Find missing types
        missing_type_ids = [tid for tid in type_ids if tid not in result]
        
        if missing_type_ids:
            logger.info(f"Fetching {len(missing_type_ids)} missing types from ESI")
            
            # Fetch missing types from ESI
            for type_id in missing_type_ids:
                try:
                    type_info = await self._fetch_and_cache_type(type_id)
                    if type_info:
                        result[type_id] = type_info
                except Exception as e:
                    logger.error(f"Failed to fetch type_id={type_id}: {e}")
                    continue
        
        return result
    
    async def _get_cached_type(self, type_id: int) -> Optional[EsiTypeCache]:
        """Get a single type from cache."""
        stmt = select(EsiTypeCache).where(EsiTypeCache.type_id == type_id)
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def _get_cached_types(self, type_ids: List[int]) -> List[EsiTypeCache]:
        """Get multiple types from cache."""
        stmt = select(EsiTypeCache).where(EsiTypeCache.type_id.in_(type_ids))
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())
    
    async def _fetch_and_cache_type(self, type_id: int) -> Optional[EsiTypeCache]:
        """
        Fetch type information from ESI and cache it.
        
        Args:
            type_id: The type ID to fetch
            
        Returns:
            EsiTypeCache object with the fetched data, or None if fetch failed
        """
        try:
            # Fetch type info from ESI
            type_data = await self.esi_client.get_type_info(type_id)
            if not type_data:
                logger.warning(f"No type data returned from ESI for type_id={type_id}")
                return None
            
            # Create EsiTypeCache object
            type_cache = EsiTypeCache(
                type_id=type_id,
                name=type_data.get('name', ''),
                description=type_data.get('description', ''),
                category_id=type_data.get('category_id'),
                group_id=type_data.get('group_id'),
                market_group_id=type_data.get('market_group_id'),
                mass=type_data.get('mass'),
                volume=type_data.get('volume'),
                capacity=type_data.get('capacity'),
                icon_id=type_data.get('icon_id'),
                graphic_id=type_data.get('graphic_id'),
                published=type_data.get('published', True),
                dogma_attributes=type_data.get('dogma_attributes'),
                dogma_effects=type_data.get('dogma_effects'),
                raw_esi_response=type_data
            )
            
            # Use PostgreSQL upsert to handle potential race conditions
            stmt = insert(EsiTypeCache).values(
                type_id=type_cache.type_id,
                name=type_cache.name,
                description=type_cache.description,
                category_id=type_cache.category_id,
                group_id=type_cache.group_id,
                market_group_id=type_cache.market_group_id,
                mass=type_cache.mass,
                volume=type_cache.volume,
                capacity=type_cache.capacity,
                icon_id=type_cache.icon_id,
                graphic_id=type_cache.graphic_id,
                published=type_cache.published,
                dogma_attributes=type_cache.dogma_attributes,
                dogma_effects=type_cache.dogma_effects,
                raw_esi_response=type_cache.raw_esi_response
            )
            
            # On conflict, update all fields (refresh cache)
            stmt = stmt.on_conflict_do_update(
                index_elements=['type_id'],
                set_={
                    'name': stmt.excluded.name,
                    'description': stmt.excluded.description,
                    'category_id': stmt.excluded.category_id,
                    'group_id': stmt.excluded.group_id,
                    'market_group_id': stmt.excluded.market_group_id,
                    'mass': stmt.excluded.mass,
                    'volume': stmt.excluded.volume,
                    'capacity': stmt.excluded.capacity,
                    'icon_id': stmt.excluded.icon_id,
                    'graphic_id': stmt.excluded.graphic_id,
                    'published': stmt.excluded.published,
                    'dogma_attributes': stmt.excluded.dogma_attributes,
                    'dogma_effects': stmt.excluded.dogma_effects,
                    'raw_esi_response': stmt.excluded.raw_esi_response
                }
            )
            
            await self.db_session.execute(stmt)
            await self.db_session.commit()
            
            logger.info(f"Successfully cached type data for type_id={type_id}, name='{type_cache.name}'")
            return type_cache
            
        except Exception as e:
            logger.error(f"Failed to fetch and cache type_id={type_id}: {e}")
            await self.db_session.rollback()
            return None
    
    async def get_ship_image_url(self, type_id: int, size: str = "64") -> Optional[str]:
        """
        Get the image URL for a ship type.
        
        Args:
            type_id: The ship type ID
            size: Image size (32, 64, 128, 256, 512)
            
        Returns:
            URL to the ship image, or None if not available
        """
        # EVE image server URL pattern
        # https://images.evetech.net/types/{type_id}/render/{size}.png
        valid_sizes = ["32", "64", "128", "256", "512"]
        if size not in valid_sizes:
            size = "64"  # Default fallback
        
        return f"https://images.evetech.net/types/{type_id}/render/{size}.png"
    
    async def get_ship_icon_url(self, type_id: int, size: str = "64") -> Optional[str]:
        """
        Get the icon URL for a ship type.
        
        Args:
            type_id: The ship type ID
            size: Icon size (32, 64, 128, 256, 512)
            
        Returns:
            URL to the ship icon, or None if not available
        """
        # EVE image server URL pattern for icons
        # https://images.evetech.net/types/{type_id}/icon/{size}.png
        valid_sizes = ["32", "64", "128", "256", "512"]
        if size not in valid_sizes:
            size = "64"  # Default fallback
        
        return f"https://images.evetech.net/types/{type_id}/icon/{size}.png"
    
    async def is_ship_type(self, type_id: int) -> bool:
        """
        Check if a given type_id represents a ship.
        
        Ships in EVE are typically in category_id 6 (Ship).
        
        Args:
            type_id: The type ID to check
            
        Returns:
            True if the type is a ship, False otherwise
        """
        type_info = await self.get_type_info(type_id)
        if not type_info:
            return False
        
        # Category ID 6 is Ships in EVE Online
        return type_info.category_id == 6
    
    async def get_ship_attributes(self, type_id: int) -> Dict[str, Any]:
        """
        Get ship-specific attributes for detailed display.
        
        Args:
            type_id: The ship type ID
            
        Returns:
            Dictionary of ship attributes relevant for contract display
        """
        type_info = await self.get_type_info(type_id)
        if not type_info:
            return {}
        
        # Extract common ship attributes from dogma_attributes
        attributes = {}
        if type_info.dogma_attributes:
            # Map common attribute IDs to readable names
            attribute_mapping = {
                3: "power_output",          # Power Output
                4: "shield_capacity",       # Shield Capacity
                5: "armor_hp",             # Armor HP
                6: "structure_hp",         # Structure HP
                11: "thermal_damage_resistance", # Thermal Damage Resistance
                12: "kinetic_damage_resistance", # Kinetic Damage Resistance
                13: "explosive_damage_resistance", # Explosive Damage Resistance
                14: "em_damage_resistance", # EM Damage Resistance
                15: "low_slots",           # Low Slots
                16: "med_slots",           # Medium Slots
                17: "high_slots",          # High Slots
                18: "rig_slots",           # Rig Slots
                38: "capacity",            # Capacity
                161: "max_velocity",       # Max Velocity
                70: "warp_speed_multiplier", # Warp Speed Multiplier
                552: "signature_radius",    # Signature Radius
            }
            
            for attr in type_info.dogma_attributes:
                attr_id = attr.get('attribute_id')
                if attr_id in attribute_mapping:
                    attributes[attribute_mapping[attr_id]] = attr.get('value')
        
        # Add basic properties
        attributes.update({
            'mass': type_info.mass,
            'volume': type_info.volume,
            'capacity': type_info.capacity,
        })
        
        return attributes
    
    async def _process_ship_attributes(
        self, 
        type_id: int, 
        detail_level: str = "key_attributes"
    ) -> Dict[str, Any]:
        """Process ship attributes based on detail level.
        
        Fetches ship attributes from ESI and formats them according
        to the requested detail level.
        
        Args:
            type_id: Ship type ID
            detail_level: "basic", "key_attributes", or "all_attributes"
            
        Returns:
            Dictionary of processed ship attributes
        """
        # Get type info with attributes
        type_info = await self.get_type_info(type_id)
        if not type_info:
            return {}
            
        # Return based on detail level
        if detail_level == "basic":
            return self._extract_basic_ship_attributes(type_info)
        elif detail_level == "key_attributes":
            return await self.get_ship_attributes(type_id)  # Use existing method
        else:  # all_attributes
            return self._extract_all_ship_attributes(type_info)
    
    def _extract_basic_ship_attributes(self, type_info: Any) -> Dict[str, Any]:
        """Extract basic ship attributes for minimal display."""
        return {
            'mass': type_info.mass,
            'volume': type_info.volume,
            'capacity': type_info.capacity,
            'name': type_info.name,
            'description': type_info.description
        }
    
    def _extract_all_ship_attributes(self, type_info: Any) -> Dict[str, Any]:
        """Extract all available ship attributes."""
        attributes = {
            'mass': type_info.mass,
            'volume': type_info.volume,
            'capacity': type_info.capacity,
            'name': type_info.name,
            'description': type_info.description,
            'category_id': type_info.category_id,
            'group_id': type_info.group_id,
            'market_group_id': type_info.market_group_id
        }
        
        # Add all dogma attributes if available
        if type_info.dogma_attributes:
            attributes['dogma_attributes'] = type_info.dogma_attributes
            
        # Add all dogma effects if available
        if type_info.dogma_effects:
            attributes['dogma_effects'] = type_info.dogma_effects
            
        return attributes
    
    async def _generate_image_urls(self, type_id: int) -> Dict[str, str]:
        """Generate standardized image URLs for ship visualization.
        
        Args:
            type_id: Ship type ID
            
        Returns:
            Dictionary containing various image URL types
        """
        base_url = "https://images.evetech.net/types"
        
        return {
            'icon': f"{base_url}/{type_id}/icon?size=64",
            'image': f"{base_url}/{type_id}/render?size=256", 
            'render': f"{base_url}/{type_id}/render?size=512",
            'portrait': f"{base_url}/{type_id}/portrait?size=256",
            'icon_small': f"{base_url}/{type_id}/icon?size=32",
            'icon_large': f"{base_url}/{type_id}/icon?size=128",
            'render_small': f"{base_url}/{type_id}/render?size=128",
            'render_large': f"{base_url}/{type_id}/render?size=1024"
        }
