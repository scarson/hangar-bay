# Angular Frontend Architecture Guidelines

**Last Updated:** 2025-06-08

## 1. Overview

This document outlines the architectural conventions and best practices for the Hangar Bay Angular frontend application. Adhering to these guidelines will help maintain a clean, scalable, performant, and maintainable codebase.

## 2. Module Organization

The application is structured using Angular NgModules. The primary types of modules and their roles are:

### 2.1. `AppModule` (Root Module)

*   **Location:** `src/app/app.module.ts`
*   **Purpose:** The root module that bootstraps the application.
*   **Responsibilities:**
    *   Imports `BrowserModule` (only once in the app).
    *   Imports `AppRoutingModule`.
    *   Imports `CoreModule` (only once).
    *   Declares the root `AppComponent`.
*   **Do's:** Keep `AppModule` lean. Its primary role is to assemble the application.
*   **Don'ts:** Do not declare or provide application-level services or shared components here directly. Delegate to `CoreModule` or `SharedModule`.

### 2.2. `CoreModule`

*   **Location:** `src/app/core/core.module.ts`
*   **Purpose:** To provide application-wide singleton services and declare/export components used *once* in the application shell (e.g., main header, main footer, main navigation).
*   **Responsibilities:**
    *   Provides singleton services (e.g., `AuthService`, `ApiService`, `LoggingService`). Services should prefer `providedIn: 'root'` for tree-shakability, but can also be listed in `CoreModule`'s `providers` array.
    *   Declares and exports components that are part of the main application layout and used only once (e.g., `HgbHeaderComponent`, `HgbFooterComponent`).
    *   Imports `HttpClientModule` and other modules whose services need to be singletons.
    *   Includes an import guard to prevent it from being imported into any module other than `AppModule`.
*   **Do's:**
    *   Import into `AppModule` only.
    *   Place services here that need to be singletons across the entire application if not using `providedIn: 'root'`.
*   **Don'ts:**
    *   **CRITICAL: NEVER import `CoreModule` into any Feature Module or `SharedModule`.**
    *   Do not declare components, directives, or pipes here that are intended for reuse across multiple feature modules. Use a `SharedModule` for that.

### 2.3. `SharedModule(s)`

*   **Location:** `src/app/shared/shared.module.ts` (and potentially more specific shared modules like `SharedUiComponentsModule`, `SharedPipesModule` if complexity grows).
*   **Purpose:** To consolidate reusable components, directives, and pipes that are used across multiple feature modules.
*   **Responsibilities:**
    *   Declares and exports commonly used UI components (e.g., custom buttons, modals, form controls, data tables).
    *   Declares and exports common directives and pipes.
    *   Imports and re-exports common Angular utility modules like `CommonModule`, `FormsModule`, `ReactiveFormsModule` if these are frequently needed by components declared in `SharedModule`.
*   **Do's:**
    *   Import `SharedModule` into any Feature Module that needs its declared/exported artifacts.
    *   Keep `SharedModule` focused on genuinely reusable, presentation-agnostic elements.
*   **Don'ts:**
    *   Do not provide services here. Services should typically be provided in `CoreModule` (for singletons using `providers` array) or using `providedIn: 'root'`, or at the component/feature module level if scoped.
    *   Do not import `CoreModule` here.

### 2.4. Feature Modules

*   **Location:** Typically `src/app/features/[feature-name]/[feature-name].module.ts` (e.g., `src/app/features/contracts/contracts.module.ts`).
*   **Purpose:** To organize code related to a specific business feature or domain (e.g., contract browsing, ship management).
*   **Responsibilities:**
    *   Declares components, directives, and pipes specific to the feature.
    *   Provides services scoped to the feature if not application-wide singletons.
    *   Defines feature-specific routing in a `[FeatureName]RoutingModule`.
    *   Imports `SharedModule` if it needs reusable elements.
    *   **Should be lazy-loaded by default** to improve initial application load time.
*   **Do's:**
    *   Encapsulate all assets related to a distinct feature.
    *   Implement lazy loading for all feature modules.
*   **Don'ts:**
    *   Do not import `CoreModule`.
    *   Avoid tight coupling with other feature modules directly; communicate via services or routing events if necessary.

## 3. Component Design & Implementation

### 3.1. Single Responsibility Principle (SRP)
*   Components should be small and focused on a single responsibility, primarily related to presentation logic.
*   Delegate complex business logic, data fetching, or state manipulation to services.

### 3.2. Smart vs. Dumb Components (Container/Presentational Pattern)
*   **Smart Components (Containers):**
    *   Concerned with *how things work*.
    *   Manage data, state, and interactions with services.
    *   Pass data down to presentational components via `@Input()`.
    *   Handle events emitted from presentational components via `@Output()`.
    *   Typically feature-specific and not highly reusable.
*   **Dumb Components (Presentational):**
    *   Concerned with *how things look*.
    *   Receive data via `@Input()` and display it.
    *   Emit events via `@Output()` when user interactions occur.
    *   Have no direct dependencies on services or application state (beyond their inputs).
    *   Highly reusable across the application.
    *   Should use `ChangeDetectionStrategy.OnPush`.

### 3.3. Change Detection Strategy
*   **Prefer `ChangeDetectionStrategy.OnPush`** for all components, especially presentational (dumb) components.
*   This strategy tells Angular to run change detection for the component only when its `@Input()` properties change, an event it emits is handled, or an `Observable` it subscribes to (via `async` pipe) emits a new value.
*   Significantly improves performance by reducing the number of change detection cycles.

### 3.4. Avoid Logic in Templates
*   Keep templates declarative and simple.
*   Avoid complex expressions, calculations, or function calls directly in the template (`{{ }}` or `*ngIf="someFunction()"`).
*   Move such logic into the component class (e.g., as properties or methods) and bind to the results in the template.
*   **Bad:** `<div *ngIf="items.filter(i => i.active).length > 0">...</div>`
*   **Good:** (In component: `hasActiveItems = this.items.some(i => i.active);`) `<div *ngIf="hasActiveItems">...</div>`

### 3.5. Lifecycle Hooks
*   Use Angular lifecycle hooks (`ngOnInit`, `ngOnChanges`, `ngOnDestroy`, etc.) for their intended purposes.
*   `ngOnInit`: For component initialization logic (e.g., initial data fetching).
*   `ngOnChanges`: To react to changes in `@Input()` properties.
*   `ngOnDestroy`: For cleanup logic (e.g., unsubscribing from Observables, detaching event listeners).

### 3.6. Standalone Components
*   Introduced in Angular 14 and refined further, standalone components, directives, and pipes do not need to be declared in an `NgModule`.
*   They directly manage their own template dependencies (other components, directives, pipes) via an `imports` array in their decorator.
*   Consider using standalone components for: 
    *   Simple, highly reusable UI elements.
    *   Reducing NgModule boilerplate, especially in libraries or for micro-frontend architectures.
    *   Facilitating easier lazy loading of individual components.
*   For Hangar Bay, while NgModules are the primary organizational structure, standalone components can be adopted where they offer clear benefits for simplicity and reusability.

## 4. Service Design & Implementation

### 4.1. Single Responsibility Principle (SRP)
*   Services should have a single, well-defined responsibility (e.g., `ContractApiService` for contract API interactions, `NotificationService` for user notifications).
*   Avoid creating monolithic services that handle too many unrelated concerns.

### 4.2. Immutability
*   When services manage or return data (especially objects or arrays) that might be shared or cached, strive for immutability.
*   Return new instances or copies of data rather than mutating existing objects/arrays directly. This helps prevent unintended side effects and makes change detection more predictable.
*   Libraries like Immer can assist, or use spread operators (`...`) and array methods (`.map()`, `.filter()`) to create new instances.

### 4.3. Error Handling
*   Implement robust error handling in services, particularly those interacting with external APIs or performing critical operations.
*   Use RxJS `catchError` operator to handle errors within Observable streams gracefully.
*   Provide meaningful error information that can be used by components to inform the user or trigger recovery actions.

## 5. RxJS Best Practices

Angular heavily relies on RxJS for asynchronous operations. Adhering to RxJS best practices is crucial for a reactive, performant, and maintainable application.

### 5.1. Unsubscribe from Observables
*   Memory leaks can occur if subscriptions to Observables are not managed correctly.
*   **`async` Pipe:** Prefer using the `async` pipe in component templates. It automatically subscribes to an Observable and unsubscribes when the component is destroyed.
    *   Example: `<div>{{ user$ | async }}</div>`
*   **`takeUntil` Pattern:** For manual subscriptions in component TypeScript code (e.g., in `ngOnInit`), use the `takeUntil` operator with a Subject that emits in `ngOnDestroy`.
    ```typescript
    private destroy$ = new Subject<void>();

    ngOnInit() {
      this.someService.getData()
        .pipe(takeUntil(this.destroy$))
        .subscribe(data => { /* ... */ });
    }

    ngOnDestroy() {
      this.destroy$.next();
      this.destroy$.complete();
    }
    ```
*   Avoid manual `unsubscribe()` calls where possible, as they can be error-prone if not managed carefully across multiple subscriptions.

### 5.2. Avoid Logic in `subscribe()`
*   Keep `subscribe()` blocks minimal. Their primary role should be to trigger the Observable stream or perform final side effects (like assigning data to a component property or calling a method).
*   Use pipeable operators (`map`, `filter`, `tap`, `switchMap`, etc.) to perform data transformations, filtering, and side effects *within* the Observable pipe.

### 5.3. Higher-Order Mapping Operators
*   To manage asynchronous operations that depend on the results of previous Observables (e.g., making a second API call based on the result of a first), use higher-order mapping operators to avoid nested subscriptions ("callback hell"):
    *   `switchMap`: When you only care about the emissions from the most recent inner Observable (e.g., for type-ahead searches, cancel previous requests).
    *   `mergeMap` (alias `flatMap`): When you want to handle all inner Observables concurrently.
    *   `concatMap`: When you want to handle inner Observables sequentially, ensuring order.
    *   `exhaustMap`: When you want to ignore new inner Observables while a current inner Observable is still active (e.g., for submit buttons to prevent multiple clicks).

### 5.4. Multicasting with `share()` / `shareReplay()`
*   By default, Observables are "cold," meaning they execute their producer function for each new subscriber. For Observables that wrap expensive operations like HTTP requests, this can lead to redundant calls.
*   Use `shareReplay({ bufferSize: 1, refCount: true })` (or `share()` with appropriate configuration) to make an Observable "hot" or "warm," allowing multiple subscribers to share a single underlying subscription and execution. `shareReplay` can also cache and replay previous emissions to late subscribers.
    *   Typically used in services for Observables that fetch data via HTTP.

### 5.5. Don't Expose Subjects Directly from Services
*   If a service uses a `Subject` or `BehaviorSubject` internally to manage state or broadcast events, do not expose the Subject itself publicly.
*   Instead, expose the Subject as an `Observable` using the `.asObservable()` method. This prevents external consumers from calling `.next()`, `.error()`, or `.complete()` on the Subject, maintaining encapsulation.
*   Provide public methods on the service to trigger changes to the internal Subject if necessary.

### 5.6. Error Handling in Streams
*   Use the `catchError` operator within individual Observable pipes to handle errors gracefully. This allows you to recover from an error (e.g., return a default value, log the error) without terminating the entire outer stream.

### 5.7. Pure Functions in Operators
*   Strive to use pure functions within RxJS operators (`map`, `filter`, etc.). Pure functions produce the same output for the same input and have no side effects, leading to more predictable and testable code.

## 6. State Management Approaches

Effective state management is key to building robust applications. Angular v20+ offers powerful tools like Signals for fine-grained reactivity.

### 6.1. Local Component State with Signals
*   For state confined to a single component, **Angular Signals** are the preferred approach. They provide a simple, efficient way to manage and react to state changes.
    ```typescript
    import { Component, signal } from '@angular/core';

    @Component({
      selector: 'hgb-my-component',
      template: `Count: {{ count() }}`,
      standalone: true,
    })
    export class MyComponent {
      count = signal(0);

      increment() {
        this.count.update(c => c + 1);
      }
    }
    ```
*   Signals automatically integrate with Angular's change detection, especially when using `ChangeDetectionStrategy.OnPush` or a zoneless setup.
*   For simple properties not requiring reactivity, standard component properties are still fine.

### 6.2. Service-Based State with Signals and RxJS
*   For state shared across multiple components or features:
    *   **Signals in Services:** Use Angular Signals within services to manage shared reactive state. This is often simpler and more performant than RxJS `BehaviorSubject` for many common scenarios.
        ```typescript
        import { Injectable, signal, computed } from '@angular/core';

        @Injectable({ providedIn: 'root' })
        export class CounterService {
          private count = signal(0);
          readonly count$ = this.count.asReadonly(); // Expose as readonly signal
          readonly doubleCount = computed(() => this.count() * 2);

          increment() {
            this.count.update(c => c + 1);
          }
        }
        ```
    *   **RxJS `BehaviorSubject` in Services:** For more complex asynchronous streams, event buses, or when interoperability with existing RxJS-heavy code is needed, `BehaviorSubject` remains a valid option.
        *   Expose state as an `Observable` (using `.asObservable()`).
        *   Provide public methods to update state (calling `.next()` on the internal `BehaviorSubject`).
*   Choose between Signals and RxJS based on the complexity and nature of the state. Signals are generally preferred for synchronous state management due to their simplicity and performance benefits.

### 6.3. Global State Management Libraries (e.g., NgRx, NGXS, Elf)
*   For applications with highly complex, global state, extensive cross-component interactions, or a need for advanced features (undo/redo, devtools for state inspection, strict unidirectional data flow), consider dedicated state management libraries:
    *   **NgRx:** Implements the Redux pattern (Actions, Reducers, Selectors, Effects).
    *   **NGXS:** Uses classes for actions and state, often considered more object-oriented.
    *   **Elf:** A newer, more lightweight and flexible library that can be a good alternative.
*   **For Hangar Bay MVP, service-based state (primarily with Signals, supplemented by RxJS where appropriate) is the initial approach.** A transition to a global state library can be evaluated post-MVP if application complexity significantly increases.

## 7. Performance Considerations

Optimizing performance is crucial for a good user experience. Angular provides several mechanisms to achieve this.

### 7.1. Lazy Loading
*   (Reiterated from Module Organization) Lazy load all feature modules to reduce the initial bundle size and improve application startup time. Angular loads these modules on demand when the user navigates to their routes.
*   **Avoid Lazy-Loading the Default Route:** The module associated with the application's default route (e.g., the initial landing page after login or the home page) should typically not be lazy-loaded. Eagerly loading it prevents an extra network request and processing delay immediately after the application bootstraps, improving the perceived initial load time.

### 7.2. `OnPush` Change Detection & Signals
*   (Reiterated from Component Design) Use `ChangeDetectionStrategy.OnPush` for components to minimize unnecessary change detection cycles.
*   **Angular Signals significantly simplify `OnPush` usage.** When a signal read in a component's template changes, Angular automatically knows to mark that component and its ancestors for check, making `OnPush` more intuitive and effective.
*   If not using signals for all state, explicitly call `ChangeDetectorRef.markForCheck()` when input properties change or asynchronous operations complete that require a UI update in an `OnPush` component.

### 7.3. `trackBy` for `*ngFor`
*   When rendering lists using the `*ngFor` directive, provide a `trackBy` function.
*   This function helps Angular identify which items in the list have been added, removed, or reordered, allowing it to update only the necessary DOM elements instead of re-rendering the entire list.
    ```html
    <div *ngFor="let item of items; trackBy: trackByItemId">
      {{ item.name }}
    </div>
    ```
    ```typescript
    trackByItemId(index: number, item: Item): string | number { // Or any unique identifier
      return item.id;
    }
    ```

### 7.4. Optimize Bundle Size
*   **Ahead-of-Time (AOT) Compilation:** Enabled by default in production builds.
*   **Tree Shaking:** Ensure code is written to be tree-shakable (e.g., using ES modules).
*   **Minimize Third-Party Libraries:** Analyze bundle size impact. Prefer tree-shakable libraries or modular imports.
*   **Source Map Explorer:** Use tools like `source-map-explorer` to analyze bundle composition.
*   **Remove `zone.js` (with Zoneless):** If adopting a zoneless architecture (see 7.8), removing `zone.js` significantly reduces bundle size.

### 7.5. Pure Pipes
*   Pure pipes (the default) are only re-evaluated when their input value(s) change. Use impure pipes (`pure: false`) sparingly.

### 7.6. Angular Signals for Efficient Change Detection
*   Signals provide fine-grained reactivity. When a signal's value changes, Angular knows precisely which components depend on that signal and need to be updated.
*   This often leads to more performant change detection compared to relying solely on Zone.js, as updates are more targeted.
*   Signals are a core part of enabling a zoneless future for Angular applications.

### 7.7. Optimizing Slow Computations
*   Identify slow computations using Angular DevTools' profiler or Chrome DevTools.
*   **Techniques:**
    *   **Optimize Algorithms:** The most effective solution is to improve the underlying algorithm.
    *   **Pure Pipes for Caching:** Move heavy computations into pure pipes. Angular re-evaluates a pure pipe only if its inputs change.
    *   **Memoization:** Cache function results. Be mindful of memory overhead if computations are frequent with many different arguments.
    *   **Avoid Layout Thrashing:** Minimize operations in lifecycle hooks or template expressions that cause synchronous browser reflows/repaints (e.g., reading `offsetHeight` then immediately changing a style).
    *   **Web Workers:** For very intensive, non-UI blocking tasks, consider offloading them to Web Workers.

### 7.8. Zoneless Angular (Developer Preview)
*   **Concept:** Zoneless applications run Angular without `zone.js`. This can lead to improved performance, smaller bundle sizes, and simpler debugging (clearer stack traces).
*   **Benefits:** Reduced framework overhead, better Core Web Vitals, improved compatibility with native browser APIs and some third-party libraries.
*   **Enabling (Experimental):**
    ```typescript
    // main.ts or app.config.ts
    bootstrapApplication(AppComponent, {
      providers: [provideZonelessChangeDetection()]
    });
    ```
    Then remove `zone.js` from `polyfills.ts` (or `angular.json` polyfills array) and uninstall the package.
*   **Key Requirements & Considerations for Compatibility:**
    *   **Signals or `markForCheck()`:** Components must signal to Angular when they need to be checked. This is handled automatically by signals, the `async` pipe, or by manually calling `ChangeDetectorRef.markForCheck()`.
    *   **`OnPush` Recommended:** While not strictly required if all state changes are signaled correctly, `OnPush` helps ensure components are designed for explicit change notification.
    *   **`NgZone` API Usage:**
        *   `NgZone.onMicrotaskEmpty`, `onUnstable`, `isStable`, `onStable` will no longer work as expected and should be removed/refactored (e.g., use `afterNextRender`, `afterEveryRender`, or `MutationObserver`).
        *   `NgZone.run()` and `NgZone.runOutsideAngular()` remain compatible and can be useful for library authors supporting both zoned and zoneless apps.
    *   **SSR (`PendingTasks`):** For Server-Side Rendering, use the `PendingTasks` service to inform Angular about ongoing asynchronous operations that should complete before serialization.
    *   **Testing:** Use `provideZonelessChangeDetection()` in `TestBed` configuration. Avoid `fixture.detectChanges()` where possible; prefer `await fixture.whenStable()` or rely on signal-driven updates.
*   **Hangar Bay Status:** Zoneless is a powerful advancement. For Hangar Bay, consider adopting it once the API is stable and the team is comfortable with the implications. Initial development can proceed with a zoned approach, keeping zoneless compatibility principles in mind (e.g., using Signals, `OnPush`).

### 7.9. Virtual Scrolling for Long Lists
*   For rendering very long lists, implement virtual scrolling to enhance performance.
*   Virtual scrolling only renders the items currently visible in the viewport, significantly reducing the number of DOM elements and improving rendering speed and memory usage.
*   Utilize the Angular CDK's `ScrollingModule` (`cdk-virtual-scroll-viewport`) for a robust implementation.

## 8. Coding Style & Conventions

Consistency in coding style improves readability and maintainability.

### 8.1. Adhere to Angular Style Guide
*   Follow the official Angular Style Guide ([https://angular.dev/style-guide](https://angular.dev/style-guide)) for conventions on file naming, class naming, component selectors, property and method naming, etc.
*   **Key Naming Conventions (largely unchanged, but reinforce):**
    *   Files: `feature.component.ts`, `feature.service.ts`, `feature.module.ts`.
    *   Classes: `PascalCase` (e.g., `MyComponent`, `UserService`).
    *   Component Selectors: Kebab-case with a custom prefix (e.g., `hgb-user-profile`).
    *   Methods & Properties: `camelCase` (e.g., `getUserData`, `userName`).
    *   Interfaces/Types: `PascalCase` (e.g., `User`, `ContractDetails`). Avoid `I` prefix unless it's a strong team convention from other projects.
*   **Angular v20+ Specific Style Recommendations:**
    *   **Dependency Injection:** Prefer the `inject()` function over constructor injection for better type inference, readability, and easier commenting, especially in base classes or when DI is optional.
        ```typescript
        // Preferred
        private readonly myService = inject(MyService);
        // Over
        // constructor(private readonly myService: MyService) {}
        ```
    *   **Readonly Properties:** Mark Angular-initialized properties (like those from `inject()`, `@Input()`, `@ViewChild()`) as `readonly` if they are not reassigned after initialization.
    *   **Class/Style Bindings:** Prefer direct class and style bindings (`[class.active]`, `[style.color]`) over `[ngClass]` and `[ngStyle]` for better performance and type checking, unless complex conditional logic makes `ngClass/ngStyle` more readable.
    *   **Event Handlers:** Name event handlers for their action/intent rather than the event type (e.g., `onSaveContract()` instead of `onClickSave()`).
    *   **Lifecycle Hooks:** Keep lifecycle hook methods simple and focused. Implement the corresponding lifecycle interfaces (e.g., `OnInit`, `OnDestroy`) for clarity and type safety.

### 8.2. Strong Typing (Avoid `any`)
*   Use TypeScript's strong typing system to its full potential. Avoid using the `any` type.
*   Define interfaces or classes for all data structures (e.g., API responses, complex objects).
*   This improves code readability, enables better static analysis and refactoring by the IDE, and helps catch errors at compile-time rather than runtime.

### 8.3. Linting & Formatting
*   Use ESLint with Angular-specific plugins (e.g., `@angular-eslint`) to enforce coding standards and catch potential errors.
*   Use Prettier for automatic code formatting to ensure a consistent visual style across the codebase.
*   Configure these tools as part of the project setup (as per Task 03.1).

### 8.4. File & Directory Structure
*   **Feature-Based Structure:** Organize code primarily by feature.
    ```
    src/app/
    ├── core/
    │   ├── guards/
    │   ├── interceptors/
    │   ├── layout/ (header, footer components)
    │   ├── services/ (singleton services)
    │   └── core.module.ts
    ├── features/
    │   └── [feature-name]/ (e.g., contracts)
    │       ├── components/ (smart & dumb components for this feature)
    │       ├── guards/ (route guards specific to this feature)
    │       ├── models/ (interfaces/classes for this feature's data)
    │       ├── services/ (services specific to this feature)
    │       ├── [feature-name]-routing.module.ts
    │       └── [feature-name].module.ts
    ├── shared/
    │   ├── components/ (reusable UI components)
    │   ├── directives/
    │   ├── pipes/
    │   └── shared.module.ts
    ├── app.component.html|scss|spec|ts
    ├── app-routing.module.ts
    └── app.module.ts
    ```
*   Keep related files for a component (HTML, SCSS/CSS, TS, Spec) co-located in their own directory.

## 9. Key Code Review Guidelines (Architectural)

In addition to general code quality, pay specific attention to these architectural aspects during reviews:

*   **Module Boundaries & Responsibilities:**
    *   `CoreModule` imported only in `AppModule`.
    *   No services provided in `SharedModule`.
    *   Feature modules are lazy-loaded and well-encapsulated.
*   **Component Design:**
    *   Adherence to SRP; components are not overly complex.
    *   Use of Smart/Dumb component pattern where appropriate.
    *   `ChangeDetectionStrategy.OnPush` used, especially for presentational components.
    *   Templates are declarative, with logic primarily in the component class.
*   **Service Design:**
    *   Services follow SRP.
    *   Proper error handling, especially for API interactions.
*   **RxJS Usage:**
    *   Observables are unsubscribed (e.g., `async` pipe, `takeUntil`).
    *   No nested subscriptions; higher-order mapping operators used correctly.
    *   `subscribe()` blocks are lean.
    *   Subjects not exposed directly from services.
*   **State Management:**
    *   Appropriate use of Signals for local and service-based state.
    *   State is managed in the correct scope.
    *   Clear distinction if/when RxJS is used for state vs. Signals.
*   **Performance:**
    *   `trackBy` used with `*ngFor`.
    *   Pure pipes preferred.
    *   Mindful of slow computations and optimization techniques.
    *   Consideration for zoneless compatibility (e.g., explicit change notification if not using signals).
*   **Coding Style & Conventions:**
    *   Adherence to the Angular Style Guide ([angular.dev/style-guide](https://angular.dev/style-guide)) and project-specific conventions, including v20+ recommendations (e.g., `inject()`).
    *   Strong typing is used; `any` type is avoided.

## 10. Team Knowledge Sharing & Onboarding

*(For solo developer + Cascade: This section serves as a reminder and reference)*

*   **Regularly Review This Document:** Revisit these guidelines periodically, especially when starting new features or major refactoring.
*   **Discuss Architectural Decisions:** Any significant deviations or new patterns should be discussed and documented (e.g., in `design-log.md` and updated here).
*   **Use Task Files for Reinforcement:** Task definitions (especially for new modules or complex components) should reference these architectural guidelines to ensure awareness and adherence.

---

## 11. References

This section lists key official documentation and resources that inform these guidelines.

*   **Angular Style Guide:** [https://angular.dev/style-guide](https://angular.dev/style-guide)
*   **Security Best Practices:** [https://angular.dev/best-practices/security](https://angular.dev/best-practices/security)
*   **Accessibility (A11y) Best Practices:** [https://angular.dev/best-practices/a11y](https://angular.dev/best-practices/a11y)
*   **Error Handling Best Practices:** [https://angular.dev/best-practices/error-handling](https://angular.dev/best-practices/error-handling)
*   **Runtime Performance:** [https://angular.dev/best-practices/runtime-performance](https://angular.dev/best-practices/runtime-performance)
*   **Zone Pollution (Understanding `NgZone`):** [https://angular.dev/best-practices/zone-pollution](https://angular.dev/best-practices/zone-pollution)
*   **Slow Computations:** [https://angular.dev/best-practices/slow-computations](https://angular.dev/best-practices/slow-computations)
*   **Skipping Subtrees (Change Detection Optimization):** [https://angular.dev/best-practices/skipping-subtrees](https://angular.dev/best-practices/skipping-subtrees)
*   **Profiling with Chrome DevTools:** [https://angular.dev/best-practices/profiling-with-chrome-devtools](https://angular.dev/best-practices/profiling-with-chrome-devtools)
*   **Zoneless Angular Guide:** [https://angular.dev/guide/zoneless](https://angular.dev/guide/zoneless)
*   **Angular Performance Checklist (Community Resource):** [https://github.com/mgechev/angular-performance-checklist](https://github.com/mgechev/angular-performance-checklist)
