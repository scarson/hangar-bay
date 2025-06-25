# Angular Pattern: Lazy-Loaded Routes File

**Pattern ID:** ANG-P-003

## 1. Problem Statement

As an application grows, eagerly loading all routes and their associated components at startup dramatically increases the initial load time and bundle size. A scalable pattern is needed to define feature-specific routes that are only loaded when the user navigates to that section of the application.

## 2. Core Pattern

This pattern involves creating a dedicated `*.routes.ts` file for each feature area. This file exports a `Route[]` array. The main application router then uses the `loadChildren` property with a dynamic `import()` to lazy-load this entire set of routes when the user navigates to the feature's path.

### 2.1. The Feature Routes File (`contracts.routes.ts`)

This file defines all routes related to the "contracts" feature. It is kept separate from any component file.

**Key Components:**
*   **`Route[]`**: A typed array of route objects.
*   **`path`**: The URL path for the route, relative to the parent path defined in `loadChildren`.
*   **`loadComponent`**: Used for individual routes within the lazy-loaded module. It takes a dynamic `import()` that resolves to a standalone component.

```typescript
// e.g., in `app/src/app/features/contracts/contracts.routes.ts`
import { Route } from '@angular/router';

// Note: This file ONLY contains the route definitions.
export const CONTRACTS_ROUTES: Route[] = [
  {
    // Path: /contracts/ (or /contracts if 'full' path match)
    path: '',
    loadComponent: () =>
      import('./pages/contract-list/contract-list.component').then(
        (m) => m.ContractListComponent
      ),
    title: 'Browse Contracts',
  },
  {
    // Path: /contracts/123
    path: ':id',
    loadComponent: () =>
      import('./pages/contract-detail/contract-detail.component').then(
        (m) => m.ContractDetailComponent
      ),
    title: 'Contract Details',
  },
  // Add other contract-related routes here
];
```

### 2.2. The Main Application Router (`app.routes.ts`)

The main router file points to the feature routes file.

**Key Components:**
*   **`loadChildren`**: The key to lazy loading. It takes a dynamic `import()` that resolves to the feature's `Route[]` array.

```typescript
// e.g., in `app/src/app/app.routes.ts`
import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./pages/home/home.component').then(m => m.HomeComponent),
    pathMatch: 'full',
  },
  {
    // When a user navigates to a URL starting with 'contracts',
    // the `contracts.routes.ts` file will be downloaded and its routes loaded.
    path: 'contracts',
    loadChildren: () =>
      import('./features/contracts/contracts.routes').then(
        (m) => m.CONTRACTS_ROUTES
      ),
  },
  {
    path: '**',
    loadComponent: () => import('./pages/not-found/not-found.component').then(m => m.NotFoundComponent),
    title: 'Page Not Found',
  }
];
```

## 3. Rationale & Benefits

*   **Performance:** Code for a feature is only downloaded when it's needed, leading to faster initial application loads.
*   **Scalability:** New features can be added without increasing the size of the main bundle. The routing configuration is decentralized and scales well.
*   **Encapsulation:** All routes for a feature are co-located, making the feature area self-contained and easier to reason about.
*   **Clear Separation of Concerns:** The routing configuration is cleanly separated from the component logic.
