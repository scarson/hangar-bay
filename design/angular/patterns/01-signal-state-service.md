# Angular Pattern: Signal-Based Service with AsyncState

**Pattern ID:** ANG-P-001

## 1. Problem Statement

When fetching asynchronous data from an API, components need a consistent way to handle the three primary states of the operation: loading, success (with data), and error. Services should manage this state and expose it reactively to the rest of the application without requiring consumers to manage complex RxJS subscription logic.

## 2. Core Pattern

This pattern uses Angular Signals to create a reactive, easy-to-consume state management service. It defines a generic `AsyncState<T>` interface and implements a service that manages this state internally with a `writableSignal` and exposes it through `computed` signals and `public` signals.

### 2.1. The `AsyncState<T>` Interface

This interface provides a standardized structure for tracking the state of an async operation.

```typescript
// e.g., in `app/src/app/core/interfaces/async-state.interface.ts`
export interface AsyncState<T> {
  loading: boolean;
  error: Error | null;
  data: T | null;
}
```

### 2.2. The Signal-Based Service Implementation

The service encapsulates the state and the logic to fetch and update it.

**Key Components:**
*   **`state` (private writableSignal):** The single source of truth for the service's state.
*   **`loading`, `error`, `data` (public signals):** Read-only signals derived from the private `state` signal, providing safe, reactive access for consumers.
*   **`loadContracts()` (public method):** The public API for triggering the data fetch operation.

```typescript
// e.g., in `app/src/app/features/contracts/services/contract-api.service.ts`
import { Injectable, signal, computed, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { lastValueFrom } from 'rxjs';

// Assuming Contract and AsyncState interfaces are defined elsewhere
import { Contract } from '../models/contract.model';
import { AsyncState } from '@core/interfaces/async-state.interface';

@Injectable({
  providedIn: 'root',
})
export class ContractApiService {
  private http = inject(HttpClient);

  // 1. Private writable signal holds the full state object.
  private state = signal<AsyncState<Contract[]>>({
    loading: false,
    error: null,
    data: null,
  });

  // 2. Public computed signals for easy consumption in templates/components.
  public loading = computed(() => this.state().loading);
  public error = computed(() => this.state().error);
  public data = computed(() => this.state().data);

  // 3. Public method to trigger the async operation.
  async loadContracts(): Promise<void> {
    // 4. Set loading state to true immediately.
    this.state.update((s) => ({ ...s, loading: true, error: null }));

    try {
      // 5. Fetch data.
      const contracts = await lastValueFrom(
        this.http.get<Contract[]>('/api/v1/contracts')
      );
      // 6. On success, update state with data and set loading to false.
      this.state.update((s) => ({ ...s, loading: false, data: contracts }));
    } catch (e) {
      // 7. On error, update state with error and set loading to false.
      this.state.update((s) => ({ ...s, loading: false, error: e as Error }));
    }
  }
}
```

## 3. How to Use in a Component

A component injects the service and binds directly to its public signals.

```typescript
// e.g., in a contract list component
import { Component, inject, OnInit } from '@angular/core';
import { ContractApiService } from '../services/contract-api.service';

@Component({
  selector: 'app-contract-list',
  standalone: true,
  imports: [/* CommonModule, etc. */],
  template: `
    @if (contractService.loading()) {
      <p>Loading contracts...</p>
    } @else if (contractService.error(); as error) {
      <p>Error: {{ error.message }}</p>
    } @else if (contractService.data(); as contracts) {
      <ul>
        @for (contract of contracts; track contract.id) {
          <li>{{ contract.name }}</li>
        }
      </ul>
    }
  `
})
export class ContractListComponent implements OnInit {
  public contractService = inject(ContractApiService);

  ngOnInit(): void {
    this.contractService.loadContracts();
  }
}

```

## 4. Rationale & Benefits

*   **Simplicity:** Consumers of the service don't need to manage subscriptions. They just use the signals.
*   **Reactivity:** The UI automatically updates whenever the service's state changes.
*   **Encapsulation:** The state mutation logic is contained entirely within the service.
*   **Testability:** The service can be tested by calling its public methods and asserting changes to its public signal values.
*   **Performance:** Aligns with Angular's modern, signal-based, zoneless change detection strategy for optimal performance.
