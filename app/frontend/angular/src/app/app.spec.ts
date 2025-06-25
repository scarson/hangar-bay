import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { Component, provideZonelessChangeDetection, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { Router } from '@angular/router';
import { RouterTestingModule } from '@angular/router/testing';
import { Location } from '@angular/common';
import { of } from 'rxjs';
import { App } from './app';
import { routes } from './app.routes';
import { Footer } from './core/layout/footer/footer';
import { Header } from './core/layout/header/header';
import { ContractApi } from './features/contracts/contract.api';
import { ContractSearch } from './features/contracts/contract-search';
import { ContractBrowsePage } from './features/contracts/contract-browse-page/contract-browse-page';

// Mock components to isolate AppComponent during testing
@Component({ selector: 'hgb-header', standalone: true, template: '' })
class MockHeaderComponent {}

@Component({ selector: 'hgb-footer', standalone: true, template: '' })
class MockFooterComponent {}

describe('App', () => {
  beforeEach(async () => {
    // Mock for the service dependency of the lazy-loaded component
    // This is a more robust mock for the ContractSearch service.
    // It prevents the real service's constructor from running and making HTTP calls.
    const mockContractSearch = jasmine.createSpyObj('ContractSearch', {
      updateFilters: undefined,
      setInitialFilters: undefined,
    });
    // Mock the public signals that components will bind to.
    mockContractSearch.loading = signal(false).asReadonly();
    mockContractSearch.error = signal(null).asReadonly();
    mockContractSearch.data = signal(null).asReadonly();
    mockContractSearch.filters = signal({ page: 1, size: 20 }).asReadonly();

    const mockContractApi = {
      state: signal({
        contracts: [],
        totalItems: 0,
        totalPages: 0,
        loading: false,
        error: null,
      }).asReadonly(),
      getContracts: () => of(undefined), // Return value is not critical for this test
    };

    await TestBed.configureTestingModule({
      imports: [
        App,
        RouterTestingModule.withRoutes(routes),
        MockHeaderComponent,
        MockFooterComponent,
      ],
      providers: [
        provideZonelessChangeDetection(),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ContractApi, useValue: mockContractApi },
        { provide: ContractSearch, useValue: mockContractSearch },
      ],
    })
      .overrideComponent(App, {
        remove: { imports: [Header, Footer] },
        add: { imports: [MockHeaderComponent, MockFooterComponent] },
      })
      .compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should render the header component', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('hgb-header')).not.toBeNull();
  });

  it('should redirect empty path to /home when navigating to root', async () => {
    const router = TestBed.inject(Router);
    const location = TestBed.inject(Location);
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges(); // Create component and initialize router

    // Explicitly navigate to the root path to test the redirect
    await router.navigate(['']);
    await fixture.whenStable(); // Wait for navigation and redirection to complete

    expect(location.path()).toBe('/contracts');
  });

  it('should render the router outlet', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('router-outlet')).not.toBeNull();
  });

  it('should render the footer component', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('hgb-footer')).not.toBeNull();
  });

  it('should lazy load and render the ContractListComponent on navigation to /contracts', async () => {
    const router = TestBed.inject(Router);
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges(); // Trigger initial navigation

    // Navigate to the contracts route
    await router.navigate(['/contracts']);
    await fixture.whenStable(); // Wait for lazy loading to complete
    fixture.detectChanges(); // Update the view with the new component

    // Verify the component is rendered
    const contractBrowsePage = fixture.debugElement.query(
      By.css('hgb-contract-browse-page')
    );
    expect(contractBrowsePage).not.toBeNull();
  });
});
