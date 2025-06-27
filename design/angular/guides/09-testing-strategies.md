## AI Analysis Guidance for Cascade

This file is over 400 lines long. Unless you are only looking for a specific section, you should read the entire file, which may require multiple tool calls.

# Angular Testing Strategies (Hangar Bay)

**Last Updated:** 2025-06-09

## 1. Introduction

Comprehensive testing is vital for building robust, maintainable, and reliable applications. For Hangar Bay, we will adopt a multi-layered testing strategy, focusing primarily on unit and component (shallow integration) tests, with considerations for broader integration and End-to-End (E2E) tests.

This document outlines our approach to testing Angular components, services, pipes, and directives, leveraging Angular's testing utilities, Jasmine as the testing framework, and Karma as the test runner (defaults provided by Angular CLI).

Referenced from: Angular Docs, `llms-full.txt` (positions 43-47), `../angular-frontend-architecture.md` (Section 2.9).

## 2. Testing Philosophy & Goals

-   **Test Pyramid:** Focus heavily on unit tests (fast, isolated), a good number of component/integration tests (verifying interactions), and a smaller, selective set of E2E tests (verifying user flows).
-   **Confidence:** Tests should provide high confidence that the application works as expected.
-   **Maintainability:** Tests should be easy to write, read, and maintain.
-   **Speed:** Test suites should run quickly to encourage frequent execution.
-   **Code Coverage:** Aim for high code coverage (e.g., >80%) for critical business logic and components, but prioritize quality of tests over raw percentage.

## 3. Tools and Frameworks

-   **Jasmine:** Default testing framework for Angular. Provides functions like `describe`, `it`, `expect`, `beforeEach`, `afterEach`, spies (`spyOn`).
-   **Karma:** Default test runner. Executes tests in a browser environment.
-   **Angular `TestBed`:** Core Angular testing utility for configuring testing modules, creating components, and managing dependencies for tests.
-   **`HttpClientTestingModule`:** For mocking HTTP requests in service and component tests.
-   **Standalone Component Testing:** Modern Angular testing focuses on testing standalone components with minimal `TestBed` configuration by providing necessary dependencies directly.

## 4. Unit Testing

Unit tests focus on testing individual, isolated pieces of code (e.g., a single method in a service, a pipe's transformation logic).

### 4.1. Testing Services

-   Services often contain business logic and data manipulation.
-   Mock dependencies (like `HttpClient` or other services) to isolate the unit under test.

```typescript
// data.service.ts (example)
import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { User } from './user.model';

@Injectable({ providedIn: 'root' })
export class DataService {
  private http = inject(HttpClient);
  private apiUrl = '/api/users';

  getUsers(): Observable<User[]> {
    return this.http.get<User[]>(this.apiUrl);
  }

  getUserById(id: string): Observable<User | undefined> {
    if (!id) return of(undefined);
    return this.http.get<User>(`${this.apiUrl}/${id}`);
  }
}

// data.service.spec.ts
import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { DataService } from './data.service';
import { User } from './user.model';

describe('DataService', () => {
  let service: DataService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [DataService]
    });
    service = TestBed.inject(DataService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify(); // Ensure no outstanding HTTP requests
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should retrieve users via GET', () => {
    const mockUsers: User[] = [{ id: '1', name: 'Test User' }];
    service.getUsers().subscribe(users => {
      expect(users.length).toBe(1);
      expect(users).toEqual(mockUsers);
    });

    const req = httpMock.expectOne('/api/users');
    expect(req.request.method).toBe('GET');
    req.flush(mockUsers);
  });

  it('should return undefined if getUserById is called with no id', (done) => {
    service.getUserById('').subscribe(user => {
      expect(user).toBeUndefined();
      done(); // For async tests not using Angular's async utilities
    });
  });
});
```

### 4.2. Testing Pipes

-   Pipes are simple functions; instantiate them and test their `transform` method.

```typescript
// my-custom.pipe.ts
import { Pipe, PipeTransform } from '@angular/core';

@Pipe({ name: 'myCustom', standalone: true })
export class MyCustomPipe implements PipeTransform {
  transform(value: string, suffix: string = '!'): string {
    return `${value.toUpperCase()}${suffix}`;
  }
}

// my-custom.pipe.spec.ts
import { MyCustomPipe } from './my-custom.pipe';

describe('MyCustomPipe', () => {
  let pipe: MyCustomPipe;

  beforeEach(() => {
    pipe = new MyCustomPipe();
  });

  it('create an instance', () => {
    expect(pipe).toBeTruthy();
  });

  it('should transform input to uppercase with default suffix', () => {
    expect(pipe.transform('hello')).toBe('HELLO!');
  });

  it('should transform input with provided suffix', () => {
    expect(pipe.transform('world', '...')).toBe('WORLD...');
  });
});
```

## 5. Component Testing

Component tests verify the component's behavior, its template, and its interaction with dependencies and users.

### 5.1. `TestBed` Configuration for Components

-   `TestBed.configureTestingModule({})`: Used to set up a testing environment similar to an Angular module.
-   For **standalone components**, you typically provide dependencies directly or import other standalone components/pipes/directives if needed.
-   `TestBed.createComponent(MyComponent)`: Creates an instance of the component.
-   `fixture.detectChanges()`: Triggers change detection.
-   `fixture.nativeElement`: Access to the component's root DOM element.
-   `fixture.debugElement`: Wrapper around `nativeElement` with more Angular-specific utilities.

### 5.2. Testing Standalone Components

```typescript
// user-profile.component.ts (simplified example)
import { Component, input, output, signal } from '@angular/core';
import { CommonModule } from '@angular/common'; // For *ngIf, etc.

@Component({
  selector: 'hb-user-profile',
  standalone: true,
  imports: [CommonModule],
  template: `
    @if (user()) {
      <h2>{{ user()?.name }}</h2>
      <p>ID: {{ user()?.id }}</p>
      <button (click)="edit.emit(user()?.id)">Edit</button>
    } @else {
      <p>No user selected.</p>
    }
  `
})
export class UserProfileComponent {
  user = input<{ id: string; name: string } | null>(null);
  edit = output<string>();
}

// user-profile.component.spec.ts
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { UserProfileComponent } from './user-profile.component';
import { By } from '@angular/platform-browser'; // For querying DOM elements

describe('UserProfileComponent', () => {
  let component: UserProfileComponent;
  let fixture: ComponentFixture<UserProfileComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UserProfileComponent] // Import the standalone component
      // No 'declarations' needed for standalone components
      // Provide mock services here if needed: providers: [{ provide: MyService, useClass: MockMyService }]
    }).compileComponents(); // compileComponents is usually not needed for standalone with Vite/esbuild

    fixture = TestBed.createComponent(UserProfileComponent);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should display user name and id when user input is provided', () => {
    const testUser = { id: '123', name: 'Jane Doe' };
    component.user.set(testUser); // Set signal input
    fixture.detectChanges();

    const nameEl = fixture.debugElement.query(By.css('h2')).nativeElement;
    const idEl = fixture.debugElement.query(By.css('p')).nativeElement;
    expect(nameEl.textContent).toContain('Jane Doe');
    expect(idEl.textContent).toContain('ID: 123');
  });

  it('should display "No user selected." when user input is null', () => {
    component.user.set(null);
    fixture.detectChanges();

    const pEl = fixture.debugElement.query(By.css('p')).nativeElement;
    expect(pEl.textContent).toContain('No user selected.');
  });

  it('should emit edit event with user id when edit button is clicked', () => {
    const testUser = { id: '123', name: 'Jane Doe' };
    spyOn(component.edit, 'emit');
    component.user.set(testUser);
    fixture.detectChanges();

    const editButton = fixture.debugElement.query(By.css('button')).nativeElement;
    editButton.click();

    expect(component.edit.emit).toHaveBeenCalledWith('123');
  });
});
```

### 5.3. Mocking Dependencies

-   **Services:** Provide mock implementations using `useClass`, `useValue`, or `useFactory` in `TestBed.configureTestingModule`.
    ```typescript
    // Example: Mocking a service
    class MockAuthService {
      isLoggedInSignal = signal(true);
      login() { /* ... */ }
    }
    // ... in TestBed.configureTestingModule
    // providers: [{ provide: AuthService, useClass: MockAuthService }]
    ```
-   **Child Components:** For shallow component tests (testing only the component itself, not its children), you can use `NO_ERRORS_SCHEMA` (discouraged as it hides template errors) or provide stub/mock components.
    - For standalone components, if a child is also standalone, you can import a mock version of it.

### 5.4. Interacting with the DOM & Component State

-   **Querying Elements:** Use `fixture.debugElement.query(By.css('.my-class'))` or `By.directive(MyDirective)`.
-   **Triggering Events:**
    -   For simple clicks: `element.nativeElement.click()`.
    -   For text inputs: `inputEl.nativeElement.value = 'test'; inputEl.nativeElement.dispatchEvent(new Event('input'));`.
    -   For `<select>` dropdowns:
        ```typescript
        const selectEl = fixture.debugElement.query(By.css('select')).nativeElement;
        selectEl.value = 'option-value'; // Set the value of the <option>
        selectEl.dispatchEvent(new Event('change'));
        fixture.detectChanges();
        ```
-   **Asserting Component State (CSS Classes):** Check for the presence of CSS classes to verify state-driven styling.
    ```typescript
    const element = fixture.debugElement.query(By.css('.my-element'));
    expect(element.classes['my-active-class']).toBeTrue();
    ```

### 5.5. Testing with Signals

-   **Inputs:** Set signal inputs directly in tests: `component.myInput.set(value);`
-   **State:** Read signal values: `expect(component.myStateSignal()).toBe(expectedValue);`
-   **Outputs:** Standard event emitter testing with `spyOn(component.myOutput, 'emit');`
-   **`computed` and `effect`:** Test the outcomes of computed signals or side effects triggered by effects. Ensure effects are cleaned up (`fixture.destroy()`).

## 6. Testing Routing

Testing the application's routing configuration is crucial for ensuring users can navigate as expected. Key scenarios include default route redirection, route guards, and lazy-loaded components.

### 6.1. Testing Default Route Redirection (Zoneless)

A common requirement is to redirect the default empty path (`''`) to a specific route. You can test this behavior using the `RouterTestingModule` and `async/await` syntax, which is compatible with our zoneless architecture.

**Key Tools:**
-   `RouterTestingModule.withRoutes(routes)`: Configures the testing module with your application's routes.
-   `Router`: The Angular router service, used to trigger navigation.
-   `Location`: An Angular service that allows you to inspect the browser's URL.
-   `fixture.whenStable()`: Returns a promise that resolves when asynchronous tasks like navigation are complete.

**Example (`app.spec.ts`):**

This test verifies that the application correctly redirects from the root path to `/home`. Note the use of `async` and `await fixture.whenStable()` instead of `fakeAsync/tick`.

```typescript
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { RouterTestingModule } from '@angular/router/testing';
import { Location } from '@angular/common';
import { routes } from './app.routes';
import { App } from './app';
import { Component } from '@angular/core';

// Create a mock component for the route to avoid importing the real one
@Component({ selector: 'hgb-home', standalone: true, template: '' })
class MockHomeComponent {}

describe('App Routing', () => {
  let location: Location;
  let fixture: ComponentFixture<App>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [
        RouterTestingModule.withRoutes(routes),
        App, // The root component
        MockHomeComponent, // Provide the mock for the '/home' route
      ],
    }).compileComponents();

    const router = TestBed.inject(Router);
    location = TestBed.inject(Location);
    fixture = TestBed.createComponent(App);
    
    // Initial navigation is triggered by RouterTestingModule. Wait for it to complete.
    await fixture.whenStable();
  });

  it('should redirect empty path to /home on initial navigation', () => {
    // The redirection has already happened in beforeEach after `whenStable()`
    expect(location.path()).toBe('/home');
  });
});
```

### 6.2. Testing Route Resolvers

Resolvers pre-fetch data before a route is activated. Testing them involves mocking their dependencies (like services) and verifying they return the correct data or perform the correct actions.

**Key Tools:**
-   `ActivatedRouteSnapshot`: A mock `ActivatedRouteSnapshot` can be created to provide query parameters or route parameters to the resolver.
-   `TestBed`: Used to provide the resolver and its mocked dependencies.

**Example (`contract-filter-resolver.spec.ts`):**

This test verifies that the resolver correctly calls a service method with parameters from the route's query params.

```typescript
import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot } from '@angular/router';
import { ContractSearch } from '../services/contract-search';
import { contractFilterResolver } from './contract-filter-resolver';

describe('contractFilterResolver', () => {
  let contractSearchSpy: jasmine.SpyObj<ContractSearch>;

  beforeEach(() => {
    const spy = jasmine.createSpyObj('ContractSearch', ['setInitialFilters']);

    TestBed.configureTestingModule({
      providers: [
        { provide: ContractSearch, useValue: spy }
      ]
    });
    contractSearchSpy = TestBed.inject(ContractSearch) as jasmine.SpyObj<ContractSearch>;
  });

  it('should parse query params and call setInitialFilters', () => {
    const route = new ActivatedRouteSnapshot();
    route.queryParams = { page: '2', type: 'auction' };

    // Execute the resolver function
    TestBed.runInInjectionContext(() => contractFilterResolver(route, {} as any));

    expect(contractSearchSpy.setInitialFilters).toHaveBeenCalledWith({
      page: 2,
      size: 50, // default
      search: '', // default
      type: 'auction'
    });
  });
});
```
});
```

## 7. Integration Testing

-   **Component Integration:** Testing how a parent component interacts with its child components, or how multiple services work together.
    -   `TestBed` is configured to include the actual child components (not mocks) to test their interaction.
-   These tests are more complex and slower than unit tests but provide higher confidence in component collaborations.

## 8. Zoneless Testing: Core Principles & Advanced Scenarios

**CRITICAL:** Our Hangar Bay Angular application is configured to be **zoneless**. This has a direct and important impact on how we write asynchronous tests.

### 8.1. Core Principles: `async/await` vs. `fakeAsync`

*   The Angular testing utilities `fakeAsync`, `tick()`, and `waitForAsync` **are fundamentally dependent on `zone.js`** to function.
*   **DO NOT USE** `fakeAsync`, `tick()`, or `waitForAsync` in this project. Their use will lead to errors and contradicts our core architecture.
*   **Correct Approach for Async Tests:**
    *   For tests involving `HttpClientTestingModule`, no special async utilities are needed. The `HttpTestingController`'s `.flush()` method makes the corresponding `subscribe` or `toPromise` block execute synchronously within the test's scope.
    *   For other asynchronous operations (e.g., those involving `setTimeout`, router navigation, or other promises), use standard JavaScript `async/await` with `fixture.whenStable()`.

### 8.2. Advanced Scenario: Testing RxJS `debounceTime` with `TestScheduler`

*   **The Problem:** Tests for services using `debounceTime` would fail, with the `HttpTestingController` reporting "Expected one matching request... found none." The asynchronous pipeline was not executing within the test's virtual time.
*   **The Root Cause:** A fundamental incompatibility exists between Angular's `toObservable` interop function and the RxJS `TestScheduler` in a zoneless environment. `toObservable` does not reliably schedule its emissions on the virtual scheduler, even when using operators like `subscribeOn`.
*   **The Solution:** Avoid `toObservable` when testing with `TestScheduler`. Refactor the service to use a standard RxJS `Subject` as the trigger for the reactive pipeline.

    *   **Service Implementation:**
        ```typescript
        // contract-search.ts
        export class ContractSearch {
          // ...
          private filterTrigger$ = new Subject<void>();

          constructor() {
            this.filterTrigger$.pipe(
              startWith(undefined), // For initial data fetch
              debounceTime(300, this.scheduler),
              // ... other operators
            ).subscribe(/* ... */);
          }

          updateFilters(newFilters: Partial<ContractSearchFilters>): void {
            this.#filters.update((current) => ({ ...current, ...newFilters }));
            this.filterTrigger$.next(); // Manually trigger the pipeline
          }
        }
        ```
    *   **Test Implementation:** The test can now reliably control the service by calling `updateFilters()` and advancing the `TestScheduler`.

*   **Cascade's Rule:** When testing a service that uses RxJS time-based operators (`debounceTime`, `throttleTime`, etc.) in this zoneless project, **DO NOT** use `toObservable` to trigger the pipeline. **ALWAYS** use a `Subject`-based pattern.

### 8.3. Advanced Scenario: Correctly Instantiating Services in `TestScheduler` Tests

*   **The Problem:** Even with a `Subject`-based pipeline, tests can fail if the service under test is not instantiated correctly.
*   **The Root Cause:** For `TestScheduler` to have full control, the service's constructor (where the RxJS pipeline is defined and subscribed to) must be executed *within* the `testScheduler.run()` callback. Instantiating it in a `beforeEach` block places it outside the scheduler's virtual time context.
*   **The Solution:** Inject dependencies in `beforeEach`, but instantiate the service itself inside each `testScheduler.run()` block.

    ```typescript
    // contract-search.spec.ts
    describe('ContractSearch with TestScheduler', () => {
      let httpMock: HttpTestingController;
      let testScheduler: TestScheduler;

      beforeEach(() => {
        // ... TestBed configuration ...
        httpMock = TestBed.inject(HttpTestingController);
        testScheduler = new TestScheduler(/* ... */);
      });

      it('should fetch initial data', () => {
        testScheduler.run(({ expectObservable }) => {
          // Instantiate the service HERE
          const service = TestBed.inject(ContractSearch);
          // ... test logic ...
        });
      });
    });
    ```

*   **Cascade's Rule:** For any test using `TestScheduler`, **ALWAYS** instantiate the service being tested inside the `testScheduler.run()` callback, not in `beforeEach`.

### 8.4. Advanced Scenario: Debugging "Phantom" HTTP 500 Errors in Tests

*   **The Problem:** Tests were failing with HTTP 500 Internal Server Errors, even though the backend server wasn't running.
*   **The Root Cause:** The `HttpTestingController` was correctly intercepting a request to an invalid URL (e.g., `/api/contracts/ships` instead of `/api/contracts/`). Because no mock was set up for this incorrect URL, the testing backend correctly returned an error. This error manifested as a 500, masking the true "Not Found" nature of the problem.
*   **The Solution:** When encountering an unexpected HTTP error in a test, the first step is to meticulously verify the URL being requested in the service against the URL expected in the test's `httpMock.expectOne()` call. They must match exactly.

*   **Cascade's Rule:** If a test fails with an unexpected HTTP error, **ALWAYS** first validate that the request URL in the service code perfectly matches the URL being expected by the `HttpTestingController`.

### 8.5. Advanced Scenario: Preventing Data Model Mismatches

*   **The Problem:** A linting error (`Property 'faction' does not exist...`) was introduced because the service code was referencing a property that had been removed from the `ContractSearchFilters` interface.
*   **The Root Cause:** Working from a stale or incorrect understanding of the current data model.
*   **The Solution:** Before writing code that interacts with a specific data model or interface, always verify its current definition. A quick `grep_search` or `view_file` can prevent this entire class of errors.

*   **Cascade's Rule:** Before implementing logic that depends on a specific data interface, **ALWAYS** first view the interface definition to ensure all property access is valid.

## 9. End-to-End (E2E) Testing

-   **Purpose:** Simulates real user scenarios by interacting with the application through the browser UI.
-   **Tools:** Cypress, Playwright, Protractor (deprecated for new Angular projects).
-   **Scope for Hangar Bay:** We will identify critical user flows (e.g., login, creating a hangar, viewing details) for E2E testing. These tests are the slowest and most brittle, so they should be used judiciously.
-   Angular CLI can set up E2E testing with tools like Cypress (`ng add @cypress/schematic`).

## 10. Code Coverage

-   Angular CLI generates code coverage reports (using Istanbul) when running tests with `ng test --coverage`.
-   The report is typically found in the `coverage/` directory.
-   **Goal:** Strive for a high percentage (e.g., >80%), but focus on testing critical paths and logic thoroughly rather than just chasing numbers.

## 11. Best Practices for Testable Code

### 11.1. Writing Testable Application Code

-   **Single Responsibility Principle:** Components and services that do one thing well are easier to test.
-   **Dependency Injection:** Makes mocking dependencies straightforward.
-   **Avoid Logic in Constructors:** Keep constructors simple; move logic to lifecycle hooks or methods.
-   **Pure Functions/Methods:** Easier to test as they have no side effects.
-   **Clear Separation of Concerns:** UI logic in components, business logic in services.

### 11.2. Writing Effective & Robust Specs (`.spec.ts` files)

-   **Every Spec Must Have an Expectation:** An `it(...)` block without at least one `expect(...)` call is not a valid test. It will pass regardless of the code's behavior, giving a false sense of security. Karma will produce a warning for such specs, which must be addressed.
-   **Verify No Outstanding HTTP Requests:** When using `HttpClientTestingModule`, always include an `afterEach` block to verify that no unexpected HTTP requests were made. This ensures tests are clean and do not interfere with one another.
    ```typescript
    afterEach(() => {
      httpMock.verify(); // Fails the test if any requests were made but not handled.
    });
    ```

By implementing these testing strategies, Hangar Bay will maintain a high level of quality and stability as it evolves.
