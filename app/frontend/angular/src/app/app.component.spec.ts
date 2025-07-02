import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { Component, provideZonelessChangeDetection, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideRouter, Router } from '@angular/router';

import { Location } from '@angular/common';
import { of } from 'rxjs';
import { AppComponent } from './app.component';
import { routes } from './app.routes';
import { Footer } from './shared/layout/footer/footer.component';
import { Header } from './shared/layout/header/header.component';
import { ContractApi } from './features/contracts/services/contract.api';
import { ContractSearch } from './features/contracts/services/contract-search.service';
import { contractFilterResolver } from './features/contracts/resolvers/contract-filter.resolver';

// Mock components to isolate AppComponent during testing
@Component({ selector: 'hgb-header', standalone: true, template: '' })
class MockHeaderComponent {}

@Component({ selector: 'hgb-footer', standalone: true, template: '' })
class MockFooterComponent {}


describe('AppComponent', () => {
  beforeEach(async () => {
    const mockContractSearch = jasmine.createSpyObj('ContractSearch', {
      updateFilters: undefined,
      setInitialFilters: undefined,
    });
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
      getContracts: () => of(undefined),
    };

    await TestBed.configureTestingModule({
      imports: [AppComponent, MockHeaderComponent, MockFooterComponent],
      providers: [
        provideZonelessChangeDetection(),
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter(routes),
        { provide: ContractApi, useValue: mockContractApi },
        { provide: ContractSearch, useValue: mockContractSearch },
        { provide: contractFilterResolver, useValue: () => of(true) },
      ],
    }).overrideComponent(AppComponent, {
        remove: { imports: [Header, Footer] },
        add: { imports: [MockHeaderComponent, MockFooterComponent] },
      })
      .compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should render the header component', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('hgb-header')).not.toBeNull();
  });

  it('should redirect empty path to /contracts when navigating to root', async () => {
    const router = TestBed.inject(Router);
    const location = TestBed.inject(Location);
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();

    await router.navigate(['']);
    await fixture.whenStable();

    expect(location.path()).toBe('/contracts');
  });

  it('should render the router outlet', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('router-outlet')).not.toBeNull();
  });

  it('should render the footer component', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('hgb-footer')).not.toBeNull();
  });

  it('should lazy load and render the ContractBrowsePage on navigation to /contracts', async () => {
    const router = TestBed.inject(Router);
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();

    await router.navigate(['/contracts']);
    await fixture.whenStable();
    fixture.detectChanges();

    const contractBrowsePage = fixture.debugElement.query(
      By.css('hgb-contract-browse-page')
    );
    expect(contractBrowsePage).not.toBeNull();
  });
});
