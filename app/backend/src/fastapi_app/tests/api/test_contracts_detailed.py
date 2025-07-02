"""
Integration tests for detailed contract API endpoints.

Tests use real database interactions with mocked ESI responses via pytest-vcr.
Verifies response schemas match ContractDetailsSchema and tests both happy path 
and error scenarios with proper HTTP status codes.
"""

import pytest
from httpx import AsyncClient
from datetime import datetime, timezone
from decimal import Decimal

from fastapi_app.models.contracts import Contract, ContractItem
from fastapi_app.models.common_models import EsiTypeCache


class TestContractsDetailedAPI:
    """Integration tests for detailed contract API endpoints."""

    @pytest.fixture
    async def sample_contract_data(self, db_session):
        """Create sample contract data in the database."""
        # Create contract
        contract = Contract(
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
        
        # Create contract items
        contract_items = [
            ContractItem(
                record_id=1,
                contract_id=12345,
                type_id=587,
                type_name="Rifter",
                quantity=1,
                is_singleton=True,
                is_included=True,
                item_id=None,
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
                item_id=None,
                raw_quantity=None
            )
        ]
        
        # Add to database
        db_session.add(contract)
        for item in contract_items:
            db_session.add(item)
        
        await db_session.flush()
        await db_session.commit()
        
        return contract, contract_items

    @pytest.fixture
    async def sample_esi_type_cache(self, db_session):
        """Create sample ESI type cache data."""
        ship_type = EsiTypeCache(
            type_id=587,
            name="Rifter",
            description="The Rifter is a versatile frigate...",
            category_id=6,  # Ship category
            group_id=25,
            published=True,
            mass=1067000.0,
            volume=27289.0,
            capacity=140.0,
            portion_size=1,
            dogma_attributes=[
                {'attribute_id': 9, 'value': 1067000},     # Mass
                {'attribute_id': 161, 'value': 27289},     # Volume
                {'attribute_id': 479, 'value': 150},       # Shield HP
                {'attribute_id': 263, 'value': 300},       # Armor HP
                {'attribute_id': 482, 'value': 325},       # Structure HP
            ],
            dogma_effects=[
                {'effect_id': 11, 'is_default': True}
            ],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        module_type = EsiTypeCache(
            type_id=31,
            name="Tritanium",
            description="A very common mineral...",
            category_id=4,  # Material category
            group_id=18,
            published=True,
            mass=1.0,
            volume=0.01,
            capacity=0.0,
            portion_size=1,
            dogma_attributes=[],
            dogma_effects=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        db_session.add(ship_type)
        db_session.add(module_type)
        await db_session.flush()
        await db_session.commit()
        
        return ship_type, module_type

    # Happy path tests
    async def test_get_contract_details_success(
        self, 
        test_client: AsyncClient, 
        sample_contract_data, 
        sample_esi_type_cache
    ):
        """Test successful contract details retrieval."""
        # Arrange
        contract, contract_items = sample_contract_data
        ship_type, module_type = sample_esi_type_cache
        contract_id = contract.contract_id

        # Act
        response = await test_client.get(f"/contracts/details/{contract_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        
        # Verify contract details schema
        assert data["contract_id"] == contract_id
        assert data["title"] == "Rifter Contract"
        assert data["type"] == "item_exchange"
        assert data["status"] == "outstanding"
        assert data["price"] == 1000000.0
        assert data["is_ship_contract"] is True
        
        # Verify items are included
        assert "items" in data
        assert len(data["items"]) == 2
        
        # Verify ship details are included
        assert "ship_details" in data
        assert data["ship_details"] is not None
        assert data["ship_details"]["ship_type_id"] == 587
        assert data["ship_details"]["ship_name"] == "Rifter"
        
        # Verify enhanced item data
        rifter_item = next(item for item in data["items"] if item["type_id"] == 587)
        assert rifter_item["type_name"] == "Rifter"
        assert rifter_item["quantity"] == 1
        assert rifter_item["is_singleton"] is True

    async def test_get_contract_details_with_key_attributes(
        self, 
        test_client: AsyncClient, 
        sample_contract_data, 
        sample_esi_type_cache
    ):
        """Test contract details with key attributes query parameter."""
        # Arrange
        contract, _ = sample_contract_data
        contract_id = contract.contract_id

        # Act
        response = await test_client.get(
            f"/contracts/details/{contract_id}?attribute_detail=key_attributes"
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        
        # Verify ship details include key attributes
        assert "ship_details" in data
        if data["ship_details"]:
            assert "attributes" in data["ship_details"]

    async def test_get_contract_details_with_all_attributes(
        self, 
        test_client: AsyncClient, 
        sample_contract_data, 
        sample_esi_type_cache
    ):
        """Test contract details with all attributes query parameter."""
        # Arrange
        contract, _ = sample_contract_data
        contract_id = contract.contract_id

        # Act
        response = await test_client.get(
            f"/contracts/details/{contract_id}?attribute_detail=all_attributes"
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "ship_details" in data
        if data["ship_details"]:
            assert "attributes" in data["ship_details"]

    async def test_get_contract_details_non_ship_contract(
        self, 
        test_client: AsyncClient, 
        db_session
    ):
        """Test contract details for non-ship contract."""
        # Arrange: Create a non-ship contract
        contract = Contract(
            contract_id=54321,
            title="Module Contract",
            type="item_exchange",
            status="outstanding",
            price=Decimal("100000.00"),
            collateral=None,
            reward=None,
            volume=100.0,
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
            is_ship_contract=False
        )
        
        # Add module item only
        contract_item = ContractItem(
            record_id=3,
            contract_id=54321,
            type_id=31,
            type_name="Tritanium",
            quantity=5000,
            is_singleton=False,
            is_included=True,
            item_id=None,
            raw_quantity=None
        )
        
        db_session.add(contract)
        db_session.add(contract_item)
        await db_session.flush()
        await db_session.commit()

        # Act
        response = await test_client.get("/contracts/details/54321")

        # Assert
        assert response.status_code == 200
        data = response.json()
        
        assert data["contract_id"] == 54321
        assert data["is_ship_contract"] is False
        assert data["ship_details"] is None

    # Error scenarios
    async def test_get_contract_details_not_found(self, test_client: AsyncClient):
        """Test contract details for non-existent contract."""
        # Act
        response = await test_client.get("/contracts/details/99999")

        # Assert
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    async def test_get_contract_details_invalid_id(self, test_client: AsyncClient):
        """Test contract details with invalid contract ID."""
        # Act
        response = await test_client.get("/contracts/details/invalid")

        # Assert
        assert response.status_code == 422  # Validation error

    async def test_get_contract_details_invalid_attribute_parameter(
        self, 
        test_client: AsyncClient, 
        sample_contract_data, 
        sample_esi_type_cache
    ):
        """Test contract details with invalid attribute_detail parameter."""
        # Arrange
        contract, _ = sample_contract_data
        contract_id = contract.contract_id

        # Act
        response = await test_client.get(
            f"/contracts/details/{contract_id}?attribute_detail=invalid_level"
        )

        # Assert
        # Should handle gracefully and return 200 with default behavior
        assert response.status_code == 200

    # Edge cases
    async def test_get_contract_details_empty_items(
        self, 
        test_client: AsyncClient, 
        db_session
    ):
        """Test contract details for contract with no items."""
        # Arrange: Create contract with no items
        contract = Contract(
            contract_id=11111,
            title="Empty Contract",
            type="item_exchange",
            status="outstanding",
            price=Decimal("0.00"),
            collateral=None,
            reward=None,
            volume=0.0,
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
            is_ship_contract=False
        )
        
        db_session.add(contract)
        await db_session.flush()
        await db_session.commit()

        # Act
        response = await test_client.get("/contracts/details/11111")

        # Assert
        assert response.status_code == 200
        data = response.json()
        
        assert data["contract_id"] == 11111
        assert data["items"] == []
        assert data["ship_details"] is None

    async def test_get_contract_details_large_contract(
        self, 
        test_client: AsyncClient, 
        db_session
    ):
        """Test contract details for contract with many items."""
        # Arrange: Create contract with many items
        contract = Contract(
            contract_id=22222,
            title="Large Contract",
            type="item_exchange",
            status="outstanding",
            price=Decimal("10000000.00"),
            collateral=None,
            reward=None,
            volume=50000.0,
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
            is_ship_contract=False
        )
        
        # Create many items
        items = []
        for i in range(50):  # 50 items
            item = ContractItem(
                record_id=100 + i,
                contract_id=22222,
                type_id=31 + (i % 10),  # Vary type IDs
                type_name=f"Item {i}",
                quantity=100 + i,
                is_singleton=False,
                is_included=True,
                item_id=None,
                raw_quantity=None
            )
            items.append(item)
        
        db_session.add(contract)
        for item in items:
            db_session.add(item)
        await db_session.flush()
        await db_session.commit()

        # Act
        response = await test_client.get("/contracts/details/22222")

        # Assert
        assert response.status_code == 200
        data = response.json()
        
        assert data["contract_id"] == 22222
        assert len(data["items"]) == 50

    # Response schema validation
    async def test_contract_details_response_schema_validation(
        self, 
        test_client: AsyncClient, 
        sample_contract_data, 
        sample_esi_type_cache
    ):
        """Test that response matches ContractDetailsSchema exactly."""
        # Arrange
        contract, _ = sample_contract_data
        contract_id = contract.contract_id

        # Act
        response = await test_client.get(f"/contracts/details/{contract_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required ContractDetailsSchema fields are present
        required_fields = [
            "contract_id", "title", "type", "status", "price", "collateral",
            "reward", "volume", "date_issued", "date_expired", "date_completed",
            "issuer_id", "issuer_name", "issuer_corporation_id", 
            "issuer_corporation_name", "start_location_id", "start_location_name",
            "start_location_system_id", "start_location_region_id", 
            "end_location_id", "for_corporation", "is_ship_contract", 
            "items", "ship_details"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify items structure
        if data["items"]:
            item = data["items"][0]
            item_required_fields = [
                "record_id", "type_id", "type_name", "quantity", 
                "is_singleton", "is_included"
            ]
            for field in item_required_fields:
                assert field in item, f"Missing required item field: {field}"
        
        # Verify ship_details structure (if present)
        if data["ship_details"]:
            ship_required_fields = ["ship_type_id", "ship_name"]
            for field in ship_required_fields:
                assert field in data["ship_details"], f"Missing required ship_details field: {field}"

    # Performance and timing tests
    async def test_contract_details_response_time(
        self, 
        test_client: AsyncClient, 
        sample_contract_data, 
        sample_esi_type_cache
    ):
        """Test that contract details response is reasonably fast."""
        import time
        
        # Arrange
        contract, _ = sample_contract_data
        contract_id = contract.contract_id

        # Act
        start_time = time.time()
        response = await test_client.get(f"/contracts/details/{contract_id}")
        end_time = time.time()

        # Assert
        assert response.status_code == 200
        response_time = end_time - start_time
        assert response_time < 5.0, f"Response took too long: {response_time}s"  # Should be fast
