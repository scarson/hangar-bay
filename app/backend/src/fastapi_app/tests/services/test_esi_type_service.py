"""
Unit tests for ESITypeService covering all methods with comprehensive coverage.

Tests include cache behavior, ESI data fetching, ship type validation, and attribute extraction.
All ESI client responses and database interactions are mocked for isolated testing.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from fastapi_app.services.esi_type_service import ESITypeService
from fastapi_app.models.common_models import EsiTypeCache
from fastapi_app.clients.esi_client import ESIClient


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
            portion_size=1,
            dogma_attributes=[
                {'attribute_id': 9, 'value': 1067000},
                {'attribute_id': 161, 'value': 27289},
            ],
            dogma_effects=[
                {'effect_id': 11, 'is_default': True}
            ],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

    # Tests for get_type_info method
    async def test_get_type_info_from_cache(self, esi_type_service, sample_cached_type):
        """Test get_type_info returns cached data when available."""
        # Arrange
        type_id = 587
        esi_type_service.db_session.execute.return_value.scalar_one_or_none.return_value = sample_cached_type

        # Act
        result = await esi_type_service.get_type_info(type_id)

        # Assert
        assert result == sample_cached_type
        esi_type_service.db_session.execute.assert_called_once()
        esi_type_service.esi_client.get_type_info.assert_not_called()

    async def test_get_type_info_fetch_from_esi(self, esi_type_service, sample_esi_type_data):
        """Test get_type_info fetches from ESI when not cached."""
        # Arrange
        type_id = 587
        esi_type_service.db_session.execute.return_value.scalar_one_or_none.return_value = None
        esi_type_service.esi_client.get_type_info.return_value = sample_esi_type_data
        
        # Mock the upsert operation
        mock_result = AsyncMock()
        mock_result.inserted_primary_key = [type_id]
        esi_type_service.db_session.execute.side_effect = [
            AsyncMock(scalar_one_or_none=AsyncMock(return_value=None)),  # Cache miss
            mock_result,  # Upsert result
            AsyncMock(scalar_one_or_none=AsyncMock(return_value=sample_esi_type_data))  # Fetch after insert
        ]

        # Act
        result = await esi_type_service.get_type_info(type_id)

        # Assert
        esi_type_service.esi_client.get_type_info.assert_called_once_with(type_id)
        assert esi_type_service.db_session.execute.call_count == 3  # Cache check, upsert, fetch after insert

    async def test_get_type_info_esi_failure(self, esi_type_service):
        """Test get_type_info handles ESI failures gracefully."""
        # Arrange
        type_id = 587
        esi_type_service.db_session.execute.return_value.scalar_one_or_none.return_value = None
        esi_type_service.esi_client.get_type_info.side_effect = Exception("ESI API Error")

        # Act
        result = await esi_type_service.get_type_info(type_id)

        # Assert
        assert result is None
        esi_type_service.esi_client.get_type_info.assert_called_once_with(type_id)

    # Tests for get_multiple_types method
    async def test_get_multiple_types_empty_list(self, esi_type_service):
        """Test get_multiple_types handles empty input."""
        # Act
        result = await esi_type_service.get_multiple_types([])

        # Assert
        assert result == {}
        esi_type_service.db_session.execute.assert_not_called()

    async def test_get_multiple_types_all_cached(self, esi_type_service, sample_cached_type):
        """Test get_multiple_types with all types cached."""
        # Arrange
        type_ids = [587, 588]
        cached_types = [
            sample_cached_type,
            EsiTypeCache(type_id=588, name='Punisher', category_id=6)
        ]
        esi_type_service.db_session.execute.return_value.scalars.return_value.all.return_value = cached_types

        # Act
        result = await esi_type_service.get_multiple_types(type_ids)

        # Assert
        assert len(result) == 2
        assert 587 in result
        assert 588 in result
        assert result[587].name == 'Rifter'
        assert result[588].name == 'Punisher'
        esi_type_service.esi_client.get_type_info.assert_not_called()

    async def test_get_multiple_types_partial_cache(self, esi_type_service, sample_cached_type, sample_esi_type_data):
        """Test get_multiple_types with partial cache hits."""
        # Arrange
        type_ids = [587, 588]
        cached_types = [sample_cached_type]  # Only 587 cached
        esi_type_service.db_session.execute.return_value.scalars.return_value.all.return_value = cached_types
        
        # Mock ESI response for missing type
        esi_data_588 = {**sample_esi_type_data, 'type_id': 588, 'name': 'Punisher'}
        esi_type_service.esi_client.get_type_info.return_value = esi_data_588
        
        # Mock upsert for missing type
        mock_result = AsyncMock()
        mock_result.inserted_primary_key = [588]
        esi_type_service.db_session.execute.side_effect = [
            AsyncMock(scalars=AsyncMock(return_value=AsyncMock(all=AsyncMock(return_value=cached_types)))),  # Cache query
            mock_result,  # Upsert for 588
            AsyncMock(scalar_one_or_none=AsyncMock(return_value=EsiTypeCache(type_id=588, name='Punisher')))  # Fetch after insert
        ]

        # Act
        result = await esi_type_service.get_multiple_types(type_ids)

        # Assert
        assert len(result) == 2
        assert 587 in result
        assert 588 in result
        esi_type_service.esi_client.get_type_info.assert_called_once_with(588)

    async def test_get_multiple_types_esi_failure_partial(self, esi_type_service, sample_cached_type):
        """Test get_multiple_types handles partial ESI failures."""
        # Arrange
        type_ids = [587, 588, 589]
        cached_types = [sample_cached_type]  # Only 587 cached
        esi_type_service.db_session.execute.return_value.scalars.return_value.all.return_value = cached_types
        
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
    async def test_process_ship_attributes_key_only(self, esi_type_service, sample_cached_type):
        """Test ship attribute processing with key attributes only."""
        # Arrange
        sample_cached_type.dogma_attributes = [
            {'attribute_id': 9, 'value': 1067000},     # Mass
            {'attribute_id': 161, 'value': 27289},     # Volume  
            {'attribute_id': 38, 'value': 315},        # Capacity
            {'attribute_id': 479, 'value': 150},       # Shield HP
            {'attribute_id': 263, 'value': 300},       # Armor HP
            {'attribute_id': 482, 'value': 325},       # Structure HP
        ]

        # Act
        result = await esi_type_service._process_ship_attributes(
            sample_cached_type, 
            attribute_detail_level="key_attributes"
        )

        # Assert
        assert 'physical' in result
        assert 'defensive' in result
        assert result['physical']['mass'] == 1067000
        assert result['physical']['volume'] == 27289
        assert result['defensive']['shield_hp'] == 150
        assert result['defensive']['armor_hp'] == 300

    async def test_process_ship_attributes_all(self, esi_type_service, sample_cached_type):
        """Test ship attribute processing with all attributes."""
        # Arrange
        sample_cached_type.dogma_attributes = [
            {'attribute_id': 9, 'value': 1067000},     # Mass
            {'attribute_id': 479, 'value': 150},       # Shield HP
            {'attribute_id': 999, 'value': 42},        # Unknown attribute
        ]

        # Act
        result = await esi_type_service._process_ship_attributes(
            sample_cached_type, 
            attribute_detail_level="all_attributes"
        )

        # Assert
        assert 'physical' in result
        assert 'defensive' in result
        assert 'other' in result
        assert len(result['other']) >= 1  # Should include unknown attribute

    # Tests for EVE image server URL generation
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
    async def test_get_cached_type_found(self, esi_type_service, sample_cached_type):
        """Test _get_cached_type when type is found."""
        # Arrange
        type_id = 587
        esi_type_service.db_session.execute.return_value.scalar_one_or_none.return_value = sample_cached_type

        # Act
        result = await esi_type_service._get_cached_type(type_id)

        # Assert
        assert result == sample_cached_type

    async def test_get_cached_type_not_found(self, esi_type_service):
        """Test _get_cached_type when type is not found."""
        # Arrange
        type_id = 587
        esi_type_service.db_session.execute.return_value.scalar_one_or_none.return_value = None

        # Act
        result = await esi_type_service._get_cached_type(type_id)

        # Assert
        assert result is None

    async def test_get_cached_types_multiple(self, esi_type_service, sample_cached_type):
        """Test _get_cached_types with multiple types."""
        # Arrange
        type_ids = [587, 588]
        cached_types = [
            sample_cached_type,
            EsiTypeCache(type_id=588, name='Punisher')
        ]
        esi_type_service.db_session.execute.return_value.scalars.return_value.all.return_value = cached_types

        # Act
        result = await esi_type_service._get_cached_types(type_ids)

        # Assert
        assert len(result) == 2
        assert result[0].type_id == 587
        assert result[1].type_id == 588

    # Tests for error handling and edge cases
    async def test_fetch_and_cache_type_invalid_data(self, esi_type_service):
        """Test _fetch_and_cache_type with invalid ESI response."""
        # Arrange
        type_id = 587
        esi_type_service.esi_client.get_type_info.return_value = None

        # Act
        result = await esi_type_service._fetch_and_cache_type(type_id)

        # Assert
        assert result is None

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

    async def test_is_ship_type_valid_ship(self, esi_type_service, sample_cached_type):
        """Test _is_ship_type with valid ship category."""
        # Arrange
        sample_cached_type.category_id = 6  # Ship category

        # Act
        result = await esi_type_service._is_ship_type(sample_cached_type)

        # Assert
        assert result is True

    async def test_is_ship_type_invalid_ship(self, esi_type_service, sample_cached_type):
        """Test _is_ship_type with non-ship category."""
        # Arrange
        sample_cached_type.category_id = 8  # Charge category

        # Act
        result = await esi_type_service._is_ship_type(sample_cached_type)

        # Assert
        assert result is False

    async def test_is_ship_type_missing_category(self, esi_type_service, sample_cached_type):
        """Test _is_ship_type with missing category."""
        # Arrange
        sample_cached_type.category_id = None

        # Act
        result = await esi_type_service._is_ship_type(sample_cached_type)

        # Assert
        assert result is False
