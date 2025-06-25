import { computed, inject, Injectable, signal } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { toObservable } from '@angular/core/rxjs-interop';
import { catchError, debounceTime, distinctUntilChanged, of, switchMap, tap } from 'rxjs';

import { ContractSearchFilters, PaginatedContractsResponse } from './contract.models';

/**
 * Defines the shape of an asynchronous data state, including loading and error status.
 */
export interface AsyncState<T> {
  loading: boolean;
  error: string | null;
  data: T | null;
}

/**
 * Manages the state for browsing and filtering public contracts.
 * Follows the advanced signal-based service pattern with an RxJS pipeline for API calls.
 */
@Injectable({
  providedIn: 'root',
})
export class ContractSearch {
  private http = inject(HttpClient);

  // The internal, private state of the service.
  #state = signal<AsyncState<PaginatedContractsResponse>>({
    loading: false,
    error: null,
    data: null,
  });

  // The internal, private signal for filters.
  #filters = signal<ContractSearchFilters>({ page: 1, size: 20 });

  // Public, read-only signals for consumers.
  readonly loading = computed(() => this.#state().loading);
  readonly error = computed(() => this.#state().error);
  readonly data = computed(() => this.#state().data);
  readonly filters = this.#filters.asReadonly();

  constructor() {
    // Reactive pipeline that triggers API calls when filters change.
    toObservable(this.#filters)
      .pipe(
        debounceTime(300), // Wait for 300ms of silence before proceeding.
        distinctUntilChanged(), // Only proceed if the filters have actually changed.
        tap(() => this.#state.update((s) => ({ ...s, loading: true }))), // Set loading to true, preserving old data.
        switchMap((filters) => {
          let params = new HttpParams()
            .set('page', filters.page.toString())
            .set('size', filters.size.toString());

          if (filters.search) {
            params = params.set('search', filters.search);
          }

          return this.http
            .get<PaginatedContractsResponse>('/api/v1/contracts/', { params })
            .pipe(
              catchError((err) => {
                const errorMessage = err.message ?? 'An unknown error occurred.';
                this.#state.set({ loading: false, error: errorMessage, data: null });
                return of(null); // Return a null observable to prevent the stream from dying.
              })
            );
        })
      )
      .subscribe((data) => {
        if (data) {
          this.#state.set({ loading: false, error: null, data });
        }
      });
  }

  /**
   * Updates the search filters. This is the primary way for components to interact
   * with the service and trigger a new data fetch.
   * @param newFilters A partial or full set of new filters.
   */
  updateFilters(newFilters: Partial<ContractSearchFilters>): void {
    this.#filters.update((current) => ({ ...current, ...newFilters }));
  }

  /**
   * Sets the initial filter state, typically from a route resolver.
   * This replaces the entire filter object.
   * @param initialFilters The complete set of initial filters.
   */
  setInitialFilters(initialFilters: ContractSearchFilters): void {
    this.#filters.set(initialFilters);
  }
}
