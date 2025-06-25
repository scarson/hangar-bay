import { TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import {
  HttpClientTestingModule,
  HttpTestingController,
} from '@angular/common/http/testing';
import { HttpRequest } from '@angular/common/http';

import { ContractApi } from './contract.api';
import {
  PaginatedShipContractsResponse,
  ShipContract,
} from './contract.model';
import { environment } from '../../../environments/environment';

describe('ContractApi', () => {
  let service: ContractApi;
  let httpTestingController: HttpTestingController;

  const mockContracts: ShipContract[] = [
    {
      contract_id: 1,
      ship_type_id: 101,
      ship_name: 'Test Ship 1',
      price: 1000,
      location_name: 'Jita',
      date_issued: new Date().toISOString(),
      title: 'Contract 1',
      is_blueprint_copy: false,
      quantity: 1,
      contains_additional_items: false,
    },
    {
      contract_id: 2,
      ship_type_id: 102,
      ship_name: 'Test Ship 2',
      price: 2000,
      location_name: 'Amarr',
      date_issued: new Date().toISOString(),
      title: 'Contract 2',
      is_blueprint_copy: true,
      quantity: 1,
      runs: 10,
      contains_additional_items: false,
    },
  ];

  const mockPaginatedResponse: PaginatedShipContractsResponse = {
    items: mockContracts,
    total_items: 2,
    total_pages: 1,
    page: 1,
    size: 20,
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [ContractApi, provideZonelessChangeDetection()],
    });

    service = TestBed.inject(ContractApi);
    httpTestingController = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTestingController.verify(); // Verify that no unmatched requests are outstanding.
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should have correct initial state', () => {
    const initialState = service.state();
    expect(initialState.contracts).toEqual([]);
    expect(initialState.loading).toBe(false);
    expect(initialState.error).toBeNull();
    expect(initialState.totalItems).toBe(0);
  });

  // Note: No fakeAsync or tick() needed for zoneless testing of HttpClient
  it('should fetch contracts and update state on success', () => {
    service.getContracts({ page: 1, size: 20 });

    // Check loading state immediately after call
    expect(service.state().loading).toBe(true);

    const req = httpTestingController.expectOne(
      `${environment.apiUrl}/api/v1/contracts/ships?page=1&size=20`
    );
    expect(req.request.method).toBe('GET');

    // Respond with mock data
    req.flush(mockPaginatedResponse);

    // Assert the final state
    const finalState = service.state();
    expect(finalState.loading).toBe(false);
    expect(finalState.contracts).toEqual(mockContracts);
    expect(finalState.totalItems).toBe(2);
    expect(finalState.error).toBeNull();
  });

  it('should handle API errors and update state accordingly', () => {
    const errorMessage = 'Internal Server Error';
    const status = 500;

    service.getContracts();

    expect(service.state().loading).toBe(true);

    const req = httpTestingController.expectOne(
      `${environment.apiUrl}/api/v1/contracts/ships`
    );
    req.flush(errorMessage, { status, statusText: errorMessage });

    const finalState = service.state();
    expect(finalState.loading).toBe(false);
    expect(finalState.contracts).toEqual([]); // Data should be empty
    expect(finalState.error).toBe(
      'Failed to load contracts. Please try again later.'
    );
  });

  it('should build correct HttpParams for given request params', () => {
    service.getContracts({ page: 2, ship_type_id: 123, region_id: 456 });

    const req = httpTestingController.expectOne(
      (request: HttpRequest<any>) =>
        request.url === `${environment.apiUrl}/api/v1/contracts/ships`
    );

    expect(req.request.params.get('page')).toBe('2');
    expect(req.request.params.get('ship_type_id')).toBe('123');
    expect(req.request.params.get('region_id')).toBe('456');
    expect(req.request.params.has('size')).toBe(false); // Should not be present if not provided

    req.flush(mockPaginatedResponse);
  });
});

