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
    try:
        with pytest.raises(
            DBAPIError,
            match=r"cannot restore NOT NULL on contracts\.price: 1 stored "
                  r"contract\(s\) have no price.*data decision this migration "
                  r"refuses to make",
        ):
            # Explicit target, never "-1": a relative step silently re-targets
            # itself the moment a newer migration lands above this one. The
            # preceding migrations' downgrades run first on the walk; the
            # refusal aborts the one caller-managed transaction, so the
            # rollback below restores every step.
            command.downgrade(cfg, "685dab7d6df5")
    finally:
        # The fixture is SESSION-scoped (TEST-23): one database and one
        # connection shared by every consumer. Leave both exactly as found
        # WHATEVER this test's outcome — clear any open/aborted transaction,
        # remove the row this test committed, and restore head (the first
        # single-step downgrade above committed).
        conn.rollback()
        conn.execute(text("DELETE FROM contracts WHERE contract_id = 990001"))
        conn.commit()
        command.upgrade(cfg, "head")
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
    # Explicit targets, never "-1" — a relative step silently re-targets
    # itself the moment a newer migration lands above this one.
    command.downgrade(cfg, "685dab7d6df5")
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


def test_offline_downgrade_renders_a_transaction_wrapped_locked_guard():
    """`alembic downgrade --sql` must emit a script that is executable as rendered:
    LOCK TABLE is only legal inside a transaction block, so BEGIN/COMMIT must wrap
    the guard, and the lock must precede the check for guard+alteration atomicity
    against concurrent writers. This pins both the env.py offline transaction
    wrapper and the lock's presence — deleting either regresses silently
    otherwise."""
    import io
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    buffer = io.StringIO()
    cfg = Config(
        str(Path(__file__).resolve().parents[2] / "alembic.ini"),
        output_buffer=buffer,
    )
    command.downgrade(cfg, "f2a91c3b7e04:685dab7d6df5", sql=True)
    rendered = buffer.getvalue()

    begin = rendered.index("BEGIN")
    lock = rendered.index("LOCK TABLE contracts IN ACCESS EXCLUSIVE MODE")
    guard = rendered.index("cannot restore NOT NULL on contracts.price")
    alter = rendered.index("ALTER COLUMN price SET NOT NULL")
    commit = rendered.index("COMMIT")
    assert begin < lock < guard < alter < commit


def test_offline_issuer_downgrade_renders_a_locked_guard_then_drops_the_indexes():
    """The issuer downgrade's emitted SQL carries the same atomicity contract as the
    price one, plus a step order of its own.

    a7c44d19e582 reuses the f2a91c3b7e04 shape — LOCK TABLE is only legal inside a
    transaction block, and the lock must precede the guard so the check and the
    alteration cannot be split by a concurrent writer — but only the price migration's
    rendering was pinned. Deleting a7c's LOCK TABLE line, or its lock_timeout preamble,
    regressed silently.

    The step order is the exact inverse of the upgrade (which sets the timeout, creates
    the system_id index, creates the location_id index, then widens): narrow first, then
    drop the indexes in reverse creation order. Pinned so a reordering has to be
    deliberate.
    """
    import io
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    buffer = io.StringIO()
    cfg = Config(
        str(Path(__file__).resolve().parents[2] / "alembic.ini"),
        output_buffer=buffer,
    )
    command.downgrade(cfg, "a7c44d19e582:f2a91c3b7e04", sql=True)
    rendered = buffer.getvalue()

    begin = rendered.index("BEGIN;")
    timeout = rendered.index("SET lock_timeout")
    lock = rendered.index("LOCK TABLE contracts IN ACCESS EXCLUSIVE MODE")
    guard = rendered.index("cannot narrow issuer columns to int32")
    narrow = rendered.index("ALTER COLUMN issuer_corporation_id TYPE INTEGER")
    drop_location = rendered.index("DROP INDEX ix_contracts_start_location_id")
    drop_system = rendered.index("DROP INDEX ix_contracts_start_location_system_id")
    commit = rendered.index("COMMIT")

    assert begin < timeout < lock < guard < narrow < drop_location < drop_system < commit
    # Both columns narrow in ONE statement: a width change rewrites the table, so two
    # ALTERs would rewrite it twice under the same exclusive lock.
    assert rendered.count("ALTER TABLE contracts ALTER COLUMN") == 1


def test_downgrade_refuses_while_an_issuer_id_exceeds_int32(blank_migrated_sync_connection):
    """The issuer-narrowing downgrade must fail with a stated reason once CCP has
    allocated beyond int32 — not with an incidental out-of-range error, and for
    EITHER column (dropping one arm of the guard must fail one variant). Same
    emitted-SQL guard shape as the price migration; TEST-23: arrangement,
    assertion, and restoration all inside one cleanup scope, so a regression in
    the tested code still leaves the session fixture exactly as found."""
    from pathlib import Path

    import pytest
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    conn = blank_migrated_sync_connection
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.attributes["connection"] = conn

    for column in ("issuer_id", "issuer_corporation_id"):
        try:
            conn.execute(
                text(
                    f"""
                    INSERT INTO contracts
                        (contract_id, collateral, status, type, issuer_id,
                         issuer_corporation_id, for_corporation, date_issued,
                         date_expired, item_processing_status, is_ship_contract)
                    VALUES
                        (990002, 0, 'outstanding', 'item_exchange',
                         {'3000000000' if column == 'issuer_id' else '1'},
                         {'3000000000' if column == 'issuer_corporation_id' else '1'},
                         FALSE, '2026-07-01T00:00:00Z', '2026-12-31T00:00:00Z',
                         'PENDING_ITEMS', FALSE)
                    """
                )
            )
            conn.commit()
            with pytest.raises(DBAPIError, match="cannot narrow issuer columns to int32"):
                command.downgrade(cfg, "f2a91c3b7e04")
        finally:
            conn.rollback()
            conn.execute(text("DELETE FROM contracts WHERE contract_id = 990002"))
            conn.commit()
            command.upgrade(cfg, "head")
            conn.commit()


def test_clean_downgrade_restores_int32_issuer_columns(blank_migrated_sync_connection):
    """With no oversized ids the downgrade must actually narrow — the guard test
    alone stays green if the alteration is dropped. Head restored in finally."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    conn = blank_migrated_sync_connection
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.attributes["connection"] = conn
    command.downgrade(cfg, "f2a91c3b7e04")
    conn.commit()

    try:
        types = dict(
            conn.execute(
                text(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_name = 'contracts' "
                    "AND column_name IN ('issuer_id', 'issuer_corporation_id')"
                )
            ).all()
        )
        assert types == {"issuer_id": "integer", "issuer_corporation_id": "integer"}
    finally:
        command.upgrade(cfg, "head")
        conn.commit()
