import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection, signal, WritableSignal } from '@angular/core';
import { ContractBrowsePage } from './contract-browse-page';
import { ContractSearch } from '../contract-search';
import { Contract, PaginatedContractsResponse } from '../contract.models';
import { Isk } from '../../../shared/pipes/isk';
import { TimeLeft } from '../../../shared/pipes/time-left';

// Helper to type the mock more strictly
type MockContractSearch = {
  loading: WritableSignal<boolean>;
  error: WritableSignal<string | null>;
  data: WritableSignal<PaginatedContractsResponse | null>;
  filters: WritableSignal<{ page: number; size: number; [key: string]: any }>;
  updateFilters: jasmine.Spy;
  setInitialFilters: jasmine.Spy;
};

describe('ContractBrowsePage', () => {
  let component: ContractBrowsePage;
  let fixture: ComponentFixture<ContractBrowsePage>;
  let mockSearchService: MockContractSearch;
  const baseTime = new Date();

  beforeEach(async () => {
    jasmine.clock().install();
    jasmine.clock().mockDate(baseTime);

    // Reset the mock for each test to ensure isolation
    mockSearchService = {
      loading: signal(false),
      error: signal(null),
      data: signal(null),
      filters: signal({ page: 1, size: 20 }),
      updateFilters: jasmine.createSpy('updateFilters'),
      setInitialFilters: jasmine.createSpy('setInitialFilters'),
    };

    await TestBed.configureTestingModule({
      // Since the component is standalone, we import it directly.
      // The pipes are also standalone and are dependencies of the component's template,
      // so they must also be imported.
      imports: [ContractBrowsePage, Isk, TimeLeft],
      providers: [
        provideZonelessChangeDetection(),
        { provide: ContractSearch, useValue: mockSearchService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ContractBrowsePage);
    component = fixture.componentInstance;
  });

  afterEach(() => {
    jasmine.clock().uninstall();
  });

  it('should create', () => {
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });

  it('should display the loading indicator when loading is true', () => {
    mockSearchService.loading.set(true);
    fixture.detectChanges();

    const loadingIndicator = fixture.nativeElement.querySelector('.loading-indicator');
    expect(loadingIndicator).toBeTruthy();
    expect(loadingIndicator.textContent).toContain('Loading contracts...');
  });

  it('should display an error message when an error is present', () => {
    const errorMessage = 'Failed to fetch contracts';
    mockSearchService.error.set(errorMessage);
    fixture.detectChanges();

    const errorElement = fixture.nativeElement.querySelector('.error-message');
    expect(errorElement).toBeTruthy();
    expect(errorElement.textContent).toContain(errorMessage);
  });

  it('should display the contract table when data is available', () => {
    const mockContract: Contract = {
      contract_id: 1,
      issuer_id: 123,
      issuer_corporation_id: 456,
      start_location_id: 789,
      type: 'item_exchange',
      status: 'outstanding',
      for_corporation: false,
      date_issued: new Date().toISOString(),
      date_expired: new Date(baseTime.getTime() + 86400000).toISOString(), // Exactly 1 day from mocked time
      items: [],
      is_ship_contract: false,
      issuer_name: 'Test Corp',
      start_location_name: 'Jita IV-4',
      price: 1000000,
    };
    const mockData: PaginatedContractsResponse = {
      items: [mockContract],
      total: 1,
      page: 1,
      size: 20,
    };
    mockSearchService.data.set(mockData);
    fixture.detectChanges();

    const table = fixture.nativeElement.querySelector('.contract-table');
    const rows = table.querySelectorAll('tbody tr');
    const firstRowCells = rows[0].querySelectorAll('td');

    expect(table).toBeTruthy();
    expect(rows.length).toBe(1);
    expect(firstRowCells[0].textContent).toContain('item_exchange');
    expect(firstRowCells[1].textContent).toContain('Test Corp');
    expect(firstRowCells[3].textContent).toContain('1M'); // IskPipe correctly formats 1,000,000 to '1M'
    expect(firstRowCells[4].textContent).toContain('1d 0h'); // TimeLeftPipe
  });

  it('should call updateFilters with the correct search term', () => {
    fixture.detectChanges(); // Initial render
    const searchInput = fixture.nativeElement.querySelector('input[type="text"]');
    searchInput.value = 'Vindicator';
    searchInput.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    expect(mockSearchService.updateFilters).toHaveBeenCalledWith({ search: 'Vindicator', page: 1 });
  });

  it('should call updateFilters with the correct page number on pagination change', () => {
    mockSearchService.data.set({ items: [], total: 50, page: 1, size: 20 });
    fixture.detectChanges();

    const nextButton = fixture.nativeElement.querySelector('.pagination-controls button:last-child');
    nextButton.click();
    fixture.detectChanges();

    expect(mockSearchService.updateFilters).toHaveBeenCalledWith({ page: 2 });
  });

  it('should call updateFilters with correct sort parameters when a sortable header is clicked', () => {
    // Set initial data to render the table and headers
    mockSearchService.data.set({ items: [], total: 1, page: 1, size: 20 });
    fixture.detectChanges();

    const sortableHeaders = fixture.nativeElement.querySelectorAll('button.sortable-header');
    const priceHeaderButton = sortableHeaders[0]; // First one is Price

    // First click: sort by price, ascending
    priceHeaderButton.click();
    fixture.detectChanges();

    expect(mockSearchService.updateFilters).toHaveBeenCalledWith({
      sort: 'price',
      order: 'asc',
      page: 1,
    });

    // Simulate the service updating the filter state for the next click
    mockSearchService.filters.set({ page: 1, size: 20, sort: 'price', order: 'asc' });
    fixture.detectChanges();

    // Second click: sort by price, descending
    priceHeaderButton.click();
    fixture.detectChanges();

    expect(mockSearchService.updateFilters).toHaveBeenCalledWith({
      sort: 'price',
      order: 'desc',
      page: 1,
    });
  });
});
