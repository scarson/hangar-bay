"""
Database integration tests for EsiTypeCache model and ESITypeService database operations.

Tests CRUD operations, constraints, indexing, query performance, and PostgreSQL 
upsert behavior in the ESI Type Service with real database interactions.
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from fastapi_app.models.common_models import EsiTypeCache
from fastapi_app.services.esi_type_service import ESITypeService
from fastapi_app.clients.esi_client import ESIClient


class TestEsiTypeCacheIntegration:
    """Database integration tests for EsiTypeCache and ESITypeService."""

    # CRUD Operations Tests
    async def test_create_esi_type_cache(self, db_session):
        """Test creating an EsiTypeCache record."""
        # Arrange
        type_cache = EsiTypeCache(
            type_id=587,
            name="Rifter",
            description="The Rifter is a versatile frigate...",
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
            ]
        )

        # Act
        db_session.add(type_cache)
        await db_session.flush()
        await db_session.commit()

        # Assert
        assert type_cache.type_id == 587
        assert type_cache.created_at is not None
        assert type_cache.updated_at is not None

    async def test_read_esi_type_cache(self, db_session):
        """Test reading an EsiTypeCache record."""
        # Arrange
        type_cache = EsiTypeCache(
            type_id=588,
            name="Punisher",
            category_id=6,
            group_id=25,
            published=True
        )
        db_session.add(type_cache)
        await db_session.flush()
        await db_session.commit()

        # Act
        stmt = select(EsiTypeCache).where(EsiTypeCache.type_id == 588)
        result = await db_session.execute(stmt)
        retrieved = result.scalar_one_or_none()

        # Assert
        assert retrieved is not None
        assert retrieved.type_id == 588
        assert retrieved.name == "Punisher"

    async def test_update_esi_type_cache(self, db_session):
        """Test updating an EsiTypeCache record."""
        # Arrange
        type_cache = EsiTypeCache(
            type_id=589,
            name="Old Name",
            category_id=6,
            published=True
        )
        db_session.add(type_cache)
        await db_session.flush()
        await db_session.commit()

        # Act
        type_cache.name = "Updated Name"
        type_cache.description = "Updated description"
        await db_session.flush()
        await db_session.commit()

        # Assert
        stmt = select(EsiTypeCache).where(EsiTypeCache.type_id == 589)
        result = await db_session.execute(stmt)
        updated = result.scalar_one_or_none()
        
        assert updated.name == "Updated Name"
        assert updated.description == "Updated description"
        assert updated.updated_at > updated.created_at

    async def test_delete_esi_type_cache(self, db_session):
        """Test deleting an EsiTypeCache record."""
        # Arrange
        type_cache = EsiTypeCache(
            type_id=590,
            name="To Delete",
            category_id=6,
            published=True
        )
        db_session.add(type_cache)
        await db_session.flush()
        await db_session.commit()

        # Act
        await db_session.delete(type_cache)
        await db_session.flush()
        await db_session.commit()

        # Assert
        stmt = select(EsiTypeCache).where(EsiTypeCache.type_id == 590)
        result = await db_session.execute(stmt)
        deleted = result.scalar_one_or_none()
        
        assert deleted is None

    # Constraint Tests
    async def test_unique_type_id_constraint(self, db_session):
        """Test unique constraint on type_id."""
        # Arrange
        type_cache1 = EsiTypeCache(
            type_id=591,
            name="First",
            category_id=6,
            published=True
        )
        type_cache2 = EsiTypeCache(
            type_id=591,  # Same type_id
            name="Second",
            category_id=6,
            published=True
        )

        # Act & Assert
        db_session.add(type_cache1)
        await db_session.flush()
        
        db_session.add(type_cache2)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_not_null_constraints(self, db_session):
        """Test NOT NULL constraints on required fields."""
        # Arrange - Missing required field
        type_cache = EsiTypeCache(
            # Missing type_id (required)
            name="Test",
            category_id=6,
            published=True
        )

        # Act & Assert
        db_session.add(type_cache)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # JSON Field Tests
    async def test_dogma_attributes_json_field(self, db_session):
        """Test dogma_attributes JSON field storage and retrieval."""
        # Arrange
        complex_attributes = [
            {'attribute_id': 9, 'value': 1067000, 'display_name': 'Mass'},
            {'attribute_id': 161, 'value': 27289, 'display_name': 'Volume'},
            {'attribute_id': 479, 'value': 150.5, 'display_name': 'Shield HP'},
        ]
        
        type_cache = EsiTypeCache(
            type_id=592,
            name="Complex Ship",
            category_id=6,
            published=True,
            dogma_attributes=complex_attributes
        )

        # Act
        db_session.add(type_cache)
        await db_session.flush()
        await db_session.commit()

        # Retrieve and verify
        stmt = select(EsiTypeCache).where(EsiTypeCache.type_id == 592)
        result = await db_session.execute(stmt)
        retrieved = result.scalar_one_or_none()

        # Assert
        assert retrieved.dogma_attributes == complex_attributes
        assert len(retrieved.dogma_attributes) == 3
        assert retrieved.dogma_attributes[0]['attribute_id'] == 9

    async def test_dogma_effects_json_field(self, db_session):
        """Test dogma_effects JSON field storage and retrieval."""
        # Arrange
        complex_effects = [
            {'effect_id': 11, 'is_default': True, 'name': 'Online'},
            {'effect_id': 12, 'is_default': False, 'name': 'Activate'},
        ]
        
        type_cache = EsiTypeCache(
            type_id=593,
            name="Complex Module",
            category_id=8,
            published=True,
            dogma_effects=complex_effects
        )

        # Act
        db_session.add(type_cache)
        await db_session.flush()
        await db_session.commit()

        # Retrieve and verify
        stmt = select(EsiTypeCache).where(EsiTypeCache.type_id == 593)
        result = await db_session.execute(stmt)
        retrieved = result.scalar_one_or_none()

        # Assert
        assert retrieved.dogma_effects == complex_effects
        assert len(retrieved.dogma_effects) == 2

    # Index Performance Tests
    async def test_type_id_index_performance(self, db_session):
        """Test query performance on type_id index."""
        # Arrange - Create multiple records
        type_caches = []
        for i in range(100, 200):  # 100 records
            type_cache = EsiTypeCache(
                type_id=i,
                name=f"Type {i}",
                category_id=6,
                published=True
            )
            type_caches.append(type_cache)
        
        db_session.add_all(type_caches)
        await db_session.flush()
        await db_session.commit()

        # Act - Query with EXPLAIN to check index usage
        stmt = text("EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM esi_type_cache WHERE type_id = 150")
        result = await db_session.execute(stmt)
        explain_output = result.fetchall()

        # Assert - Verify index scan is used (not sequential scan)
        explain_text = " ".join([str(row[0]) for row in explain_output])
        assert "Index Scan" in explain_text or "Bitmap Heap Scan" in explain_text
        assert "Seq Scan" not in explain_text

    async def test_category_id_index_performance(self, db_session):
        """Test query performance on category_id index."""
        # Arrange - Create records with different categories
        type_caches = []
        for i in range(300, 350):
            type_cache = EsiTypeCache(
                type_id=i,
                name=f"Type {i}",
                category_id=6 if i % 2 == 0 else 8,  # Mix of categories
                published=True
            )
            type_caches.append(type_cache)
        
        db_session.add_all(type_caches)
        await db_session.flush()
        await db_session.commit()

        # Act - Query by category_id
        stmt = select(EsiTypeCache).where(EsiTypeCache.category_id == 6)
        result = await db_session.execute(stmt)
        ships = result.scalars().all()

        # Assert
        assert len(ships) == 25  # Half of the 50 records
        for ship in ships:
            assert ship.category_id == 6

    # PostgreSQL Upsert Tests (via ESITypeService)
    async def test_upsert_new_record(self, db_session):
        """Test PostgreSQL upsert behavior for new records."""
        # Arrange
        mock_esi_client = ESITypeService.__new__(ESITypeService)  # Create without calling __init__
        mock_esi_client.db_session = db_session
        
        # Mock ESI data
        esi_data = {
            'type_id': 594,
            'name': 'New Ship',
            'description': 'A brand new ship',
            'category_id': 6,
            'group_id': 25,
            'published': True,
            'mass': 1000000.0,
            'volume': 25000.0,
            'capacity': 100.0,
            'portion_size': 1,
            'dogma_attributes': [{'attribute_id': 9, 'value': 1000000}],
            'dogma_effects': []
        }

        # Act - Simulate the upsert operation from ESITypeService
        from sqlalchemy.dialects.postgresql import insert
        
        stmt = insert(EsiTypeCache).values(
            type_id=esi_data['type_id'],
            name=esi_data['name'],
            description=esi_data.get('description'),
            category_id=esi_data.get('category_id'),
            group_id=esi_data.get('group_id'),
            published=esi_data.get('published', False),
            mass=esi_data.get('mass'),
            volume=esi_data.get('volume'),
            capacity=esi_data.get('capacity'),
            portion_size=esi_data.get('portion_size'),
            dogma_attributes=esi_data.get('dogma_attributes', []),
            dogma_effects=esi_data.get('dogma_effects', [])
        ).on_conflict_do_update(
            index_elements=['type_id'],
            set_={
                'name': stmt.excluded.name,
                'description': stmt.excluded.description,
                'updated_at': text('CURRENT_TIMESTAMP')
            }
        )
        
        result = await db_session.execute(stmt)
        await db_session.commit()

        # Assert
        assert result.inserted_primary_key[0] == 594

        # Verify the record was created
        select_stmt = select(EsiTypeCache).where(EsiTypeCache.type_id == 594)
        select_result = await db_session.execute(select_stmt)
        created_record = select_result.scalar_one_or_none()
        
        assert created_record is not None
        assert created_record.name == 'New Ship'

    async def test_upsert_existing_record(self, db_session):
        """Test PostgreSQL upsert behavior for existing records."""
        # Arrange - Create existing record
        existing = EsiTypeCache(
            type_id=595,
            name="Old Name",
            description="Old description",
            category_id=6,
            published=True
        )
        db_session.add(existing)
        await db_session.flush()
        await db_session.commit()

        # Act - Upsert with updated data
        from sqlalchemy.dialects.postgresql import insert
        
        stmt = insert(EsiTypeCache).values(
            type_id=595,
            name="Updated Name",
            description="Updated description",
            category_id=6,
            published=True
        ).on_conflict_do_update(
            index_elements=['type_id'],
            set_={
                'name': stmt.excluded.name,
                'description': stmt.excluded.description,
                'updated_at': text('CURRENT_TIMESTAMP')
            }
        )
        
        await db_session.execute(stmt)
        await db_session.commit()

        # Assert - Verify record was updated, not duplicated
        select_stmt = select(EsiTypeCache).where(EsiTypeCache.type_id == 595)
        result = await db_session.execute(select_stmt)
        all_records = result.scalars().all()
        
        assert len(all_records) == 1  # Only one record
        updated_record = all_records[0]
        assert updated_record.name == "Updated Name"
        assert updated_record.description == "Updated description"

    # Batch Operations Tests
    async def test_bulk_insert_performance(self, db_session):
        """Test bulk insert performance for multiple EsiTypeCache records."""
        import time
        
        # Arrange
        batch_size = 100
        type_caches = []
        for i in range(400, 400 + batch_size):
            type_cache = EsiTypeCache(
                type_id=i,
                name=f"Bulk Type {i}",
                category_id=6,
                published=True,
                dogma_attributes=[{'attribute_id': 9, 'value': i * 1000}]
            )
            type_caches.append(type_cache)

        # Act
        start_time = time.time()
        db_session.add_all(type_caches)
        await db_session.flush()
        await db_session.commit()
        end_time = time.time()

        # Assert
        insert_time = end_time - start_time
        assert insert_time < 5.0, f"Bulk insert took too long: {insert_time}s"

        # Verify all records were inserted
        stmt = select(EsiTypeCache).where(
            EsiTypeCache.type_id.between(400, 400 + batch_size - 1)
        )
        result = await db_session.execute(stmt)
        inserted_records = result.scalars().all()
        
        assert len(inserted_records) == batch_size

    # Edge Cases and Error Handling
    async def test_large_json_fields(self, db_session):
        """Test handling of large JSON fields."""
        # Arrange - Create large attribute and effect arrays
        large_attributes = []
        for i in range(100):  # 100 attributes
            large_attributes.append({
                'attribute_id': i,
                'value': i * 1.5,
                'display_name': f'Attribute {i}',
                'description': f'This is attribute number {i} with some description text'
            })

        type_cache = EsiTypeCache(
            type_id=596,
            name="Ship with Many Attributes",
            category_id=6,
            published=True,
            dogma_attributes=large_attributes
        )

        # Act
        db_session.add(type_cache)
        await db_session.flush()
        await db_session.commit()

        # Assert
        stmt = select(EsiTypeCache).where(EsiTypeCache.type_id == 596)
        result = await db_session.execute(stmt)
        retrieved = result.scalar_one_or_none()
        
        assert len(retrieved.dogma_attributes) == 100
        assert retrieved.dogma_attributes[50]['attribute_id'] == 50

    async def test_null_json_fields_handling(self, db_session):
        """Test handling of NULL JSON fields."""
        # Arrange
        type_cache = EsiTypeCache(
            type_id=597,
            name="Minimal Type",
            category_id=6,
            published=True,
            dogma_attributes=None,  # Explicitly NULL
            dogma_effects=None      # Explicitly NULL
        )

        # Act
        db_session.add(type_cache)
        await db_session.flush()
        await db_session.commit()

        # Assert
        stmt = select(EsiTypeCache).where(EsiTypeCache.type_id == 597)
        result = await db_session.execute(stmt)
        retrieved = result.scalar_one_or_none()
        
        assert retrieved.dogma_attributes is None
        assert retrieved.dogma_effects is None

    async def test_concurrent_upserts(self, db_session):
        """Test handling of concurrent upsert operations."""
        # This test verifies that the database handles concurrent operations gracefully
        # In a real scenario, this would test race conditions, but in our test environment
        # we simulate the conflict resolution behavior
        
        # Arrange - Create initial record
        type_cache = EsiTypeCache(
            type_id=598,
            name="Concurrent Test",
            category_id=6,
            published=True
        )
        db_session.add(type_cache)
        await db_session.flush()
        await db_session.commit()

        # Act - Simulate concurrent update via upsert
        from sqlalchemy.dialects.postgresql import insert
        
        stmt = insert(EsiTypeCache).values(
            type_id=598,
            name="Concurrently Updated",
            category_id=6,
            published=True,
            description="Added by concurrent process"
        ).on_conflict_do_update(
            index_elements=['type_id'],
            set_={
                'name': stmt.excluded.name,
                'description': stmt.excluded.description,
                'updated_at': text('CURRENT_TIMESTAMP')
            }
        )
        
        await db_session.execute(stmt)
        await db_session.commit()

        # Assert
        stmt = select(EsiTypeCache).where(EsiTypeCache.type_id == 598)
        result = await db_session.execute(stmt)
        final_record = result.scalar_one_or_none()
        
        assert final_record.name == "Concurrently Updated"
        assert final_record.description == "Added by concurrent process"
