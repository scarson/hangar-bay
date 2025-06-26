import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import {
  ActivatedRouteSnapshot,
  convertToParamMap,
  RouterStateSnapshot,
} from '@angular/router';
import { asapScheduler } from 'rxjs';

import { contractFilterResolver } from './contract-filter-resolver';
import { ContractSearch, SEARCH_SCHEDULER } from './contract-search';

describe('contractFilterResolver', () => {
  let mockContractSearch: jasmine.SpyObj<ContractSearch>;

  // Helper to execute the resolver in an injection context
  const executeResolver = (route: ActivatedRouteSnapshot): boolean => {
    let result!: boolean;
    TestBed.runInInjectionContext(() => {
      // The resolver is a plain function returning a boolean, not an Observable or Promise.
      result = contractFilterResolver(
        route,
        {} as RouterStateSnapshot
      ) as boolean;
    });
    return result;
  };

  beforeEach(() => {
    mockContractSearch = jasmine.createSpyObj('ContractSearch', [
      'setInitialFilters',
    ]);

    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ContractSearch, useValue: mockContractSearch },
        { provide: SEARCH_SCHEDULER, useValue: asapScheduler },
      ],
    });
  });

  it('should call setInitialFilters with default values when no query params are present', () => {
    const route = new ActivatedRouteSnapshot(); // Empty snapshot has no query params
    const result = executeResolver(route);

    expect(result).toBe(true);
    expect(mockContractSearch.setInitialFilters).toHaveBeenCalledWith({
      page: 1,
      size: 20,
      search: undefined,
      type: undefined,
    });
  });

  it('should call setInitialFilters with values from query params', () => {
    // Create a mock snapshot object with the desired queryParamMap
    const route = {
      queryParamMap: convertToParamMap({
        search: 'jita',
        page: '3',
        size: '50',
      }),
    } as ActivatedRouteSnapshot;

    const result = executeResolver(route);

    expect(result).toBe(true);
    expect(mockContractSearch.setInitialFilters).toHaveBeenCalledWith({
      page: 3,
      size: 50,
      search: 'jita',
      type: undefined,
    });
  });

  it('should handle invalid numeric query params gracefully', () => {
    const route = {
      queryParamMap: convertToParamMap({
        page: 'invalid',
        size: '-10', // Should be sanitized to default
      }),
    } as ActivatedRouteSnapshot;

    const result = executeResolver(route);

    expect(result).toBe(true);
    expect(mockContractSearch.setInitialFilters).toHaveBeenCalledWith({
      page: 1, // Falls back to default
      size: 20, // Falls back to default
      search: undefined,
      type: undefined,
    });
  });

  it('should call setInitialFilters with the type from query params', () => {
    const route = {
      queryParamMap: convertToParamMap({
        type: 'auction',
      }),
    } as ActivatedRouteSnapshot;

    const result = executeResolver(route);

    expect(result).toBe(true);
    expect(mockContractSearch.setInitialFilters).toHaveBeenCalledWith({
      page: 1,
      size: 20,
      search: undefined,
      type: 'auction',
    });
  });
});
