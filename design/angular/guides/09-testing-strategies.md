## AI Analysis Guidance for Cascade

This file is over 200 lines long. Unless you are only looking for a specific section, you should read the entire file, which may require multiple tool calls.

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

### 5.4. Interacting with the DOM

-   `fixture.debugElement.query(By.css('.my-class'))` or `By.directive(MyDirective)`.
-   `nativeElement.click()`, `nativeElement.value = 'test'`, `nativeElement.dispatchEvent(new Event('input'))`.

### 5.5. Testing with Signals

-   **Inputs:** Set signal inputs directly in tests: `component.myInput.set(value);`
-   **State:** Read signal values: `expect(component.myStateSignal()).toBe(expectedValue);`
-   **Outputs:** Standard event emitter testing with `spyOn(component.myOutput, 'emit');`
-   **`computed` and `effect`:** Test the outcomes of computed signals or side effects triggered by effects. Ensure effects are cleaned up (`fixture.destroy()`).

## 6. Integration Testing

-   **Component Integration:** Testing how a parent component interacts with its child components, or how multiple services work together.
    -   `TestBed` is configured to include the actual child components (not mocks) to test their interaction.
-   These tests are more complex and slower than unit tests but provide higher confidence in component collaborations.

## 7. End-to-End (E2E) Testing

-   **Purpose:** Simulates real user scenarios by interacting with the application through the browser UI.
-   **Tools:** Cypress, Playwright, Protractor (deprecated for new Angular projects).
-   **Scope for Hangar Bay:** We will identify critical user flows (e.g., login, creating a hangar, viewing details) for E2E testing. These tests are the slowest and most brittle, so they should be used judiciously.
-   Angular CLI can set up E2E testing with tools like Cypress (`ng add @cypress/schematic`).

## 8. Code Coverage

-   Angular CLI generates code coverage reports (using Istanbul) when running tests with `ng test --coverage`.
-   The report is typically found in the `coverage/` directory.
-   **Goal:** Strive for a high percentage (e.g., >80%), but focus on testing critical paths and logic thoroughly rather than just chasing numbers.

## 9. Best Practices for Testable Code

-   **Single Responsibility Principle:** Components and services that do one thing well are easier to test.
-   **Dependency Injection:** Makes mocking dependencies straightforward.
-   **Avoid Logic in Constructors:** Keep constructors simple; move logic to lifecycle hooks or methods.
-   **Pure Functions/Methods:** Easier to test as they have no side effects.
-   **Clear Separation of Concerns:** UI logic in components, business logic in services.

By implementing these testing strategies, Hangar Bay will maintain a high level of quality and stability as it evolves.
