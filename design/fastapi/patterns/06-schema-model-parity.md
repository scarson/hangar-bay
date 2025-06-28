# Pattern: Schema-Model Parity

**Last Updated:** 2025-06-28
**Related Design Log Entry:** [2025-06-28 14:50:00-05:00: Enforcing Schema-Model Parity in Pydantic and SQLAlchemy](../../meta/design-log.md#2025-06-28-145000-0500-enforcing-schema-model-parity-in-pydantic-and-sqlalchemy)

## 1. Context & Objective

A frequent source of runtime `ValidationError` and `AttributeError` exceptions is a mismatch, or "drift," between the Pydantic schemas used for API data transfer and the SQLAlchemy ORM models used for database representation. This pattern establishes a mandatory process to ensure these two representations remain synchronized.

## 2. The Pattern: Explicit Alignment

### 2.1. Core Rule

Any field in a SQLAlchemy model that is intended for exposure through the API **must** have a corresponding field in its Pydantic schema. This alignment must be meticulously maintained.

### 2.2. Handling Name Discrepancies

It is common for field names to differ for clarity (e.g., Python-idiomatic `contract_type` vs. JSON-idiomatic `type`).

*   **Mechanism:** Use Pydantic's `validation_alias` to explicitly map the API-facing field name to the ORM model's attribute name.

### 2.3. Code Review Mandate

Verifying schema-model parity is a **required checklist item** for all code reviews involving changes to either Pydantic schemas or SQLAlchemy models.

## 3. Implementation Example

### 3.1. Pydantic Configuration (Critical)

For this pattern to work, the Pydantic schema's `ConfigDict` **must** be configured correctly. The example below shows the required settings, and their roles are critical:

*   `from_attributes=True`: This is the most important setting. It tells Pydantic to read the data not just from a dictionary, but also directly from ORM model attributes. Without this, you cannot create a schema from a model instance (e.g., `ContractSchema.model_validate(db_contract)`).
*   `populate_by_name=True`: This allows the Pydantic model to be populated using either the field's actual name (`contract_type`) or its alias (`type`). This provides flexibility when creating model instances.
*   `alias_generator=to_camel`: This is a project-specific convention to automatically generate `camelCase` JSON field names from `snake_case` model attributes, which is a common best practice for modern APIs.

### 3.2. Code Example

**Scenario:** The `Contract` ORM model has an attribute `is_blueprint_copy`, but the corresponding Pydantic schema is missing it. Additionally, the API uses `type` while the model uses `contract_type`.

**SQLAlchemy Model (`models/contracts.py`):**
```python
class Contract(Base):
    # ... other fields
    contract_type: Mapped[str] = mapped_column(String, index=True)
    is_blueprint_copy: Mapped[Optional[bool]]
```

**Pydantic Schema (`schemas/contracts.py`):**
```python
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

class ContractSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    # ... other fields

    # CORRECT: Use validation_alias to map 'type' from API to 'contract_type' in model
    contract_type: str = Field(validation_alias="type")

    # CORRECT: Ensure the field exists in the schema if it's in the model
    is_blueprint_copy: bool | None
```

**Anti-Pattern (to avoid):**
```python
class ContractSchema(BaseModel):
    # ...
    # INCORRECT: Field is named differently but not aliased
    type: str
    # INCORRECT: Field is missing entirely, will cause validation errors
    # is_blueprint_copy: bool | None
```

## 4. AI Action Mandate

As Cascade, I **must** adhere to the following process whenever I create or modify a SQLAlchemy model or a Pydantic schema that are meant to be linked:

1.  **Verify File Access:** Before generating code, I will use `view_file` to read both the target schema file and the corresponding model file to ensure I have the complete and current definitions.
2.  **Perform Field-by-Field Comparison:** I will manually compare every field in the model with the schema.
    *   Any field intended for API exposure in the model must exist in the schema.
    *   Any field in the schema must have a corresponding source in the model or be explicitly handled.
3.  **Enforce Naming Alignment:** If a field name in the schema (e.g., `type`) differs from the model attribute (`contract_type`), I **must** use `Field(validation_alias="...")` to declare the mapping.
4.  **Confirm Configuration:** I will verify that the schema's `ConfigDict` contains `from_attributes=True` and `populate_by_name=True`.

This checklist is non-negotiable to prevent runtime data validation errors.

## 5. Benefits

*   **Prevents Runtime Errors:** Directly mitigates a common class of hard-to-debug validation and attribute errors.
*   **Clarity and Maintainability:** Makes the mapping between API and database explicit and self-documenting.
*   **Improved Developer Confidence:** Reduces the likelihood of introducing subtle bugs when modifying data models.
