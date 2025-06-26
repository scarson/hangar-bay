---
description: Outlines standard strategies and best practices for testing the FastAPI backend.
---

# Guide: FastAPI Testing Strategies

## 1. Philosophy

Our testing strategy aims for a balance between confidence and speed. We want to be confident that our application works as expected, but we don't want tests to be so slow or brittle that they hinder development. We use a combination of unit tests and integration tests to achieve this.

- **Unit Tests:** Fast, isolated tests that check a single piece of logic (e.g., a single function or method) in isolation from its dependencies (like databases or external APIs).
- **Integration Tests:** Slower, more comprehensive tests that check how multiple components work together. These may involve a real (test) database or mocked external services.

## 2. Tools

- **`pytest`**: Our primary test runner. We use it for its powerful features like fixtures, parametrization, and plugins.
- **`pytest-asyncio`**: A pytest plugin for testing `asyncio` code.
- **`httpx.TestClient`**: FastAPI's recommended way to test API endpoints. It allows you to make requests to your application without needing to run a live server.
- **`unittest.mock`**: Python's built-in library for creating mock objects, which are essential for isolating code in unit tests.

## 3. Testing API Endpoints

Use `TestClient` to write integration tests for your API endpoints. These tests ensure that your endpoints behave correctly, handle authentication, and return the expected responses.

```python
# app/backend/src/fastapi_app/tests/api/test_contracts.py

from fastapi.testclient import TestClient
from fastapi_app.main import app

client = TestClient(app)

def test_get_public_contracts():
    response = client.get("/api/v1/contracts/")
    assert response.status_code == 200
    # Further assertions on the response body
    assert isinstance(response.json(), list)
```

## 4. Testing Service Classes

Service classes often contain business logic and interact with external dependencies. They should have both unit and integration tests.

### Unit Testing Services

For unit tests, mock all external dependencies (like the database or an API client) to test the service's logic in isolation.

```python
# app/backend/src/fastapi_app/tests/services/test_aggregation_service.py

import pytest
from unittest.mock import MagicMock, AsyncMock

from fastapi_app.services.background_aggregation import ContractAggregationService

@pytest.mark.asyncio
asnyc def test_aggregation_logic_with_mock_esi():
    # Arrange
    mock_esi_client = AsyncMock()
    mock_esi_client.get_public_contracts.return_value = [{'contract_id': 1, 'issuer_id': 100}]
    mock_esi_client.resolve_ids_to_names.return_value = {100: 'Test Issuer'}

    mock_settings = MagicMock()
    # ... configure settings ...

    service = ContractAggregationService(esi_client=mock_esi_client, settings=mock_settings)

    # Act
    # ... call the method to be tested ...

    # Assert
    # ... assert that the correct calls were made to the mocks ...
    mock_esi_client.resolve_ids_to_names.assert_called_once()
```

### Integration Testing Services

For integration tests, you might use a real test database to verify that data is being written correctly. You would still typically mock external APIs to avoid making real network calls.

## 5. Mocking Dependencies

FastAPI's dependency injection system makes it easy to override dependencies during testing. This is the preferred way to provide mocks to your application.

```python
# In your test file

from fastapi_app.main import app
from fastapi_app.core.dependencies import get_esi_client

async def override_get_esi_client():
    # Return a mock client instead of the real one
    return AsyncMock()

app.dependency_overrides[get_esi_client] = override_get_esi_client
```

## 6. The Limits of Testing: Patterns and Reviews

It is critical to understand that testing, especially unit testing, is not a silver bullet. Its primary strength is in verifying **functional correctness**—that a piece of code produces the correct output for a given input.

However, testing is often a weak defense against **architectural or non-functional errors**, such as:

- **Performance issues:** A unit test that mocks network calls will not detect that the code is inefficiently creating a new HTTP client for every call.
- **Security vulnerabilities:** A test might confirm a function works, but not that it properly sanitizes input.
- **Maintainability problems:** Tests do not typically measure code clarity or adherence to project conventions.

This is why our quality strategy relies on multiple layers of defense:

1.  **Testing:** Our first line of defense for catching functional bugs and regressions.
2.  **Documented Patterns:** Our primary tool for ensuring architectural consistency, performance, and maintainability. Adhering to patterns (like the [API Client Service Pattern](./../patterns/04-api-client-service-pattern.md)) prevents entire classes of non-functional bugs.
3.  **Code Review:** The human element that verifies both functional correctness and adherence to patterns. A good review asks not just "Does it work?" but "Does it work *correctly within our architecture*?"

## 7. Mandatory: Testing Structural Contracts & Protocols

While unit tests are excellent for verifying business logic, they can miss structural implementation errors. A common failure mode is designing a class to follow a specific pattern or protocol (like a context manager) but failing to implement the required methods (`__aenter__`, `__exit__`, etc.). This leads to `TypeError` exceptions at runtime, as seen with the `ESIClient` implementation.

To prevent this entire class of bugs, the following practice is **mandatory**:

**If a class is designed to implement a specific Python protocol, a dedicated, simple unit test must exist to verify its structural contract.**

This is not about testing the *logic* inside the methods, but simply that the methods *exist* and have the correct signature, making the class compliant with the protocol.

### Example: Testing an Async Context Manager

This test would have caught the `ESIClient` implementation bug before it was ever committed.

```python
# In a relevant test file, e.g., tests/core/test_esi_client_class.py
import pytest
from collections.abc import AsyncContextManager

from fastapi_app.core.esi_client_class import ESIClient
from fastapi_app.core.config import get_settings # or a mock

@pytest.mark.asyncio
asnyc def test_esi_client_is_valid_async_context_manager():
    """
    Verifies that ESIClient correctly implements the async context manager protocol.
    This is a structural test, not a functional one.
    """
    settings = get_settings() # Get real settings for instantiation
    client = ESIClient(settings=settings)

    # 1. Static check: Does it claim to be an AsyncContextManager?
    assert isinstance(client, AsyncContextManager)

    # 2. Dynamic check: Can it be used in an `async with` block without error?
    try:
        async with client as client_instance:
            assert client_instance is client
    except Exception as e:
        pytest.fail(f"ESIClient failed to function as an async context manager. Error: {e}")

```

This simple, fast-running test provides a powerful guarantee that our architectural patterns are being correctly implemented.
