# Migration Plan: SQLite to PostgreSQL

**Document Version:** 1.0
**Date:** 2025-06-12
**Author:** Cascade (AI Assistant) & USER (Sam)

## 1. Introduction & Objectives

This document outlines the plan and procedures for migrating the Hangar Bay backend application's database from SQLite to PostgreSQL.

**Objectives:**
*   Transition the development and future production environments to use PostgreSQL.
*   Leverage PostgreSQL's advanced features, scalability, and stricter data typing.
*   Eliminate limitations encountered with SQLite, particularly concerning schema migrations (e.g., `ALTER TABLE` constraints) and concurrent access.
*   Ensure a smooth transition with minimal disruption to development workflow.
*   Update all relevant documentation and configurations.

## 2. Scope

This migration plan covers:
*   Local development environment setup for PostgreSQL.
*   Application configuration changes for database connectivity.
*   Adjustments to SQLAlchemy models and type hints, if necessary.
*   Review and potential modification of Alembic migration scripts.
*   Data migration strategy for existing development data (optional, but recommended).
*   Testing procedures to validate the migration.
*   Updates to project documentation.

## 3. Pre-requisites & Assumptions

*   PostgreSQL server (e.g., version 15 or 16) will be installed and accessible for development.
*   Basic familiarity with PostgreSQL administration (creating databases, users, granting permissions).
*   The project uses SQLAlchemy as the ORM and Alembic for database migrations.
*   The project uses `pdm` for dependency management.

## 4. Migration Phases & Tasks

### Phase 1: Preparation & Environment Setup

*   **Task 1.1: Install PostgreSQL**
    *   Action: Install PostgreSQL server locally (if not already installed).
    *   Guidance: Use official installers or package managers (e.g., Homebrew for macOS, apt for Debian/Ubuntu, official Windows installer).
    *   Resources: [PostgreSQL Downloads](https://www.postgresql.org/download/)
*   **Task 1.2: Create Development Database & User**
    *   Action: Create a new PostgreSQL database (e.g., `hangar_bay_dev`).
    *   Action: Create a dedicated PostgreSQL user (e.g., `hangar_bay_user`) with a secure password.
    *   Action: Grant necessary privileges to `hangar_bay_user` on the `hangar_bay_dev` database (connect, create, etc.).
    *   Example PSQL commands:
        ```sql
        CREATE DATABASE hangar_bay_dev;
        CREATE USER hangar_bay_user WITH PASSWORD 'your_secure_password';
        GRANT ALL PRIVILEGES ON DATABASE hangar_bay_dev TO hangar_bay_user;
        -- For schema ownership if using specific schemas beyond public
        -- ALTER DATABASE hangar_bay_dev OWNER TO hangar_bay_user;
        -- GRANT CREATE ON SCHEMA public TO hangar_bay_user; -- If needed
        ```
*   **Task 1.3: Add PostgreSQL Driver Dependency**
    *   Action: Add the asynchronous PostgreSQL driver `asyncpg` to the project's dependencies.
    *   Command: `pdm add asyncpg`
    *   Verification: Ensure `pyproject.toml` and `pdm.lock` are updated.
*   **Task 1.4: Update Project Documentation (Initial Setup)**
    *   Action: Create/update a section in `README.md` or a dedicated development setup guide (`CONTRIBUTING.md` or `DEV_SETUP.md`) detailing PostgreSQL installation and setup for Hangar Bay.

### Phase 2: Application Configuration & Code Adjustments

*   **Task 2.1: Update Database Connection URL**
    *   Action: Modify the database connection URL in the project's configuration (e.g., `.env` file, settings module).
    *   Current (SQLite example): `DATABASE_URL="sqlite+aiosqlite:///./app/backend/sql_app.db"`
    *   New (PostgreSQL example): `DATABASE_URL="postgresql+asyncpg://hangar_bay_user:your_secure_password@localhost:5432/hangar_bay_dev"`
    *   Ensure the application loads this new URL.
*   **Task 2.2: Update SQLAlchemy Engine Configuration**
    *   Action: Review `app.backend.src.fastapi_app.database.py` (or equivalent) where the SQLAlchemy engine is created.
    *   Ensure it correctly uses the `postgresql+asyncpg` dialect. No major changes should be needed if `DATABASE_URL` is parsed correctly.
    *   Consider PostgreSQL-specific engine arguments if necessary (e.g., connection pool settings, `json_serializer`).
*   **Task 2.3: Review SQLAlchemy Models & Data Types**
    *   Action: Examine all SQLAlchemy models in `app.backend.src.fastapi_app.models.*`.
    *   Identify any data types that might have been chosen due to SQLite limitations or that have better alternatives in PostgreSQL (e.g., `sqlalchemy.dialects.postgresql.JSONB` for JSON fields instead of `sqlalchemy.JSON`).
    *   Pay attention to `String` lengths, `DateTime` types (consider `DateTime(timezone=True)`), and `Numeric` precision.
    *   If changes are made, new Alembic revisions will be required.
*   **Task 2.4: Review Raw SQL Queries (if any)**
    *   Action: Search the codebase for any raw SQL queries.
    *   Ensure they are compatible with PostgreSQL syntax. SQLAlchemy typically abstracts this, but direct queries bypass the ORM.

### Phase 3: Alembic Migration Adjustments

*   **Task 3.1: Update Alembic `env.py` for PostgreSQL**
    *   Action: Review `alembic/env.py`.
    *   Ensure `target_metadata` correctly points to your `Base.metadata`.
    *   The SQLAlchemy URL used by Alembic should now point to the PostgreSQL database. This is typically sourced from your application's configuration.
    *   Remove/adjust SQLite-specific configurations in `context.configure()`, such as `render_as_batch=True` if it was set globally for SQLite. `batch_alter_table` operations might still be needed for specific migrations if they were generated that way, but new migrations for PostgreSQL generally won't require it for simple column additions/alterations.
*   **Task 3.2: Review Existing Migration Scripts**
    *   Action: Carefully review all existing migration scripts in `alembic/versions/`.
    *   Identify any operations that used `op.batch_alter_table()` specifically for SQLite compatibility.
    *   Determine if these batch operations are still necessary or if they can be simplified for PostgreSQL. It's generally safer to leave them if they run correctly on PostgreSQL, but new migrations should avoid unnecessary batch mode.
    *   Test running existing migrations against a clean PostgreSQL database.
        ```bash
        # Ensure DB is clean or drop/recreate
        pdm run alembic upgrade head
        ```
*   **Task 3.3: Generate Initial Autogenerate Revision (Optional Check)**
    *   Action: After configuring Alembic for PostgreSQL and applying existing migrations, run `pdm run alembic revision -m "check_pg_schema_after_initial_migrations" --autogenerate`.
    *   Analyze the generated script. It might detect differences due to stricter typing or default behaviors in PostgreSQL (e.g., nullability, server defaults). This helps identify necessary schema adjustments.
    *   Apply any necessary changes.

### Phase 4: Data Migration (Development Data)

*   **Task 4.1: Choose a Data Migration Strategy (Optional)**
    *   Option A: Fresh Start (No data migration). Suitable if development data is easily reproducible or not critical.
    *   Option B: Manual Scripting (e.g., Python script using SQLAlchemy to read from SQLite and write to PostgreSQL). Suitable for small to medium datasets with manageable complexity.
    *   Option C: ETL Tools (e.g., `pgloader`). More powerful but might be overkill for dev data.
*   **Task 4.2: Implement Data Migration (if chosen)**
    *   Action: Develop and test the chosen data migration script/process.
    *   Consider data type transformations, primary/foreign key constraints, and sequences.
    *   Example (Python script concept):
        ```python
        # pseudocode
        # connect to sqlite_db
        # connect to postgresql_db
        # for each table:
        #   read data from sqlite_table
        #   transform data if needed
        #   write data to postgresql_table
        ```
    *   Ensure to handle `AUTOINCREMENT` (SQLite) vs. `SERIAL`/`IDENTITY` (PostgreSQL) for primary keys correctly. Alembic usually handles table creation, so this is more about data transfer.

### Phase 5: Testing

*   **Task 5.1: Run Unit & Integration Tests**
    *   Action: Execute the full test suite against the PostgreSQL database.
    *   Ensure all tests pass.
    *   Pay close attention to tests involving database interactions, data type handling, and transaction management.
*   **Task 5.2: Manual & Exploratory Testing**
    *   Action: Perform manual testing of all application features that interact with the database.
    *   Focus on CRUD operations, data filtering, sorting, and any complex queries.
*   **Task 5.3: Test Alembic Migrations**
    *   Action: Test downgrade and upgrade paths for migrations on PostgreSQL.
    *   Action: Test generating new migrations with autogenerate and applying them.

### Phase 6: Documentation & Finalization

*   **Task 6.1: Update `README.md` and Developer Guides**
    *   Action: Finalize documentation on setting up PostgreSQL for development.
    *   Include connection string examples, common troubleshooting tips.
*   **Task 6.2: Document PostgreSQL-specific Decisions**
    *   Action: If any PostgreSQL-specific features (e.g., `JSONB`, extensions) are adopted, document their usage and rationale in `design/database/` or relevant design logs.
*   **Task 6.3: Update CI/CD Pipeline (Future)**
    *   Action: If the project has a CI/CD pipeline, update it to run tests against a PostgreSQL service. (This might be a later step if CI is not yet in place).
*   **Task 6.4: Remove SQLite Dependencies & Files (Optional)**
    *   Action: Once confident with PostgreSQL, consider removing `aiosqlite` if no longer needed.
    *   Action: Remove the old `sql_app.db` SQLite file.
    *   Command: `pdm remove aiosqlite` (if it's an explicit dependency and not just for dev).

## 5. Rollback Plan (Contingency)

*   **Condition for Rollback:** If critical, unresolvable issues arise during the migration to PostgreSQL that significantly impede development.
*   **Rollback Steps:**
    1.  Revert application configuration (e.g., `.env`) to use the SQLite `DATABASE_URL`.
    2.  Ensure SQLAlchemy engine configuration points back to SQLite.
    3.  If `aiosqlite` was removed, re-add it: `pdm add aiosqlite`.
    4.  Ensure Alembic `env.py` is configured for SQLite (including `render_as_batch=True` if it was used).
    5.  If any PostgreSQL-specific Alembic migrations were applied and committed, they would need to be carefully downgraded or managed. This highlights the importance of testing migrations thoroughly on a non-critical branch first.
    6.  Communicate the rollback to the team.

## 6. Timeline & Responsibilities

*   **Timeline:** To be determined. Suggest breaking down phases into smaller, manageable chunks.
*   **Lead:** USER (Sam) with support from Cascade.

---
