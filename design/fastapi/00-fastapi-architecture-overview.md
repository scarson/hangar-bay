# FastAPI Backend Architecture Overview

This document provides a high-level overview of the Hangar Bay FastAPI backend architecture, including its layers, key components, and core design patterns. It serves as the primary architectural reference for all backend development.

## 1. Core Principles

-   **Layered Architecture**: The backend is organized into distinct layers (Controllers, Services, Data Access) to promote separation of concerns, testability, and maintainability.
-   **Dependency Injection (DI)**: FastAPI's native DI system is used extensively to manage dependencies, provide resources like database sessions and API clients, and decouple components.
-   **Configuration as Code**: Application settings are managed centrally via a Pydantic [Settings](cci:2://file:///c:/Users/Sam/OneDrive/Documents/Code/hangar-bay/app/backend/src/fastapi_app/core/config.py:7:0-85:85) class, loaded from environment variables and a `.env` file. This provides type-safe, validated configuration.
-   **Asynchronous Everywhere**: The entire stack is asynchronous, from the database drivers to the API clients, to ensure high performance and scalability.

## 2. Architectural Layers

### 2.1. Controller Layer (`/routers`)

-   **Purpose**: Defines the API endpoints, handles HTTP request/response logic, and performs data validation using Pydantic models.
-   **Responsibilities**:
    -   Define API routes (`@router.get`, `@router.post`, etc.).
    -   Inject services using `Depends()`.
    -   Delegate business logic to the appropriate service.
    -   Return Pydantic models as JSON responses.
-   **Example**: `app/backend/src/fastapi_app/routers/contracts.py`

### 2.2. Service Layer (`/services`)

-   **Purpose**: Encapsulates all business logic. This is the core of the application.
-   **Responsibilities**:
    -   Implement complex operations and workflows.
    -   Coordinate between different data sources (e.g., database, external APIs).
    -   Can be injected into controllers or other services.
-   **Example**: `app/backend/src/fastapi_app/services/contract_service.py`

### 2.3. Data Access Layer (`/models`, `/db`)

-   **Purpose**: Manages all interactions with the database.
-   **Components**:
    -   **SQLAlchemy Models** (`/models`): Define the database schema as Python classes.
    -   **Database Session Management** (`/db/session.py`): Provides a dependency (`get_db`) to manage the lifecycle of database sessions for API requests.

## 3. Key Patterns & Solutions

### 3.1. The Dual-Mode Service Pattern for Background Jobs

A critical challenge in this architecture is integrating services with `apscheduler` for background tasks, as the scheduler requires jobs to be *picklable*. However, services often rely on unpicklable resources like database connections or HTTP clients for performance.

We solve this with a **Dual-Mode Service Pattern** that allows a service to be both high-performance for API requests and picklable for background jobs.

For a detailed explanation and implementation guide, see the full pattern documentation:
-   **[Pattern: Dual-Mode Service for Background Jobs](./patterns/05-dual-mode-service-pattern.md)**

### 3.2. Configuration Management

-   **Source**: `app/backend/src/fastapi_app/core/_config.py_`
-   **Mechanism**: A single [Settings](cci:2://file:///c:/Users/Sam/OneDrive/Documents/Code/hangar-bay/app/backend/src/fastapi_app/core/config.py:7:0-85:85) class inherits from `pydantic_settings.BaseSettings`. It defines all required configuration variables with types and optional default values.
-   **Loading**: Settings are automatically loaded from environment variables or a `.env` file.
-   **Requirement**: Any new configuration needed by a service (e.g., `ESI_TIMEOUT`) **must** be added to this central [Settings](cci:2://file:///c:/Users/Sam/OneDrive/Documents/Code/hangar-bay/app/backend/src/fastapi_app/core/config.py:7:0-85:85) class to ensure it's available throughout the application.