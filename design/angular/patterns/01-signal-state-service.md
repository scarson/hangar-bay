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

## 5. Advanced Pattern: Service with Dynamic Filters

The basic pattern is excellent for simple data fetching, but real-world applications often require fetching data based on dynamic user input, such as search terms, sorting, or pagination. This advanced pattern extends the signal service to handle this complexity using an RxJS pipeline for robust, debounced API calls.

### 5.1. Extended State and Service Logic

The service state is expanded to include the current filters. An RxJS pipeline, triggered by changes to the filters, manages the data fetching lifecycle.

```typescript
// e.g., in `app/src/app/features/contracts/services/contract-search.service.ts`
import { Injectable, signal, computed, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { toObservable } from '@angular/core/rxjs-interop';
import { of } from 'rxjs';
import { switchMap, debounceTime, catchError } from 'rxjs/operators';

// Assume interfaces are defined elsewhere
import { PaginatedContractsResponse, ContractSearchFilters } from '../models/contract.models';
import { AsyncState } from '@core/interfaces/async-state.interface';

// The full state now includes the filters that produced the data.
type ContractSearchState = AsyncState<PaginatedContractsResponse> & {
  filters: ContractSearchFilters;
};

@Injectable({ providedIn: 'root' })
export class ContractSearchService {
  private http = inject(HttpClient);

  // 1. Private writable signal for the complete state.
  private state = signal<ContractSearchState>({
    loading: true, // Start in loading state initially
    error: null,
    data: null,
    filters: { page: 1, query: '', faction: null }, // Default initial filters
  });

  // 2. Public computed signals for easy consumption.
  public loading = computed(() => this.state().loading);
  public error = computed(() => this.state().error);
  public data = computed(() => this.state().data);
  private filters = computed(() => this.state().filters);

  // 3. Observable of filters, which will drive the API calls.
  private filters$ = toObservable(this.filters);

  constructor() {
    // 4. RxJS pipeline to react to filter changes.
    this.filters$.pipe(
      debounceTime(300), // Wait for user to stop typing
      switchMap(currentFilters => {
        // Set loading state, but preserve stale data for better UX
        this.state.update(s => ({ ...s, loading: true }));
        
        const params = new HttpParams({ fromObject: { ...currentFilters } as any });
        return this.http.get<PaginatedContractsResponse>('/api/v1/contracts', { params }).pipe(
          catchError(err => {
            // On HTTP error, create a state object to pass through the stream
            return of({ error: err, data: null, loading: false });
          })
        );
      })
    ).subscribe(response => {
      // 5. Update state with the result of the API call.
      if (response.error) {
        this.state.update(s => ({ ...s, loading: false, error: response.error, data: null }));
      } else {
        this.state.update(s => ({ ...s, loading: false, error: null, data: response as PaginatedContractsResponse }));
      }
    });
  }

  // 6. Public methods to allow components to update filters.
  public updateFilters(newFilters: Partial<ContractSearchFilters>): void {
    this.state.update(s => ({
      ...s,
      // When filters change, go into a loading state immediately
      loading: true,
      filters: { ...s.filters, ...newFilters },
    }));
  }
  
  public setInitialFilters(initialFilters: ContractSearchFilters): void {
      this.state.update(s => ({ ...s, filters: initialFilters }));
  }
}
```

### 5.2. Rationale for Additions

*   **Stale-While-Revalidate:** By setting `loading: true` but not clearing `data`, the UI can show a loading indicator over the old, stale data. This is a much better user experience than a blank screen.
*   **RxJS for Complex Events:** Using `debounceTime` prevents excessive API calls while the user is interacting with filters. `switchMap` automatically cancels previous, in-flight requests, preventing race conditions where an older request could return after a newer one.
*   **Centralized Logic:** All of this complex logic is encapsulated within the service, keeping components simple and focused on presentation.

### 5.3. Note on Initial State with Route Resolvers

For bookmarkable URLs, it's a best practice to initialize the service's filters from the URL's query parameters. An Angular Route Resolver is the ideal tool for this. The resolver would parse the `ActivatedRouteSnapshot.queryParams`, create an initial `ContractSearchFilters` object, and this object would be passed to the service's `setInitialFilters` method before the component loads. This decouples the service from the router and makes it more testable.
