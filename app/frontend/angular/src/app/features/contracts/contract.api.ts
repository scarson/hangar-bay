import { Injectable, inject, signal } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { catchError, finalize, of, tap } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  PaginatedShipContractsResponse,
  ShipContract,
  ShipContractsRequestParams,
} from './contract.model';

export interface ContractApiState {
  contracts: ShipContract[];
  totalItems: number;
  totalPages: number;
  loading: boolean;
  error: string | null;
}

@Injectable({
  providedIn: 'root',
})
export class ContractApi {
  private http = inject(HttpClient);

  // Internal state management with a Signal
  private readonly _state = signal<ContractApiState>({
    contracts: [],
    totalItems: 0,
    totalPages: 0,
    loading: false,
    error: null,
  });

  // Expose state as a public, readonly signal
  public readonly state = this._state.asReadonly();

  constructor() {}

  /**
   * Fetches ship contracts from the backend API and updates the service state.
   * @param params Optional query parameters for pagination and filtering.
   */
  getContracts(params?: ShipContractsRequestParams): void {
    // Set loading state and clear previous errors
    this._state.update((current) => ({
      ...current,
      loading: true,
      error: null,
    }));

    // Build query parameters, ignoring null/undefined values
    let httpParams = new HttpParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== null && value !== undefined) {
          httpParams = httpParams.set(key, value.toString());
        }
      });
    }

    const apiUrl = `${environment.apiUrl}/contracts/ships`;

    this.http
      .get<PaginatedShipContractsResponse>(apiUrl, { params: httpParams })
      .pipe(
        tap((response) => {
          // Update state with the fetched data on success
          this._state.update((current) => ({
            ...current,
            contracts: response.items,
            totalItems: response.total_items,
            totalPages: response.total_pages,
          }));
        }),
        catchError((err: HttpErrorResponse) => {
          // Log the full error for debugging
          console.error('API Error fetching contracts:', err);

          // Update state with a user-friendly error message
          this._state.update((current) => ({
            ...current,
            error: 'Failed to load contracts. Please try again later.',
          }));

          // Return an empty observable to complete the stream
          return of(null);
        }),
        finalize(() => {
          // Ensure loading is set to false when the stream completes or errors
          this._state.update((current) => ({ ...current, loading: false }));
        })
      )
      .subscribe(); // Subscribe to trigger the HTTP request
  }
}

