# ABOUTME: Guards the alembic env.py contract — import-safe outside alembic, migration/model equivalence (Task 3.9).
import importlib.util
from pathlib import Path


def test_alembic_env_import_is_side_effect_free():
    """Importing env.py outside an alembic EnvironmentContext must not run migrations
    (the invocation tail is guarded); reaching the end of the module without error IS the assertion."""
    env_path = Path(__file__).resolve().parents[2] / "alembic" / "env.py"
    spec = importlib.util.spec_from_file_location("alembic_env_import_check", env_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)   # raises if the tail fires without alembic context
    assert callable(module.do_run_migrations)


def test_migrated_schema_matches_model_metadata(blank_migrated_sync_connection):
    """Baseline-migration <-> model-metadata equivalence: schema drift cannot accumulate
    silently once production schema flows through Alembic only (spec §5)."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from fastapi_app.db import Base

    # Match env.py's comparison flags — without compare_server_default the guard is
    # blind to exactly the server-default autogen-hazard class spec §5 hand-reviews.
    ctx = MigrationContext.configure(
        blank_migrated_sync_connection,
        opts={"compare_type": True, "compare_server_default": True},
    )
    diff = compare_metadata(ctx, Base.metadata)
    assert diff == [], f"schema drift between migrations and models: {diff}"


def test_downgrade_refuses_while_priceless_contracts_exist(blank_migrated_sync_connection):
    """The price-nullable migration's downgrade must fail with a stated reason, not an
    incidental NotNullViolation: restoring NOT NULL would require deleting or zero-filling
    contracts ESI legitimately sent without a price (ESI-3). The guard is emitted SQL
    (a DO block), so the refusal surfaces as the database's RaiseException carrying the
    stated message."""
    from pathlib import Path

    import pytest
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    conn = blank_migrated_sync_connection
    conn.execute(
        text(
            """
            INSERT INTO contracts
                (contract_id, collateral, status, type, issuer_id,
                 issuer_corporation_id, for_corporation, date_issued, date_expired,
                 item_processing_status, is_ship_contract)
            VALUES
                (990001, 0, 'outstanding', 'item_exchange', 1, 1, FALSE,
                 '2026-07-01T00:00:00Z', '2026-12-31T00:00:00Z', 'PENDING_ITEMS',
                 FALSE)
            """
        )
    )
    conn.commit()

    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.attributes["connection"] = conn
    with pytest.raises(DBAPIError, match="cannot restore NOT NULL on contracts.price"):
        command.downgrade(cfg, "-1")
    # The fixture is SESSION-scoped: one database and one connection shared by
    # every consumer. Leave both exactly as found — clear the aborted
    # transaction the refusal left open, then remove the row this test
    # committed, or the sibling clean-downgrade test meets a corpus with a
    # price-less contract and is refused too.
    conn.rollback()
    conn.execute(text("DELETE FROM contracts WHERE contract_id = 990001"))
    conn.commit()


def test_clean_downgrade_restores_not_null_on_price(blank_migrated_sync_connection):
    """With no price-less rows the downgrade must actually restore the constraint —
    the guard test alone would stay green if the alteration itself were dropped."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    conn = blank_migrated_sync_connection
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.attributes["connection"] = conn
    command.downgrade(cfg, "-1")
    conn.commit()

    try:
        nullable = conn.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'contracts' AND column_name = 'price'"
            )
        ).scalar_one()
        assert nullable == "NO"
    finally:
        # Session-scoped fixture: restore head so any later consumer sees the
        # schema the fixture promises, whatever this test's outcome.
        command.upgrade(cfg, "head")
        conn.commit()
