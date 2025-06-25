import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection, signal } from '@angular/core';
import { ContractBrowsePage } from './contract-browse-page';
import { ContractSearch } from '../contract-search';

describe('ContractBrowsePage', () => {
  let component: ContractBrowsePage;
  let fixture: ComponentFixture<ContractBrowsePage>;

  // Create a mock that matches the public interface of ContractSearch
  const mockContractSearch = {
    loading: signal(false),
    error: signal(null),
    data: signal(null),
    filters: signal({ page: 1, size: 20 }),
    updateFilters: () => {},
    setInitialFilters: () => {},
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ContractBrowsePage],
      providers: [
        provideZonelessChangeDetection(),
        { provide: ContractSearch, useValue: mockContractSearch },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ContractBrowsePage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
