## AI Analysis Guidance for Cascade

This file is over 200 lines long. Unless you are only looking for a specific section, you should read the entire file, which may require multiple tool calls.

# Angular State Management & RxJS (Hangar Bay)

**Last Updated:** 2025-06-09

## 1. Introduction

Effective state management is crucial for building robust and maintainable Angular applications. For Hangar Bay, we adopt a **"Signals First"** approach for managing reactive state, complemented by RxJS for complex asynchronous operations and event stream management. This document outlines our strategies, best practices, and how these two paradigms interoperate.

Referenced from: Angular Docs, `llms-full.txt` (positions 20-21 for Signals, 23-25 for RxJS), `../angular-frontend-architecture.md` (Section 2.2, Section 5).

## 2. Angular Signals: The Primary Reactive Primitive

Angular Signals provide a fine-grained, synchronous reactivity model. They are the preferred way to manage state within components and services for most scenarios.

### 2.1. Core Signal Concepts

-   **`signal<T>(initialValue)`:** Creates a writable signal. This is a container for a value that can change over time. When its value changes, Angular knows exactly which parts of the application need to update.
    ```typescript
    import { signal } from '@angular/core';
    const count = signal(0);
    count.set(1);
    count.update(current => current + 1);
    console.log(count()); // Reads the current value
    ```
-   **`computed<T>(computationFn)`:** Creates a read-only signal whose value is derived from other signals. It automatically re-computes its value when any of its dependent signals change.
    ```typescript
    const firstName = signal('Jane');
    const lastName = signal('Doe');
    const fullName = computed(() => `${firstName()} ${lastName()}`);
    // fullName() will update if firstName() or lastName() changes.
    ```
-   **`effect(effectFn, options?)`:** Schedules a side effect to run whenever any of the signals read within its function change. Effects are useful for logging, analytics, or manually interacting with the DOM (though `afterRender` / `afterNextRender` are often better for DOM work).
    ```typescript
    effect(() => {
      console.log(`The current count is: ${count()}`);
    });
    ```
    -   **Cleanup:** Effects can register a cleanup function, which is crucial if the effect sets up long-lived resources (e.g., global event listeners, timers not tied to component lifecycle).
        ```typescript
        effect((onCleanup) => {
          const timer = setInterval(() => console.log('tick'), 1000);
          onCleanup(() => clearInterval(timer));
        });
        ```
    -   **`manualCleanup`:** By default, effects are automatically cleaned up when their enclosing context (e.g., component) is destroyed. If an effect is created outside such a context (e.g., in a service constructor without `destroyRef`), you might need `manualCleanup: true` and to manage its lifecycle explicitly.

### 2.2. State in Components

-   **Local UI State:** Manage component-specific UI state directly using signals.
    ```typescript
    import { Component, signal, computed } from '@angular/core';

    @Component({
      selector: 'hb-counter',
      standalone: true,
      template: `
        <button (click)="decrement()">-</button>
        <span>{{ count() }}</span>
        <button (click)="increment()">+</button>
        <p>Double count: {{ doubleCount() }}</p>
      `
    })
    export class CounterComponent {
      count = signal(0);
      doubleCount = computed(() => this.count() * 2);

      increment() { this.count.update(c => c + 1); }
      decrement() { this.count.update(c => c - 1); }
    }
    ```
-   **Inputs as Signals:** Component inputs defined with `input()` are already signals. See `02-component-and-directive-deep-dive.md`.

### 2.3. State in Services

-   **Shared Application State:** Services are the ideal place for managing state shared across multiple components or application-wide.
-   **Expose State via Signals:** Services should expose their state as signals (writable or computed/read-only).
    ```typescript
    import { Injectable, signal, computed, effect, inject, DestroyRef } from '@angular/core';
    import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
    import { HttpClient } from '@angular/common/http';
    import { tap } from 'rxjs/operators';

    interface User { id: string; name: string; }

    @Injectable({ providedIn: 'root' })
    export class UserService {
      private http = inject(HttpClient);
      private destroyRef = inject(DestroyRef); // For automatic cleanup of subscriptions

      // Private writable signal for internal state management
      private readonly _currentUser = signal<User | null>(null);
      private readonly _isLoading = signal<boolean>(false);

      // Public read-only signals for consumers
      readonly currentUser = this._currentUser.asReadonly();
      readonly isLoading = this._isLoading.asReadonly();
      readonly isLoggedIn = computed(() => !!this._currentUser());

      constructor() {
        // Example: Load initial user from local storage or an effect
        const storedUser = localStorage.getItem('currentUser');
        if (storedUser) {
          this._currentUser.set(JSON.parse(storedUser));
        }

        effect(() => {
          // Persist user to local storage when it changes
          const user = this._currentUser();
          if (user) {
            localStorage.setItem('currentUser', JSON.stringify(user));
          } else {
            localStorage.removeItem('currentUser');
          }
        });
      }

      fetchUser(id: string) {
        this._isLoading.set(true);
        this.http.get<User>(`/api/users/${id}`)
          .pipe(
            tap(user => this._currentUser.set(user)),
            takeUntilDestroyed(this.destroyRef) // Auto-unsubscribe on service destruction
          )
          .subscribe({
            error: (err) => {
              console.error('Failed to fetch user', err);
              this._currentUser.set(null);
              this._isLoading.set(false);
            },
            complete: () => this._isLoading.set(false)
          });
      }

      logout() {
        this._currentUser.set(null);
      }
    }
    ```

## 3. RxJS: For Complex Asynchronous Operations

While Signals are excellent for synchronous state reactivity, RxJS remains powerful for managing complex asynchronous operations, event streams, and intricate data transformations over time.

### 3.1. When to Use RxJS

-   **HTTP Requests:** `HttpClient` returns Observables. RxJS operators (`map`, `filter`, `switchMap`, `catchError`, etc.) are invaluable for processing HTTP responses.
-   **Complex Event Sequences:** Handling sequences of user interactions (e.g., drag-and-drop, multi-key shortcuts), WebSocket messages, or real-time data streams.
-   **Advanced Asynchronous Control:** Scenarios requiring debouncing, throttling, retries with backoff, or combining multiple asynchronous sources.
-   **Interoperability:** When integrating with libraries or browser APIs that expose events as Observables.

### 3.2. Integrating RxJS with Signals: `rxjs-interop`

Angular provides the `rxjs-interop` package to bridge Signals and Observables seamlessly.

-   **`toSignal(observable$, options?)`:** Converts an Observable to a Signal. This is extremely useful for displaying data from Observables in templates or using it in computed signals.
    ```typescript
    import { Component, inject } from '@angular/core';
    import { toSignal } from '@angular/core/rxjs-interop';
    import { DataService } from './data.service'; // Assumes DataService has a data$ observable

    @Component({
      selector: 'hb-data-display',
      standalone: true,
      template: `
        @if (data()) {
          <p>Data: {{ data()?.value }}</p>
        } @else if (error()) {
          <p>Error: {{ error()?.message }}</p>
        } @else {
          <p>Loading data...</p>
        }
      `
    })
    export class DataDisplayComponent {
      private dataService = inject(DataService);
      // Convert an observable to a signal.
      // `initialValue` is recommended to avoid `undefined` during initial load.
      // `requireSync: true` can be used if the observable is known to emit synchronously.
      data = toSignal(this.dataService.data$, { initialValue: null });
      error = toSignal(this.dataService.error$, { initialValue: null });
    }
    ```
    -   **`initialValue`:** Important for type safety and avoiding `undefined` states before the observable emits.
    -   **Error Handling:** `toSignal` will propagate errors from the observable. The resulting signal will hold the error object.
    -   **Completion:** If the observable completes, the signal will keep its last emitted value.
    -   **`destroyRef`:** `toSignal` automatically unsubscribes when the component/service is destroyed if a `DestroyRef` is available via injection.

-   **`takeUntilDestroyed(destroyRef?)`:** A pipeable operator to automatically unsubscribe from an observable when the component/service is destroyed. This is crucial for preventing memory leaks with manual subscriptions.
    ```typescript
    // In a component or service constructor or ngOnInit
    this.someObservable$
      .pipe(takeUntilDestroyed(this.destroyRef)) // inject DestroyRef
      .subscribe(value => console.log(value));
    ```

### 3.3. The "Stateful Service" Pattern for Asynchronous Data

When building features that fetch data based on user input (e.g., search, filtering), a more robust pattern is required to handle race conditions and manage state transitions gracefully. The `ContractSearch` service from Phase 4 is the canonical example of this pattern.

**Core Principles:**

1.  **Centralized State in a Service:** The injectable service is the single source of truth.
2.  **Private Writable Signals:** The service uses private `signal` instances to hold the internal state (`AsyncState` and filters). This prevents components from directly mutating the state.
3.  **Public Read-Only Signals:** The service exposes state to the application via public `computed` or `asReadonly()` signals. Components react to this state but cannot change it directly.
4.  **RxJS for the Pipeline:** An RxJS pipeline is used to orchestrate the asynchronous data fetching, providing crucial operators like `debounceTime` and `switchMap`.
5.  **Explicit Trigger:** A method (`updateFilters`) is exposed to allow components to signal their intent to change the state, which then triggers the RxJS pipeline.

**Canonical Example: `ContractSearch` Service**

This service manages fetching a paginated list of contracts based on filter criteria.

```typescript
import { computed, inject, Injectable, signal, InjectionToken } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { catchError, debounceTime, distinctUntilChanged, of, switchMap, tap, Subject, startWith, map } from 'rxjs';
import { SchedulerLike, asyncScheduler } from 'rxjs';

import { ContractSearchFilters, PaginatedContractsResponse } from './contract.models';

// ... AsyncState interface ...

@Injectable({
  providedIn: 'root',
})
export class ContractSearch {
  private http = inject(HttpClient);

  // Private, internal state
  #state = signal<AsyncState<PaginatedContractsResponse>>({ loading: false, error: null, data: null });
  #filters = signal<ContractSearchFilters>({ page: 1, size: 20 });

  // Public, read-only signals for consumers
  readonly loading = computed(() => this.#state().loading);
  readonly error = computed(() => this.#state().error);
  readonly data = computed(() => this.#state().data);
  readonly filters = this.#filters.asReadonly();

  private readonly apiUrl = '/api/v1/contracts/';
  private scheduler = inject(SEARCH_SCHEDULER, { optional: true }) ?? asyncScheduler;

  private filterTrigger$ = new Subject<void>();

  constructor() {
    this.filterTrigger$
      .pipe(
        startWith(undefined), // Trigger initial fetch
        debounceTime(300, this.scheduler), // Wait for user to stop typing
        map(() => this.#filters()), // Get the latest filters from the signal
        distinctUntilChanged((prev, curr) => JSON.stringify(prev) === JSON.stringify(curr)),
        tap(() => this.#state.update((s) => ({ ...s, loading: true }))), // Set loading state
        switchMap((filters) => { // Key operator: cancels previous, stale requests
          let params = new HttpParams() // ... build params
          return this.http.get<PaginatedContractsResponse>(this.apiUrl, { params }).pipe(
            catchError((error) => { // Handle errors within the stream
              this.#state.update((s) => ({ ...s, loading: false, error: `An error occurred.` }));
              return of(null); // Prevent pipeline from dying
            })
          );
        })
      )
      .subscribe((response) => {
        if (response) {
          this.#state.update((s) => ({ ...s, loading: false, data: response, error: null }));
        }
      });
  }

  updateFilters(newFilters: Partial<ContractSearchFilters>): void {
    this.#filters.update((current) => ({ ...current, ...newFilters }));
    this.filterTrigger$.next(); // Trigger the pipeline
  }
}
```

## 4. Choosing Between Signals and RxJS

| Feature / Scenario             | Prefer Signals                                  | Prefer RxJS                                       |
| ------------------------------ | ----------------------------------------------- | ------------------------------------------------- |
| **Synchronous State**          | Yes (e.g., form state, UI visibility)           | Can be used, but Signals are often simpler        |
| **Derived State (Sync)**       | Yes (`computed()`)                              | Can be used (`map`, `combineLatest`), but `computed` is simpler |
| **Simple Async Values**        | `toSignal(observable$)`                         | Source is often an Observable                     |
| **HTTP Requests**              | Use `HttpClient` (returns Observable), then `toSignal` | Yes (core `HttpClient` usage)                     |
| **Complex Async Logic**        |                                                 | Yes (chaining operators, `switchMap`, `mergeMap`) |
| **Event Streams**              |                                                 | Yes (WebSockets, complex UI event sequences)      |
| **Rate Limiting / Timing**     |                                                 | Yes (`debounceTime`, `throttleTime`, `delay`)     |
| **Fine-grained Change Detection**| Built-in                                        | Requires `async` pipe or manual `markForCheck`    |
| **Template Binding**           | Direct binding to signal values                 | `async` pipe or `toSignal` for easy binding     |

**General Guideline:**
-   Start with **Signals** for most component and service state.
-   Use **RxJS** when you need its powerful operators for complex asynchronous tasks or event stream manipulation.
-   Use **`toSignal`** to bring reactive values from Observables into the Signal world for consumption in templates or computed signals.
-   Always ensure Observables are properly unsubscribed (often via `takeUntilDestroyed` or `toSignal`'s automatic behavior).

## 5. Avoiding Common Pitfalls

-   **Large `effect`s:** Avoid putting too much logic or multiple unrelated side effects into a single `effect`. Break them down if they react to different signal changes for different purposes.
-   **`effect` for Derived State:** Don't use `effect` to update another signal. This is what `computed` is for. An anti-pattern: `effect(() => mySignal.set(anotherSignal() * 2));`. Correct: `mySignal = computed(() => anotherSignal() * 2);` (if `mySignal` is meant to be derived).
-   **Manual Subscriptions without Cleanup:** If you manually `subscribe()` to an Observable, you *must* unsubscribe to prevent memory leaks. Use `takeUntilDestroyed` or manage subscriptions carefully and call `unsubscribe()` in `ngOnDestroy`.
-   **Overuse of `toSignal` without `initialValue`:** Can lead to templates briefly showing `undefined` or requiring `?.` operators everywhere. Providing a sensible `initialValue` often improves template clarity.

By understanding the strengths of both Signals and RxJS and how they interoperate, we can build highly reactive, performant, and maintainable applications in Hangar Bay.
