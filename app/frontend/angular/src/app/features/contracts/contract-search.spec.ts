import { TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestScheduler } from 'rxjs/testing';
import { provideHttpClient } from '@angular/common/http';

import { ContractSearch, SEARCH_SCHEDULER } from './contract-search';
import { PaginatedContractsResponse } from './contract.models';

// Mock data for tests
const mockInitialData: PaginatedContractsResponse = {
  total: 1,
  page: 1,
  size: 20,
  items: [
    {
      contract_id: 1,
      issuer_id: 1001,
      issuer_corporation_id: 2001,
      start_location_id: 5001,
      type: 'item_exchange',
      status: 'outstanding',
      for_corporation: false,
      date_issued: '2024-01-01T00:00:00Z',
      date_expired: '2024-01-08T00:00:00Z',
      is_ship_contract: false,
      items: [],
    },
  ],
};

describe('ContractSearch with TestScheduler', () => {
  let httpMock: HttpTestingController;
  let testScheduler: TestScheduler;

  beforeEach(() => {
    testScheduler = new TestScheduler((actual, expected) => {
      expect(actual).toEqual(expected);
    });

    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideHttpClient(),
        provideHttpClientTesting(),
        ContractSearch,
        { provide: SEARCH_SCHEDULER, useValue: testScheduler },
      ],
    });

    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should have correct initial state before debounce', () => {
    const service = TestBed.inject(ContractSearch);
    expect(service.loading()).toBe(false);
    expect(service.error()).toBeNull();
    expect(service.data()).toBeNull();
    // No flush, so no API call
    httpMock.expectNone('/api/v1/contracts/?page=1&size=20');
  });

  it('should fetch initial data after debounceTime', () => {
    testScheduler.run(({ flush }) => {
      // Per testing guide 8.3, service is instantiated inside the run() callback.
      const service = TestBed.inject(ContractSearch);
      flush(); // Let debounceTime pass and trigger the initial API call

      const req = httpMock.expectOne('/api/v1/contracts/?page=1&size=20');
      expect(req.request.method).toBe('GET');
      req.flush(mockInitialData);

      expect(service.data()).toEqual(mockInitialData);
      expect(service.loading()).toBe(false);
    });
  });

  it('should manage loading state correctly', () => {
    testScheduler.run(({ flush }) => {
      // Per testing guide 8.3, service is instantiated inside the run() callback.
      const service = TestBed.inject(ContractSearch);
      expect(service.loading()).toBe(false);

      flush(); // Trigger the pipeline

      // After debounce, before flush, loading should be true
      expect(service.loading()).toBe(true);

      const req = httpMock.expectOne('/api/v1/contracts/?page=1&size=20');
      req.flush(mockInitialData);

      // After request completes, loading should be false
      expect(service.loading()).toBe(false);
    });
  });

  it('should include the type parameter in the API request when the type filter is set', () => {
    testScheduler.run(({ flush }) => {
      const service = TestBed.inject(ContractSearch);
      flush(); // Initial fetch
      httpMock.expectOne('/api/v1/contracts/?page=1&size=20').flush(mockInitialData);

      service.updateFilters({ type: 'auction' });
      flush(); // Trigger filter update

      const req = httpMock.expectOne((r) => r.url.startsWith('/api/v1/contracts/'));
      expect(req.request.params.get('type')).toBe('auction');
      req.flush(mockInitialData);
    });
  });

  it('should debounce filter updates to prevent excessive API calls', () => {
    testScheduler.run(({ flush }) => {
      // Per testing guide 8.3, service is instantiated inside the run() callback.
      const service = TestBed.inject(ContractSearch);

      // Handle initial call from constructor
      flush();
      httpMock.expectOne('/api/v1/contracts/?page=1&size=20').flush(mockInitialData);

      // Trigger multiple updates within the debounce window
      service.updateFilters({ search: 'test1' });
      testScheduler.schedule(() => service.updateFilters({ search: 'test2' }), 100);
      testScheduler.schedule(() => service.updateFilters({ search: 'test3' }), 200);

      flush(); // Advance time past the debounce period

      // Only one request for the latest value should be made
      const req = httpMock.expectOne('/api/v1/contracts/?page=1&size=20&search=test3');
      expect(req.request.method).toBe('GET'); // Add explicit expectation
      req.flush(mockInitialData);
    });
  });

  it('should handle API errors gracefully', () => {
    testScheduler.run(({ flush }) => {
      // Spy on console.error before the action to prevent logging to the console.
      const consoleErrorSpy = spyOn(console, 'error');

      // Per testing guide 8.3, service is instantiated inside the run() callback.
      const service = TestBed.inject(ContractSearch);

      flush(); // Let initial call happen
      const initialReq = httpMock.expectOne('/api/v1/contracts/?page=1&size=20');

      initialReq.flush('Error', { status: 500, statusText: 'Server Error' });

      // Verify that the error was logged and the state was updated correctly.
      expect(consoleErrorSpy).toHaveBeenCalled();
      expect(service.error()).not.toBeNull();
      expect(service.data()).toBeNull();
      expect(service.loading()).toBe(false);
    });
  });
});
