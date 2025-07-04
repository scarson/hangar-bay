"""
Unit tests for ESITypeService covering all methods with comprehensive coverage.

Tests include cache behavior, ESI data fetching, ship type validation, and attribute extraction.
All ESI client responses and database interactions are mocked for isolated testing.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from fastapi_app.services.esi_type_service import ESITypeService
from fastapi_app.models.common_models import EsiTypeCache
from fastapi_app.core.esi_client_class import ESIClient


class TestESITypeService:
    """Test suite for ESITypeService with comprehensive method coverage."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        session = AsyncMock(spec=AsyncSession)
        return session

    @pytest.fixture
    def mock_esi_client(self):
        """Mock ESI client."""
        client = AsyncMock(spec=ESIClient)
        return client

    @pytest.fixture
    def esi_type_service(self, mock_db_session, mock_esi_client):
        """ESITypeService instance with mocked dependencies."""
        return ESITypeService(
            db_session=mock_db_session,
            esi_client=mock_esi_client
        )

    @pytest.fixture
    def sample_esi_type_data(self):
        """Sample ESI type data for testing."""
        return {
            'type_id': 587,
            'name': 'Rifter',
            'description': 'The Rifter is a versatile frigate...',
            'category_id': 6,
            'group_id': 25,
            'published': True,
            'mass': 1067000,
            'volume': 27289,
            'capacity': 140,
            'portion_size': 1,
            'dogma_attributes': [
                {'attribute_id': 9, 'value': 1067000},  # Mass
                {'attribute_id': 161, 'value': 27289},  # Volume
            ],
            'dogma_effects': [
                {'effect_id': 11, 'is_default': True}
            ]
        }

    @pytest.fixture
    def sample_cached_type(self):
        """Sample cached type for testing."""
        return EsiTypeCache(
            type_id=587,
            name='Rifter',
            description='The Rifter is a versatile frigate...',
            category_id=6,
            group_id=25,
            published=True,
            mass=1067000.0,
            volume=27289.0,
            capacity=140.0,
            dogma_attributes=[
                {'attribute_id': 9, 'value': 1067000},
                {'attribute_id': 161, 'value': 27289},
            ],
            dogma_effects=[
                {'effect_id': 11, 'is_default': True}
            ]
        )

    # Tests for get_type_info method
    @pytest.mark.asyncio
    async def test_get_type_info_from_cache(self, esi_type_service, sample_cached_type):
        """Test get_type_info returns cached data when available."""
        # Arrange
        type_id = 587
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_cached_type
        esi_type_service.db_session.execute = AsyncMock(return_value=mock_result)

        # Act
        result = await esi_type_service.get_type_info(type_id)

        # Assert
        assert result == sample_cached_type
        esi_type_service.db_session.execute.assert_called_once()
        esi_type_service.esi_client.get_type_info.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_type_info_fetch_from_esi(self, esi_type_service, sample_esi_type_data):
        """Test get_type_info fetches from ESI when not cached."""
        # Arrange
        type_id = 587
        esi_type_service.esi_client.get_type_info.return_value = sample_esi_type_data
        
        # Mock the database operations sequence
        cache_miss_result = Mock()
        cache_miss_result.scalar_one_or_none.return_value = None
        
        upsert_result = Mock()
        upsert_result.inserted_primary_key = [type_id]
        
        esi_type_service.db_session.execute = AsyncMock(side_effect=[
            cache_miss_result,  # Cache miss
            upsert_result,  # Upsert result
        ])

        # Act
        result = await esi_type_service.get_type_info(type_id)

        # Assert
        esi_type_service.esi_client.get_type_info.assert_called_once_with(type_id)
        assert esi_type_service.db_session.execute.call_count == 2  # Cache check, upsert

    @pytest.mark.asyncio
    async def test_get_type_info_esi_failure(self, esi_type_service):
        """Test get_type_info handles ESI failures gracefully."""
        # Arrange
        type_id = 587
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        esi_type_service.db_session.execute = AsyncMock(return_value=mock_result)
        esi_type_service.esi_client.get_type_info.side_effect = Exception("ESI API Error")

        # Act
        result = await esi_type_service.get_type_info(type_id)

        # Assert
        assert result is None
        esi_type_service.esi_client.get_type_info.assert_called_once_with(type_id)

    # Tests for get_multiple_types method
    @pytest.mark.asyncio
    async def test_get_multiple_types_empty_list(self, esi_type_service):
        """Test get_multiple_types handles empty input."""
        # Act
        result = await esi_type_service.get_multiple_types([])

        # Assert
        assert result == {}
        esi_type_service.db_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_multiple_types_all_cached(self, esi_type_service, sample_cached_type):
        """Test get_multiple_types with all types cached."""
        # Arrange
        type_ids = [587, 588]
        cached_types = [
            sample_cached_type,
            EsiTypeCache(type_id=588, name='Punisher', category_id=6)
        ]
        mock_scalars = Mock()
        mock_scalars.all.return_value = cached_types
        mock_result = Mock()
        mock_result.scalars.return_value = mock_scalars
        esi_type_service.db_session.execute = AsyncMock(return_value=mock_result)

        # Act
        result = await esi_type_service.get_multiple_types(type_ids)

        # Assert
        assert len(result) == 2
        assert 587 in result
        assert 588 in result
        assert result[587].name == 'Rifter'
        assert result[588].name == 'Punisher'
        esi_type_service.esi_client.get_type_info.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_multiple_types_partial_cache(self, esi_type_service, sample_cached_type, sample_esi_type_data):
        """Test get_multiple_types with partial cache hits."""
        # Arrange
        type_ids = [587, 588]
        cached_types = [sample_cached_type]  # Only 587 cached
        
        # Mock ESI response for missing type
        esi_data_588 = {**sample_esi_type_data, 'type_id': 588, 'name': 'Punisher'}
        esi_type_service.esi_client.get_type_info.return_value = esi_data_588
        
        # Mock database operations
        cache_result = Mock()
        cache_scalars = Mock()
        cache_scalars.all.return_value = cached_types
        cache_result.scalars.return_value = cache_scalars
        
        upsert_result = Mock()
        upsert_result.inserted_primary_key = [588]
        
        esi_type_service.db_session.execute = AsyncMock(side_effect=[
            cache_result,  # Cache query
            upsert_result,  # Upsert for 588
        ])

        # Act
        result = await esi_type_service.get_multiple_types(type_ids)

        # Assert
        assert len(result) == 2
        assert 587 in result
        assert 588 in result
        esi_type_service.esi_client.get_type_info.assert_called_once_with(588)

    @pytest.mark.asyncio
    async def test_get_multiple_types_esi_failure_partial(self, esi_type_service, sample_cached_type):
        """Test get_multiple_types handles partial ESI failures."""
        # Arrange
        type_ids = [587, 588, 589]
        cached_types = [sample_cached_type]  # Only 587 cached
        mock_scalars = Mock()
        mock_scalars.all.return_value = cached_types
        mock_result = Mock()
        mock_result.scalars.return_value = mock_scalars
        esi_type_service.db_session.execute = AsyncMock(return_value=mock_result)
        
        # Mock ESI failures for missing types
        esi_type_service.esi_client.get_type_info.side_effect = Exception("ESI Error")

        # Act
        result = await esi_type_service.get_multiple_types(type_ids)

        # Assert
        assert len(result) == 1  # Only cached item returned
        assert 587 in result
        assert 588 not in result
        assert 589 not in result

    # Tests for ship attribute processing
    @pytest.mark.asyncio
    async def test_process_ship_attributes_key_only(self, esi_type_service, sample_cached_type):
        """Test ship attribute processing with key attributes only."""
        # Arrange
        type_id = 587
        esi_type_service.get_type_info = AsyncMock(return_value=sample_cached_type)
        esi_type_service.get_ship_attributes = AsyncMock(return_value={
            'physical': {'mass': 1067000, 'volume': 27289},
            'defensive': {'shield_hp': 150, 'armor_hp': 300}
        })

        # Act
        result = await esi_type_service._process_ship_attributes(
            type_id, 
            detail_level="key_attributes"
        )

        # Assert
        assert 'physical' in result
        assert 'defensive' in result
        assert result['physical']['mass'] == 1067000
        assert result['physical']['volume'] == 27289
        assert result['defensive']['shield_hp'] == 150
        assert result['defensive']['armor_hp'] == 300
        esi_type_service.get_ship_attributes.assert_called_once_with(type_id)

    @pytest.mark.asyncio
    async def test_process_ship_attributes_all(self, esi_type_service, sample_cached_type):
        """Test ship attribute processing with all attributes."""
        # Arrange
        type_id = 587
        sample_cached_type.dogma_attributes = [
            {'attribute_id': 9, 'value': 1067000},     # Mass
            {'attribute_id': 479, 'value': 150},       # Shield HP
            {'attribute_id': 999, 'value': 42},        # Unknown attribute
        ]
        esi_type_service.get_type_info = AsyncMock(return_value=sample_cached_type)

        # Act
        result = await esi_type_service._process_ship_attributes(
            type_id, 
            detail_level="all_attributes"
        )

        # Assert
        assert 'mass' in result
        assert 'dogma_attributes' in result
        assert len(result['dogma_attributes']) == 3
        esi_type_service.get_type_info.assert_called_once_with(type_id)

    # Tests for EVE image server URL generation
    @pytest.mark.asyncio
    async def test_generate_image_urls(self, esi_type_service):
        """Test EVE image server URL generation."""
        # Arrange
        type_id = 587

        # Act
        result = await esi_type_service._generate_image_urls(type_id)

        # Assert
        assert 'icon' in result
        assert 'render' in result
        assert f"types/{type_id}/icon" in result['icon']
        assert f"types/{type_id}/render" in result['render']
        assert result['icon'].startswith('https://images.evetech.net/')
        assert result['render'].startswith('https://images.evetech.net/')

    # Tests for cache operations
    @pytest.mark.asyncio
    async def test_get_cached_type_found(self, esi_type_service, sample_cached_type):
        """Test _get_cached_type when type is found."""
        # Arrange
        type_id = 587
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_cached_type
        esi_type_service.db_session.execute = AsyncMock(return_value=mock_result)

        # Act
        result = await esi_type_service._get_cached_type(type_id)

        # Assert
        assert result == sample_cached_type

    @pytest.mark.asyncio
    async def test_get_cached_type_not_found(self, esi_type_service):
        """Test _get_cached_type when type is not found."""
        # Arrange
        type_id = 587
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        esi_type_service.db_session.execute = AsyncMock(return_value=mock_result)

        # Act
        result = await esi_type_service._get_cached_type(type_id)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_cached_types_multiple(self, esi_type_service, sample_cached_type):
        """Test _get_cached_types with multiple types."""
        # Arrange
        type_ids = [587, 588]
        cached_types = [
            sample_cached_type,
            EsiTypeCache(type_id=588, name='Punisher')
        ]
        mock_scalars = Mock()
        mock_scalars.all.return_value = cached_types
        mock_result = Mock()
        mock_result.scalars.return_value = mock_scalars
        esi_type_service.db_session.execute = AsyncMock(return_value=mock_result)

        # Act
        result = await esi_type_service._get_cached_types(type_ids)

        # Assert
        assert len(result) == 2
        assert result[0].type_id == 587
        assert result[1].type_id == 588

    # Tests for error handling and edge cases
    @pytest.mark.asyncio
    async def test_fetch_and_cache_type_invalid_data(self, esi_type_service):
        """Test _fetch_and_cache_type with invalid ESI response."""
        # Arrange
        type_id = 587
        esi_type_service.esi_client.get_type_info.return_value = None

        # Act
        result = await esi_type_service._fetch_and_cache_type(type_id)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_and_cache_type_database_error(self, esi_type_service, sample_esi_type_data):
        """Test _fetch_and_cache_type with database error during upsert."""
        # Arrange
        type_id = 587
        esi_type_service.esi_client.get_type_info.return_value = sample_esi_type_data
        esi_type_service.db_session.execute.side_effect = Exception("Database error")

        # Act
        result = await esi_type_service._fetch_and_cache_type(type_id)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_is_ship_type_valid_ship(self, esi_type_service, sample_cached_type):
        """Test is_ship_type with valid ship category."""
        # Arrange
        sample_cached_type.category_id = 6  # Ship category
        esi_type_service.get_type_info = AsyncMock(return_value=sample_cached_type)

        # Act
        result = await esi_type_service.is_ship_type(sample_cached_type.type_id)

        # Assert
        assert result is True
        esi_type_service.get_type_info.assert_called_once_with(sample_cached_type.type_id)

    @pytest.mark.asyncio
    async def test_is_ship_type_invalid_ship(self, esi_type_service, sample_cached_type):
        """Test is_ship_type with non-ship category."""
        # Arrange
        sample_cached_type.category_id = 8  # Charge category
        esi_type_service.get_type_info = AsyncMock(return_value=sample_cached_type)

        # Act
        result = await esi_type_service.is_ship_type(sample_cached_type.type_id)

        # Assert
        assert result is False
        esi_type_service.get_type_info.assert_called_once_with(sample_cached_type.type_id)

    @pytest.mark.asyncio
    async def test_is_ship_type_missing_category(self, esi_type_service):
        """Test is_ship_type with missing type info."""
        # Arrange
        esi_type_service.get_type_info = AsyncMock(return_value=None)

        # Act
        result = await esi_type_service.is_ship_type(999)

        # Assert
        assert result is False
        esi_type_service.get_type_info.assert_called_once_with(999)


    # =============================================================================
    # Tests for New Ship Attribute Processing Methods
    # =============================================================================

    @pytest.mark.asyncio
    async def test_process_ship_attributes_basic_level(self, esi_type_service, sample_cached_type):
        """Test _process_ship_attributes with basic detail level."""
        # Arrange
        type_id = 587
        esi_type_service.get_type_info = AsyncMock(return_value=sample_cached_type)
        
        # Act
        result = await esi_type_service._process_ship_attributes(type_id, "basic")
        
        # Assert
        assert result is not None
        assert "mass" in result
        assert "volume" in result
        assert "capacity" in result
        assert "name" in result
        assert "description" in result
        assert result["mass"] == sample_cached_type.mass
        assert result["name"] == sample_cached_type.name
        esi_type_service.get_type_info.assert_called_once_with(type_id)

    @pytest.mark.asyncio
    async def test_process_ship_attributes_key_attributes_level(self, esi_type_service, sample_cached_type):
        """Test _process_ship_attributes with key_attributes detail level."""
        # Arrange
        type_id = 587
        esi_type_service.get_type_info = AsyncMock(return_value=sample_cached_type)
        esi_type_service.get_ship_attributes = AsyncMock(return_value={
            "defensive": {"shield_hp": 150, "armor_hp": 300},
            "physical": {"mass": 1067000, "volume": 27289}
        })
        
        # Act
        result = await esi_type_service._process_ship_attributes(type_id, "key_attributes")
        
        # Assert
        assert result is not None
        assert "defensive" in result
        assert "physical" in result
        esi_type_service.get_ship_attributes.assert_called_once_with(type_id)

    @pytest.mark.asyncio
    async def test_process_ship_attributes_all_attributes_level(self, esi_type_service, sample_cached_type):
        """Test _process_ship_attributes with all_attributes detail level."""
        # Arrange
        type_id = 587
        sample_cached_type.dogma_attributes = [{"attribute_id": 9, "value": 1067000}]
        sample_cached_type.dogma_effects = [{"effect_id": 11, "is_default": True}]
        sample_cached_type.market_group_id = 123
        esi_type_service.get_type_info = AsyncMock(return_value=sample_cached_type)
        
        # Act
        result = await esi_type_service._process_ship_attributes(type_id, "all_attributes")
        
        # Assert
        assert result is not None
        assert "mass" in result
        assert "category_id" in result
        assert "group_id" in result
        assert "dogma_attributes" in result
        assert "dogma_effects" in result
        assert result["dogma_attributes"] == sample_cached_type.dogma_attributes
        assert result["dogma_effects"] == sample_cached_type.dogma_effects

    @pytest.mark.asyncio
    async def test_process_ship_attributes_no_type_info(self, esi_type_service):
        """Test _process_ship_attributes when type info is not available."""
        # Arrange
        type_id = 587
        esi_type_service.get_type_info = AsyncMock(return_value=None)
        
        # Act
        result = await esi_type_service._process_ship_attributes(type_id, "basic")
        
        # Assert
        assert result == {}
        esi_type_service.get_type_info.assert_called_once_with(type_id)

    @pytest.mark.asyncio
    async def test_process_ship_attributes_invalid_detail_level(self, esi_type_service, sample_cached_type):
        """Test _process_ship_attributes with invalid detail level defaults to all_attributes."""
        # Arrange
        type_id = 587
        esi_type_service.get_type_info = AsyncMock(return_value=sample_cached_type)
        
        # Act
        result = await esi_type_service._process_ship_attributes(type_id, "invalid_level")
        
        # Assert
        assert result is not None
        assert "mass" in result
        assert "category_id" in result  # Should have all attributes

    def test_extract_basic_ship_attributes_complete_data(self, esi_type_service, sample_cached_type):
        """Test _extract_basic_ship_attributes with complete type data."""
        # Act
        result = esi_type_service._extract_basic_ship_attributes(sample_cached_type)
        
        # Assert
        assert result is not None
        assert len(result) == 5  # mass, volume, capacity, name, description
        assert result["mass"] == sample_cached_type.mass
        assert result["volume"] == sample_cached_type.volume
        assert result["capacity"] == sample_cached_type.capacity
        assert result["name"] == sample_cached_type.name
        assert result["description"] == sample_cached_type.description

    def test_extract_basic_ship_attributes_minimal_data(self, esi_type_service):
        """Test _extract_basic_ship_attributes with minimal type data."""
        # Arrange - Create minimal type cache with only required fields
        minimal_type = EsiTypeCache(
            type_id=587,
            name="Minimal Ship",
            description=None,
            category_id=6,
            group_id=25,
            published=True,
            mass=None,
            volume=None,
            capacity=None,
            dogma_attributes=[],
            dogma_effects=[]
        )
        
        # Act
        result = esi_type_service._extract_basic_ship_attributes(minimal_type)
        
        # Assert
        assert result["mass"] is None
        assert result["volume"] is None
        assert result["capacity"] is None
        assert result["name"] == "Minimal Ship"
        assert result["description"] is None

    def test_extract_all_ship_attributes_complete_data(self, esi_type_service, sample_cached_type):
        """Test _extract_all_ship_attributes with complete type data including dogma."""
        # Arrange
        sample_cached_type.dogma_attributes = [
            {"attribute_id": 9, "value": 1067000},
            {"attribute_id": 161, "value": 27289}
        ]
        sample_cached_type.dogma_effects = [
            {"effect_id": 11, "is_default": True},
            {"effect_id": 12, "is_default": False}
        ]
        sample_cached_type.market_group_id = 123
        
        # Act
        result = esi_type_service._extract_all_ship_attributes(sample_cached_type)
        
        # Assert
        assert len(result) >= 8  # Basic + extended attributes
        assert result["mass"] == sample_cached_type.mass
        assert result["category_id"] == sample_cached_type.category_id
        assert result["group_id"] == sample_cached_type.group_id
        assert result["market_group_id"] == sample_cached_type.market_group_id
        assert result["dogma_attributes"] == sample_cached_type.dogma_attributes
        assert result["dogma_effects"] == sample_cached_type.dogma_effects
        assert len(result["dogma_attributes"]) == 2
        assert len(result["dogma_effects"]) == 2

    def test_extract_all_ship_attributes_no_dogma_data(self, esi_type_service, sample_cached_type):
        """Test _extract_all_ship_attributes when dogma data is not available."""
        # Arrange
        sample_cached_type.dogma_attributes = None
        sample_cached_type.dogma_effects = None
        
        # Act
        result = esi_type_service._extract_all_ship_attributes(sample_cached_type)
        
        # Assert
        assert "dogma_attributes" not in result
        assert "dogma_effects" not in result
        assert result["mass"] == sample_cached_type.mass
        assert result["category_id"] == sample_cached_type.category_id

    def test_extract_all_ship_attributes_empty_dogma_lists(self, esi_type_service, sample_cached_type):
        """Test _extract_all_ship_attributes with empty dogma lists."""
        # Arrange
        sample_cached_type.dogma_attributes = []
        sample_cached_type.dogma_effects = []
        
        # Act
        result = esi_type_service._extract_all_ship_attributes(sample_cached_type)
        
        # Assert
        assert "dogma_attributes" not in result  # Empty lists are excluded  
        assert "dogma_effects" not in result
        assert result["mass"] == sample_cached_type.mass

    # =============================================================================
    # Tests for Enhanced Image URL Generation Method
    # =============================================================================

    @pytest.mark.asyncio
    async def test_generate_image_urls_comprehensive(self, esi_type_service):
        """Test _generate_image_urls with comprehensive URL generation."""
        # Arrange
        type_id = 587  # Rifter
        
        # Act
        result = await esi_type_service._generate_image_urls(type_id)
        
        # Assert
        assert result is not None
        assert len(result) == 8  # All 8 image URL types
        
        # Verify all required URL types exist
        expected_keys = [
            'icon', 'image', 'render', 'portrait',
            'icon_small', 'icon_large', 'render_small', 'render_large'
        ]
        for key in expected_keys:
            assert key in result
            assert f"{type_id}" in result[key]
            assert "https://images.evetech.net/types" in result[key]
        
        # Verify specific URL formats
        assert result['icon'] == f"https://images.evetech.net/types/{type_id}/icon?size=64"
        assert result['image'] == f"https://images.evetech.net/types/{type_id}/render?size=256"
        assert result['render'] == f"https://images.evetech.net/types/{type_id}/render?size=512"
        assert result['portrait'] == f"https://images.evetech.net/types/{type_id}/portrait?size=256"
        assert result['icon_small'] == f"https://images.evetech.net/types/{type_id}/icon?size=32"
        assert result['icon_large'] == f"https://images.evetech.net/types/{type_id}/icon?size=128"
        assert result['render_small'] == f"https://images.evetech.net/types/{type_id}/render?size=128"
        assert result['render_large'] == f"https://images.evetech.net/types/{type_id}/render?size=1024"

    @pytest.mark.asyncio
    async def test_generate_image_urls_different_type_ids(self, esi_type_service):
        """Test _generate_image_urls with different type IDs to ensure proper templating."""
        # Arrange & Act
        test_type_ids = [587, 588, 11129, 25]  # Different ship types
        
        for type_id in test_type_ids:
            result = await esi_type_service._generate_image_urls(type_id)
            
            # Assert each type_id is properly embedded in URLs
            assert str(type_id) in result['icon']
            assert str(type_id) in result['render']
            assert result['icon'].startswith("https://images.evetech.net/types/")
            assert f"/{type_id}/" in result['icon']

    @pytest.mark.asyncio
    async def test_generate_image_urls_edge_cases(self, esi_type_service):
        """Test _generate_image_urls with edge case type IDs."""
        # Test with large type ID
        result_large = await esi_type_service._generate_image_urls(999999999)
        assert "999999999" in result_large['icon']
        
        # Test with zero type ID
        result_zero = await esi_type_service._generate_image_urls(0)
        assert "0" in result_zero['icon']
        assert result_zero['icon'] == "https://images.evetech.net/types/0/icon?size=64"

    @pytest.mark.asyncio
    async def test_generate_image_urls_url_structure_validation(self, esi_type_service):
        """Test _generate_image_urls validates proper URL structure and parameters."""
        # Arrange
        type_id = 587
        
        # Act
        result = await esi_type_service._generate_image_urls(type_id)
        
        # Assert URL structure components
        for url_type, url in result.items():
            # All URLs should start with the base EVE image server
            assert url.startswith("https://images.evetech.net/types/")
            
            # All URLs should contain the type_id
            assert f"/{type_id}/" in url
            
            # All URLs should have size parameter
            assert "?size=" in url
            
            # Verify expected endpoints
            if 'icon' in url_type:
                assert "/icon?" in url
            elif 'render' in url_type:
                assert "/render?" in url
            elif 'portrait' in url_type:
                assert "/portrait?" in url
            elif url_type == 'image':
                assert "/render?" in url  # image uses render endpoint