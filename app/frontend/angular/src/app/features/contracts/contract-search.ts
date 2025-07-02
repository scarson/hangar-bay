import { computed, inject, Injectable, signal, InjectionToken } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { catchError, debounceTime, distinctUntilChanged, of, switchMap, tap, Subject, startWith, map } from 'rxjs';
import { SchedulerLike, asyncScheduler } from 'rxjs';

import { ContractSearchFilters, PaginatedContractsResponse } from './contract.models';

/**
 * An injection token for providing a scheduler to the ContractSearch service,
 * primarily for testing purposes.
 */
export const SEARCH_SCHEDULER = new InjectionToken<SchedulerLike>('search.scheduler');

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

  private readonly apiUrl = '/api/v1/contracts/';
  private scheduler = inject(SEARCH_SCHEDULER, { optional: true }) ?? asyncScheduler;

  // A subject to trigger the pipeline when filters are updated.
  private filterTrigger$ = new Subject<void>();

  constructor() {
    this.filterTrigger$
      .pipe(
        startWith(undefined), // Trigger initial fetch
        debounceTime(300, this.scheduler),
        map(() => this.#filters()), // Get the latest filters from the signal
        distinctUntilChanged((prev, curr) => JSON.stringify(prev) === JSON.stringify(curr)),
        tap(() => this.#state.update((s) => ({ ...s, loading: true }))),
        switchMap((filters) => {
          let params = new HttpParams()
            .set('page', filters.page.toString())
            .set('size', filters.size.toString());

          if (filters.search) {
            params = params.set('search', filters.search);
          }

          if (filters.type) {
            params = params.set('type', filters.type);
          }

          if (filters.sort_by && filters.sort_order) {
            params = params.set('sort_by', filters.sort_by);
            params = params.set('sort_order', filters.sort_order);
          }

          return this.http.get<PaginatedContractsResponse>(this.apiUrl, { params }).pipe(
            catchError((error) => {
              console.error('API Error fetching contracts:', error);
              this.#state.update((s) => ({ ...s, loading: false, error: `An unknown error occurred. Please try again later.` }));
              return of(null);
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

  /**
   * Updates the search filters. This is the primary way for components to interact
   * with the service and trigger a new data fetch.
   * @param newFilters A partial or full set of new filters.
   */
  updateFilters(newFilters: Partial<ContractSearchFilters>): void {
    this.#filters.update((current) => ({ ...current, ...newFilters }));
    this.filterTrigger$.next();
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
