# Angular Pattern: Standalone Routed Component

**Pattern ID:** ANG-P-002

## 1. Problem Statement

In a modern, standalone Angular application, feature components are often the target of a route. A consistent pattern is needed for creating these components, ensuring they are self-contained, properly declare their dependencies, and can easily access route parameters.

## 2. Core Pattern

This pattern defines a standalone component that is loaded via the router. It uses the `@Component` decorator's `standalone: true` flag, imports its dependencies directly, uses `inject()` for service injection, and uses the `input()` function to bind route parameters directly to component properties.

### 2.1. The Standalone Component

**Key Components:**
*   **`standalone: true`**: Marks the component as a standalone component, meaning it manages its own dependencies.
*   **`imports` array**: Directly imports other standalone components, directives, or pipes used in the template.
*   **`inject()`**: The modern, preferred way to inject dependencies (like services) within the component's constructor context.
*   **`input()`**: Used to create a component input that can be bound to route parameters (requires `withComponentInputBinding()` in the router configuration).

```typescript
// e.g., in `app/src/app/features/contracts/pages/contract-detail/contract-detail.component.ts`
import { Component, inject, input, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';

// Import a standalone child component used in the template
import { ItemListComponent } from '../../components/item-list/item-list.component';

// Import the signal-based service
import { ContractDetailService } from '../../services/contract-detail.service';

@Component({
  selector: 'app-contract-detail',
  standalone: true,
  // 1. Import all dependencies for the template.
  imports: [CommonModule, ItemListComponent],
  template: `
    @if (detailService.loading()) {
      <p>Loading contract details...</p>
    } @else if (detailService.data(); as contract) {
      <h2>{{ contract.name }} (ID: {{ contractId() }})</h2>
      <p>Issuer: {{ contract.issuer }}</p>

      <!-- 2. Use the imported standalone child component -->
      <app-item-list [items]="contract.items"></app-item-list>
    } @else {
      <p>Contract not found or an error occurred.</p>
    }
  `,
})
export class ContractDetailComponent implements OnInit {
  // 3. Use input() to bind the 'id' route parameter.
  public contractId = input.required<string>();

  // 4. Use inject() to get an instance of the service.
  public detailService = inject(ContractDetailService);

  ngOnInit(): void {
    // 5. Call the service method, passing the route parameter from the input signal.
    this.detailService.loadContractDetails(this.contractId());
  }
}
```

## 3. The Corresponding Route Configuration

To make this work, the route configuration must enable component input binding.

```typescript
// In a routes file, e.g., `app.routes.ts` or `contracts.routes.ts`
import { Route } from '@angular/router';
import { ContractDetailComponent } from './pages/contract-detail/contract-detail.component';

export const routes: Route[] = [
  {
    // The ':id' parameter will be bound to the 'contractId' input.
    path: 'contracts/:id',
    component: ContractDetailComponent,
  },
  // ... other routes
];
```

And the main application router must be configured with `withComponentInputBinding()`.

```typescript
// In `app.config.ts`
// ...
provideRouter(routes, withComponentInputBinding()),
// ...
```

## 4. Rationale & Benefits

*   **Encapsulation:** The component is self-contained and explicitly declares its dependencies, making it easier to understand and reuse.
*   **Simplified Routing:** `withComponentInputBinding()` removes the need to inject `ActivatedRoute` and manually subscribe to `paramMap`, reducing boilerplate and complexity.
*   **Type Safety:** Using `input.required<string>()` provides compile-time safety for the route parameter.
*   **Testability:** The component is easier to test in isolation, as its dependencies (services, route params) can be easily mocked or provided.
