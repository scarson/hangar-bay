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
