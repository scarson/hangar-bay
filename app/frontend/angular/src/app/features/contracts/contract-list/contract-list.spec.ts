import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection, signal } from '@angular/core';
import { of } from 'rxjs';

import { ContractList } from './contract-list';
import { ContractApi, ContractApiState } from '../contract.api';

// Mock ContractApi service
class MockContractApi {
  // Use a writable signal for testing purposes
  private readonly _state = signal<ContractApiState>({
    contracts: [],
    totalItems: 0,
    totalPages: 0,
    loading: true,
    error: null,
  });

  // Expose the readonly signal as the public API
  public readonly state = this._state.asReadonly();

  // Method to update the mock state for different test scenarios
  setState(newState: Partial<ContractApiState>) {
    this._state.update(current => ({ ...current, ...newState }));
  }

  // Spy on this method to ensure it's called
  getContracts = jasmine.createSpy('getContracts');
}

describe('ContractList', () => {
  let component: ContractList;
  let fixture: ComponentFixture<ContractList>;
  let mockContractApi: MockContractApi;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ContractList],
      providers: [
        provideZonelessChangeDetection(),
        { provide: ContractApi, useClass: MockContractApi },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ContractList);
    component = fixture.componentInstance;
    mockContractApi = TestBed.inject(ContractApi) as unknown as MockContractApi;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should call getContracts on initialization', () => {
    // ngOnInit is called automatically by detectChanges in the first test run
    fixture.detectChanges();
    expect(mockContractApi.getContracts).toHaveBeenCalledWith({ page: 1, size: 10 });
  });

  it('should display loading state initially', () => {
    mockContractApi.setState({ loading: true });
    fixture.detectChanges();
    const loadingEl = fixture.nativeElement.querySelector('.loading-shade');
    expect(loadingEl).toBeTruthy();
    expect(loadingEl.textContent).toContain('Loading contracts...');
  });

  it('should display contracts when data is loaded', () => {
    const mockContracts = [{ ship_name: 'Test Ship' }];
    mockContractApi.setState({ loading: false, contracts: mockContracts as any, totalPages: 1 });
    fixture.detectChanges();

    const tableRows = fixture.nativeElement.querySelectorAll('tbody tr');
    expect(tableRows.length).toBe(1);
    expect(fixture.nativeElement.querySelector('td').textContent).toContain('Test Ship');
  });

  it('should display empty state when no contracts are available', () => {
    mockContractApi.setState({ loading: false, contracts: [], totalPages: 0 });
    fixture.detectChanges();

    const emptyStateEl = fixture.nativeElement.querySelector('.empty-state');
    expect(emptyStateEl).toBeTruthy();
    expect(emptyStateEl.textContent).toContain('No ship contracts found.');
  });

  it('should display error state when an error occurs', () => {
    mockContractApi.setState({ loading: false, error: 'Test Error' });
    fixture.detectChanges();

    const errorEl = fixture.nativeElement.querySelector('.error-message');
    expect(errorEl).toBeTruthy();
    expect(errorEl.textContent).toContain('Test Error');
  });

  it('should call getContracts when page is changed', () => {
    mockContractApi.setState({ totalPages: 5 });
    fixture.detectChanges();

    component.onPageChange(2);
    expect(mockContractApi.getContracts).toHaveBeenCalledWith({ page: 2, size: 10 });
  });

  it('should not allow changing to a page less than 1', () => {
    mockContractApi.setState({ totalPages: 5 });
    fixture.detectChanges();
    mockContractApi.getContracts.calls.reset(); // Reset spy after ngOnInit call

    component.onPageChange(0);
    expect(mockContractApi.getContracts).not.toHaveBeenCalled();
  });
});
