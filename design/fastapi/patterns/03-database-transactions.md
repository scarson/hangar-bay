# Pattern: Atomic Database Transactions for Logical Units of Work

**Last Updated:** 2025-06-12
**Related Design Log Entry:** [2025-06-12 04:30:57-05:00: Lessons from ESI Data Aggregation: Transaction Management & Batching](..\..\meta\design-log.md#2025-06-12-043057-0500-lessons-from-esi-data-aggregation-transaction-management--batching)
**Related Post-Mortem Section:** [Challenge 5: Optimizing Database Transactions and Batching for ESI Data Aggregation](..\..\reviews\post-mortems\phase-reviews\02-backend-f001-public-contract-aggregation.md#challenge-5-optimizing-database-transactions-and-batching-for-esi-data-aggregation)

## 1. Context & Objective

When aggregating data from external APIs (like EVE Online's ESI) and persisting it to the local database, there's a risk of data inconsistency if operations are only partially completed. For example, fetching a contract header might succeed, but a subsequent call to fetch its items might fail. If the contract header was committed independently, the database would be left in an inconsistent state.

The objective of this pattern is to ensure data integrity by defining clear boundaries for database transactions, aligning them with "logical units of work" performed during data aggregation or complex business operations.

## 2. The Pattern: Commit on Full Success, Rollback on Any Failure

### 2.1. Define the "Logical Unit of Work"

*   **Definition:** A "logical unit of work" encompasses all external API calls, data processing steps, and database operations required to fetch, process, and store a complete, self-contained entity or to complete a single, coherent business operation.
*   **Examples:**
    *   Fetching one public contract from ESI *and all* its associated items, then saving them to the database.
    *   Processing a user request that involves multiple database reads and writes that must succeed or fail together.

### 2.2. Single Database Transaction per Logical Unit

*   **Core Rule:** All database changes (inserts, updates, deletes) related to a single logical unit of work **must** be performed within a **single database transaction**.
*   **Mechanism (SQLAlchemy Async):**
    *   A single `AsyncSession` should be used for all database operations within the unit of work.
    *   The session is typically obtained via FastAPI's dependency injection (`db: AsyncSession = Depends(get_db)`) for API-driven operations or created explicitly within a background task.

### 2.3. Commit on Full Success Only

*   **Condition:** The database transaction (`await db.commit()`) is executed **only if all** external API calls (if any) for that unit are successful and all associated data processing and validation steps complete without error.

### 2.4. Rollback on Any Failure

*   **Condition:** If *any* part of the logical unit of work fails (e.g., an ESI API error, a data validation error, a processing exception), the *entire* database transaction for that unit **must be rolled back** (`await db.rollback()`).
*   **Error Handling:** The error should be logged, and appropriate action should be taken (e.g., returning an error response to the user, scheduling a retry for a background task).

## 3. Rationale & Cost Asymmetry

*   **Data Integrity is Paramount:** It is far preferable to re-attempt fetching/processing a complete logical unit (especially when mechanisms like ESI ETags can minimize actual data re-transfer) than to risk persisting incomplete, orphaned, or inconsistent data.
*   **Cost Asymmetry:**
    *   **External API Calls (e.g., ESI):** These are "expensive" due to network latency, rate limits, and potential unreliability. Each call should be treated as a valuable, potentially failing operation.
    *   **Local Database Transactions:** Commits and rollbacks on the local database are comparatively "cheap" and fast.
*   **Design Implication:** The transaction boundary should be drawn to ensure that the outcome of the "expensive" external operations is fully processed and validated before the "cheap" database commit is performed.

## 4. Implementation Example (Conceptual - Aggregating a Contract)

```python
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException
from ..core.dependencies import get_db
from ..services.esi_client_class import ESIClient # Assumes ESIClient handles its own HTTP errors
from ..core.config import Settings

async def aggregate_and_store_contract(
    contract_id: int,
    esi_client: ESIClient, # Instantiated with settings
    db: AsyncSession # Injected by FastAPI or managed by background task
):
    try:
        # --- Start of Logical Unit of Work ---
        # 1. Fetch contract header (expensive ESI call)
        contract_header_data = await esi_client.get_contract_header(contract_id)
        if not contract_header_data:
            # Handle case where contract doesn't exist or error occurs
            # For this example, assume esi_client raises specific exceptions
            raise ValueError(f"Contract {contract_id} header not found.")

        # 2. Fetch contract items (another expensive ESI call)
        contract_items_data = await esi_client.get_contract_items(contract_id)
        if contract_items_data is None: # Check for None if API can return it on error
             raise ValueError(f"Failed to fetch items for contract {contract_id}.")

        # 3. Process and validate data (application logic)
        # ... (e.g., transform ESI data to DB model instances, validate fields) ...
        db_contract = YourContractModel(**processed_header_data)
        db_items = [YourItemModel(**item_data) for item_data in processed_items_data]

        # 4. Perform database operations (within the transaction)
        db.add(db_contract)
        db.add_all(db_items)

        # 5. Commit only if all previous steps succeeded
        await db.commit() # --- Transaction Commit ---
        # --- End of Logical Unit of Work ---

        return {"status": "success", "contract_id": contract_id}

    except ValueError as ve:
        await db.rollback() # --- Transaction Rollback ---
        # Log error: logger.error(f"Validation error for contract {contract_id}: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except ESIClient.ESITimeoutError as ete: # Example custom ESI exception
        await db.rollback()
        # Log error: logger.error(f"ESI Timeout for contract {contract_id}: {ete}")
        raise HTTPException(status_code=504, detail="ESI API timeout")
    except Exception as e:
        await db.rollback()
        # Log error: logger.error(f"Generic error for contract {contract_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

```

## 5. Benefits

*   **Ensures Data Integrity:** The primary benefit. The database is always left in a consistent state.
*   **Simplified Error Handling:** Rollback logic is straightforward – if anything fails, the entire unit's DB changes are undone.
*   **Robustness against External Failures:** Protects the local database from inconsistencies caused by unreliable external APIs.
*   **Idempotency Support:** When combined with upsert logic, re-processing a failed unit of work (e.g., on a retry) can correctly reach the desired final state without duplicates.

## 6. When to Apply

*   **Mandatory** for operations involving multiple external API calls whose collective data must be stored together.
*   **Mandatory** for any multi-step business logic where partial completion would lead to an invalid or inconsistent application state.
*   **Recommended** even for single external API calls if the subsequent processing and validation are complex and could fail.
```
