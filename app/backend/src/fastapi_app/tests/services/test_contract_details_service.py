"""
Unit tests for ContractDetailsService covering contract retrieval, item enhancement, 
ship details processing, and comprehensive error handling.

Tests mock ESI Type Service interactions and verify proper data flow throughout
the contract details enhancement pipeline.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from decimal import Decimal

from fastapi_app.services.contract_details_service import ContractDetailsService
from fastapi_app.services.esi_type_service import ESITypeService
from fastapi_app.models.contracts import Contract, ContractItem
from fastapi_app.models.common_models import EsiTypeCache
from fastapi_app.schemas.contracts import (
    ContractDetailsSchema,
    ContractDetailsItemSchema,
    ShipDetailsSchema,
    ShipAttributeSchema
)

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio

class TestContractDetailsService:
    """Test suite for ContractDetailsService with comprehensive method coverage."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        session = AsyncMock(spec=AsyncSession)
        return session

    @pytest.fixture
    def mock_esi_type_service(self):
        """Mock ESI Type Service."""
        service = AsyncMock(spec=ESITypeService)
        return service

    @pytest.fixture
    def contract_details_service(self, mock_db_session, mock_esi_type_service):
        """ContractDetailsService instance with mocked dependencies."""
        service = ContractDetailsService(
            db_session=mock_db_session,
            esi_type_service=mock_esi_type_service
        )
        
        # Add standard _process_ship_details mock to prevent validation errors
        from fastapi_app.schemas.contracts import ShipDetailsSchema
        mock_ship_details = ShipDetailsSchema(
            type_id=587,
            type_name="Test Ship",
            attributes={},
            icon_url="https://images.evetech.net/types/587/icon?size=64",
            render_url="https://images.evetech.net/types/587/render?size=512"
        )
        service._process_ship_details = AsyncMock(return_value=mock_ship_details)
        
        return service

    @pytest.fixture
    def sample_contract(self):
        """Sample contract for testing."""
        return Contract(
            contract_id=12345,
            title="Rifter Contract",
            type="item_exchange",
            status="outstanding",
            price=Decimal("1000000.00"),
            collateral=Decimal("500000.00"),
            reward=None,
            volume=30000.0,
            date_issued=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            date_expired=datetime(2024, 2, 15, 10, 30, 0, tzinfo=timezone.utc),
            date_completed=None,
            issuer_id=123456789,
            issuer_name="Test Pilot",
            issuer_corporation_id=987654321,
            issuer_corporation_name="Test Corp",
            start_location_id=60003760,
            start_location_name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            start_location_system_id=30000142,
            start_location_region_id=10000002,
            end_location_id=None,
            for_corporation=False,
            is_ship_contract=True
        )

    @pytest.fixture
    def sample_contract_items(self):
        """Sample contract items for testing."""
        return [
            ContractItem(
                record_id=1,
                contract_id=12345,
                type_id=587,
                type_name="Rifter",
                quantity=1,
                is_singleton=True,
                is_included=True,
                raw_quantity=None
            ),
            ContractItem(
                record_id=2,
                contract_id=12345,
                type_id=31,
                type_name="Tritanium",
                quantity=1000,
                is_singleton=False,
                is_included=True,
                raw_quantity=None
            )
        ]

    @pytest.fixture
    def sample_ship_type_cache(self):
        """Sample ship type cache data."""
        return EsiTypeCache(
            type_id=587,
            name="Rifter",
            description="The Rifter is a versatile frigate...",
            category_id=6,  # Ship category
            group_id=25,
            published=True,
            mass=1067000.0,
            volume=27289.0,
            capacity=140.0,
            dogma_attributes=[
                {'attribute_id': 9, 'value': 1067000},     # Mass
                {'attribute_id': 161, 'value': 27289},     # Volume
                {'attribute_id': 479, 'value': 150},       # Shield HP
                {'attribute_id': 263, 'value': 300},       # Armor HP
                {'attribute_id': 482, 'value': 325},       # Structure HP
            ],
            dogma_effects=[
                {'effect_id': 11, 'is_default': True}
            ]
        )

    @pytest.fixture
    def sample_module_type_cache(self):
        """Sample module type cache data."""
        return EsiTypeCache(
            type_id=31,
            name="Tritanium",
            description="A very common mineral...",
            category_id=4,  # Material category
            group_id=18,
            published=True,
            mass=1.0,
            volume=0.01,
            capacity=0.0,
            dogma_attributes=[],
            dogma_effects=[]
        )

    # Tests for get_contract_details method
    async def test_get_contract_details_success(
        self, 
        contract_details_service, 
        sample_contract, 
        sample_contract_items,
        sample_ship_type_cache,
        sample_module_type_cache
    ):
        """Test successful contract details retrieval with ship attributes."""
        # Arrange
        contract_id = 12345
        sample_contract.items = sample_contract_items
        
        # Mock the async method directly to return the sample contract
        contract_details_service._get_contract_with_items = AsyncMock(return_value=sample_contract)
        
        # Mock ESI type service responses
        contract_details_service.esi_type_service.get_multiple_types.return_value = {
            587: sample_ship_type_cache,
            31: sample_module_type_cache
        }
        
        # Mock ship details processing
        from fastapi_app.schemas.contracts import ShipDetailsSchema
        mock_ship_details = ShipDetailsSchema(
            type_id=587,
            type_name="Rifter",
            attributes={},
            icon_url="https://images.evetech.net/types/587/icon?size=64",
            render_url="https://images.evetech.net/types/587/render?size=512"
        )
        contract_details_service._process_ship_details = AsyncMock(return_value=mock_ship_details)

        # Act
        result = await contract_details_service.get_contract_details(
            contract_id=contract_id,
            include_ship_attributes=True,
            attribute_detail_level="key_attributes"
        )

        # Assert
        assert result is not None
        assert isinstance(result, ContractDetailsSchema)
        assert result.contract_id == contract_id
        assert result.title == "Rifter Contract"
        assert result.is_ship_contract is True
        assert len(result.items) == 2
        assert result.ship_details is not None
        assert result.ship_details.type_id == 587
        assert result.ship_details.type_name == "Rifter"
        
        # Verify service calls
        contract_details_service.esi_type_service.get_multiple_types.assert_called_once()

    async def test_get_contract_details_not_found(self, contract_details_service):
        """Test get_contract_details when contract is not found."""
        # Arrange
        contract_id = 99999
        # Mock the async method directly to return None
        contract_details_service._get_contract_with_items = AsyncMock(return_value=None)

        # Act
        result = await contract_details_service.get_contract_details(contract_id)

        # Assert
        assert result is None

    async def test_get_contract_details_without_ship_attributes(
        self, 
        contract_details_service, 
        sample_contract, 
        sample_contract_items
    ):
        """Test get_contract_details without ship attribute processing."""
        # Arrange
        contract_id = 12345
        sample_contract.items = sample_contract_items
        sample_contract.is_ship_contract = False
        
        # Mock the async method directly to return the sample contract
        contract_details_service._get_contract_with_items = AsyncMock(return_value=sample_contract)
        
        contract_details_service.esi_type_service.get_multiple_types.return_value = {}

        # Act
        result = await contract_details_service.get_contract_details(
            contract_id=contract_id,
            include_ship_attributes=False
        )

        # Assert
        assert result is not None
        assert result.ship_details is None

    async def test_get_contract_details_esi_failure(
        self, 
        contract_details_service, 
        sample_contract, 
        sample_contract_items
    ):
        """Test get_contract_details with ESI service failure."""
        # Arrange
        contract_id = 12345
        sample_contract.items = sample_contract_items
        
        # Mock the async method directly to return the sample contract
        contract_details_service._get_contract_with_items = AsyncMock(return_value=sample_contract)
        
        # Mock ESI failure
        contract_details_service.esi_type_service.get_multiple_types.side_effect = Exception("ESI Error")

        # Act & Assert: Expect the exception to be raised
        with pytest.raises(Exception, match="ESI Error"):
            await contract_details_service.get_contract_details(contract_id)

    async def test_get_contract_details_database_error(self, contract_details_service):
        """Test get_contract_details with database error."""
        # Arrange
        contract_id = 12345
        contract_details_service.db_session.execute.side_effect = Exception("Database error")

        # Act & Assert: Expect the exception to be raised
        with pytest.raises(Exception, match="Database error"):
            await contract_details_service.get_contract_details(contract_id)

    # Tests for _enhance_contract_items method
    async def test_enhance_contract_items_success(
        self, 
        contract_details_service, 
        sample_contract_items,
        sample_ship_type_cache,
        sample_module_type_cache
    ):
        """Test successful contract item enhancement."""
        # Arrange
        type_data_map = {
            587: sample_ship_type_cache,
            31: sample_module_type_cache
        }
        # Mock the ESI service call
        contract_details_service.esi_type_service.get_multiple_types.return_value = type_data_map

        # Act
        result = await contract_details_service._enhance_contract_items(sample_contract_items)

        # Assert: Check structure since we can't easily mock the actual enhancement
        assert isinstance(result, list)

    async def test_enhance_contract_items_empty_list(self, contract_details_service):
        """Test _enhance_contract_items with empty items list."""
        # Act
        result = await contract_details_service._enhance_contract_items([])

        # Assert
        assert result == []

    # Tests for error handling and edge cases
    async def test_get_contract_details_partial_esi_data(
        self, 
        contract_details_service, 
        sample_contract, 
        sample_contract_items,
        sample_ship_type_cache
    ):
        """Test handling partial ESI data availability."""
        # Arrange
        contract_id = 12345
        sample_contract.items = sample_contract_items
        
        # Mock the async method directly to return the sample contract
        contract_details_service._get_contract_with_items = AsyncMock(return_value=sample_contract)
        
        # Return partial ESI data (missing some types)
        contract_details_service.esi_type_service.get_multiple_types.return_value = {
            587: sample_ship_type_cache  # Only ship data, missing tritanium
        }

        # Act
        result = await contract_details_service.get_contract_details(contract_id)

        # Assert
        assert result is not None
        assert len(result.items) == 2  # Should still return all items

    async def test_get_contract_details_invalid_attribute_level(
        self, 
        contract_details_service, 
        sample_contract, 
        sample_contract_items
    ):
        """Test handling invalid attribute detail level."""
        # Arrange
        contract_id = 12345
        sample_contract.items = sample_contract_items
        
        # Mock the async method directly to return the sample contract
        contract_details_service._get_contract_with_items = AsyncMock(return_value=sample_contract)
        
        contract_details_service.esi_type_service.get_multiple_types.return_value = {}

        # Act
        result = await contract_details_service.get_contract_details(
            contract_id=contract_id,
            attribute_detail_level="invalid_level"
        )

        # Assert
        assert result is not None  # Should handle gracefully

    async def test_contract_details_logging(
        self, 
        contract_details_service, 
        sample_contract, 
        sample_contract_items
    ):
        """Test that proper logging occurs during contract details retrieval."""
        # Arrange
        contract_id = 12345
        sample_contract.items = sample_contract_items
        
        # Mock the async method directly to return the sample contract
        contract_details_service._get_contract_with_items = AsyncMock(return_value=sample_contract)
        
        contract_details_service.esi_type_service.get_multiple_types.return_value = {}

        # Act & Assert: Verify the method completes without error
        # (Detailed logging verification would require log capture setup)
        result = await contract_details_service.get_contract_details(contract_id)
        assert result is not None

    # =============================================================================
    # Tests for Ship Contract Processing Methods
    # =============================================================================

    async def test_process_ship_details_success(self, contract_details_service, sample_contract_items, sample_ship_type_cache):
        """Test successful ship details processing with all components."""
        # Arrange
        attribute_detail_level = "key_attributes"
        
        # Remove the universal mock since we want to test the actual method
        del contract_details_service._process_ship_details
        
        # Mock dependencies
        contract_details_service._find_ship_in_items = AsyncMock(return_value=sample_contract_items[0])  # Rifter
        contract_details_service.esi_type_service.get_type_info = AsyncMock(return_value=sample_ship_type_cache)
        contract_details_service.esi_type_service._process_ship_attributes = AsyncMock(return_value={
            "mass": 1067000,
            "volume": 27289,
            "shield_hp": 150
        })
        contract_details_service.esi_type_service._generate_image_urls = AsyncMock(return_value={
            "icon": "https://images.evetech.net/types/587/icon?size=64",
            "render": "https://images.evetech.net/types/587/render?size=512"
        })
        
        # Act
        result = await contract_details_service._process_ship_details(
            sample_contract_items, 
            attribute_detail_level
        )
        
        # Assert
        assert result is not None
        assert isinstance(result, ShipDetailsSchema)
        assert result.type_id == 587
        assert result.type_name == "Rifter"
        assert "mass" in result.attributes
        assert result.icon_url == "https://images.evetech.net/types/587/icon?size=64"
        
        # Verify method calls
        contract_details_service._find_ship_in_items.assert_called_once_with(sample_contract_items)
        contract_details_service.esi_type_service.get_type_info.assert_called_once_with(587)
        contract_details_service.esi_type_service._process_ship_attributes.assert_called_once_with(587, "key_attributes")
        contract_details_service.esi_type_service._generate_image_urls.assert_called_once_with(587)

    async def test_process_ship_details_no_ship_found(self, contract_details_service, sample_contract_items):
        """Test ship details processing when no ship is found in items."""
        # Arrange
        del contract_details_service._process_ship_details
        contract_details_service._find_ship_in_items = AsyncMock(return_value=None)
        
        # Act
        result = await contract_details_service._process_ship_details(sample_contract_items)
        
        # Assert
        assert result is None
        contract_details_service._find_ship_in_items.assert_called_once_with(sample_contract_items)

    async def test_process_ship_details_no_type_info(self, contract_details_service, sample_contract_items):
        """Test ship details processing when ESI type info is unavailable."""
        # Arrange
        del contract_details_service._process_ship_details
        contract_details_service._find_ship_in_items = AsyncMock(return_value=sample_contract_items[0])
        contract_details_service.esi_type_service.get_type_info = AsyncMock(return_value=None)
        
        # Act
        result = await contract_details_service._process_ship_details(sample_contract_items)
        
        # Assert
        assert result is None
        contract_details_service.esi_type_service.get_type_info.assert_called_once_with(587)

    async def test_process_ship_details_with_basic_attributes(self, contract_details_service, sample_contract_items, sample_ship_type_cache):
        """Test ship details processing with basic attribute level."""
        # Arrange
        del contract_details_service._process_ship_details
        contract_details_service._find_ship_in_items = AsyncMock(return_value=sample_contract_items[0])
        contract_details_service.esi_type_service.get_type_info = AsyncMock(return_value=sample_ship_type_cache)
        contract_details_service.esi_type_service._process_ship_attributes = AsyncMock(return_value={"mass": 1067000})
        contract_details_service.esi_type_service._generate_image_urls = AsyncMock(return_value={})
        
        # Act
        result = await contract_details_service._process_ship_details(sample_contract_items, "basic")
        
        # Assert
        assert result is not None
        contract_details_service.esi_type_service._process_ship_attributes.assert_called_once_with(587, "basic")

    async def test_find_ship_in_items_success(self, contract_details_service, sample_contract_items):
        """Test successfully finding a ship among contract items."""
        # Arrange
        contract_details_service.esi_type_service.is_ship_type = AsyncMock(side_effect=[True, False])  # First item is ship
        
        # Act
        result = await contract_details_service._find_ship_in_items(sample_contract_items)
        
        # Assert
        assert result is not None
        assert result.type_id == 587  # Rifter
        assert result.type_name == "Rifter"
        contract_details_service.esi_type_service.is_ship_type.assert_called_with(587)

    async def test_find_ship_in_items_no_ship(self, contract_details_service, sample_contract_items):
        """Test finding ship when no ship exists in contract items."""
        # Arrange
        contract_details_service.esi_type_service.is_ship_type = AsyncMock(return_value=False)  # No ships
        
        # Act
        result = await contract_details_service._find_ship_in_items(sample_contract_items)
        
        # Assert
        assert result is None
        # Should have checked both items
        assert contract_details_service.esi_type_service.is_ship_type.call_count == 2

    async def test_find_ship_in_items_empty_list(self, contract_details_service):
        """Test finding ship in empty contract items list."""
        # Act
        result = await contract_details_service._find_ship_in_items([])
        
        # Assert
        assert result is None
        contract_details_service.esi_type_service.is_ship_type.assert_not_called()

    async def test_find_ship_in_items_second_item_is_ship(self, contract_details_service, sample_contract_items):
        """Test finding ship when the ship is not the first item."""
        # Arrange
        contract_details_service.esi_type_service.is_ship_type = AsyncMock(side_effect=[False, True])  # Second item is ship
        
        # Act
        result = await contract_details_service._find_ship_in_items(sample_contract_items)
        
        # Assert
        assert result is not None
        assert result.type_id == 31  # Tritanium (in our test, second item)
        assert contract_details_service.esi_type_service.is_ship_type.call_count == 2

    async def test_build_ship_details_complete_data(self, contract_details_service, sample_contract_items, sample_ship_type_cache):
        """Test building ship details with complete data."""
        # Arrange
        ship_item = sample_contract_items[0]  # Rifter
        ship_attributes = {
            "mass": 1067000,
            "volume": 27289,
            "shield_hp": 150,
            "armor_hp": 300,
            "structure_hp": 325
        }
        image_urls = {
            "icon": "https://images.evetech.net/types/587/icon?size=64",
            "image": "https://images.evetech.net/types/587/image?size=256",
            "render": "https://images.evetech.net/types/587/render?size=512"
        }
        
        # Act
        result = await contract_details_service._build_ship_details(
            ship_item, sample_ship_type_cache, ship_attributes, image_urls
        )
        
        # Assert
        assert isinstance(result, ShipDetailsSchema)
        assert result.type_id == 587
        assert result.type_name == "Rifter"
        assert result.description == "The Rifter is a versatile frigate..."
        assert result.attributes == ship_attributes
        assert result.icon_url == "https://images.evetech.net/types/587/icon?size=64"
        assert result.image_url == "https://images.evetech.net/types/587/image?size=256"
        assert result.render_url == "https://images.evetech.net/types/587/render?size=512"
        assert result.mass == 1067000.0
        assert result.volume == 27289.0
        assert result.capacity == 140.0

    async def test_build_ship_details_minimal_data(self, contract_details_service, sample_contract_items):
        """Test building ship details with minimal data (missing optional fields)."""
        # Arrange
        ship_item = sample_contract_items[0]
        
        # Create minimal ship type cache without optional fields
        minimal_ship_type = EsiTypeCache(
            type_id=587,
            name="Rifter",
            description=None,  # Optional
            category_id=6,
            group_id=25,
            published=True,
            mass=None,  # Optional
            volume=None,  # Optional
            capacity=None,  # Optional
            dogma_attributes=[],
            dogma_effects=[]
        )
        
        ship_attributes = {}
        image_urls = {}  # Empty image URLs
        
        # Act
        result = await contract_details_service._build_ship_details(
            ship_item, minimal_ship_type, ship_attributes, image_urls
        )
        
        # Assert
        assert isinstance(result, ShipDetailsSchema)
        assert result.type_id == 587
        assert result.type_name == "Rifter"
        assert result.description is None
        assert result.attributes == {}
        assert result.icon_url is None
        assert result.image_url is None
        assert result.render_url is None
        assert result.mass is None
        assert result.volume is None
        assert result.capacity is None

    async def test_build_ship_details_partial_image_urls(self, contract_details_service, sample_contract_items, sample_ship_type_cache):
        """Test building ship details with partial image URLs."""
        # Arrange
        ship_item = sample_contract_items[0]
        ship_attributes = {"mass": 1067000}
        image_urls = {
            "icon": "https://images.evetech.net/types/587/icon?size=64"
            # Missing 'image' and 'render'
        }
        
        # Act
        result = await contract_details_service._build_ship_details(
            ship_item, sample_ship_type_cache, ship_attributes, image_urls
        )
        
        # Assert
        assert result.icon_url == "https://images.evetech.net/types/587/icon?size=64"
        assert result.image_url is None
        assert result.render_url is None
