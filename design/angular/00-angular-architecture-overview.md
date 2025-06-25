# Hangar Bay - Angular Frontend Architecture

**Last Updated:** 2025-06-25

## 1. Introduction

This document outlines the high-level architecture for the Hangar Bay Angular frontend. Our goal is to build a modern, scalable, performant, and maintainable application by leveraging the latest Angular features and best practices.

This document serves as the single source of truth for our architectural decisions. For in-depth details on specific topics, refer to the guideline documents in the `design/angular/guides/` directory.

## 2. Core Architectural Tenets

Our frontend architecture is built upon the following core principles, which together enable a high-performance, **zoneless** application.

### 2.1. Change Detection: Zoneless by Default
- **Primary Approach:** The application is **zoneless**. We bootstrap Angular without `zone.js` to achieve better performance, smaller bundle sizes, and clearer stack traces.
- **Mechanism:** Change detection is driven by **Angular Signals**. All state should be managed via signals (`signal`, `computed`, `effect`) to ensure fine-grained, automatic reactivity.
- **Details:** See [`design/angular/guides/09-testing-strategies.md`](./guides/09-testing-strategies.md) for critical information on testing in a zoneless environment.

### 2.2. Component Model: Standalone by Default
- **Primary Approach:** We exclusively use **Standalone Components, Directives, and Pipes**. This approach completely removes the need for `NgModules`.
- **Benefits:** Enhances modularity, improves tree-shakability, and simplifies dependency management at the component level.
- **Details:** See [`design/angular/guides/02-component-and-directive-deep-dive.md`](./guides/02-component-and-directive-deep-dive.md)

### 2.3. Reactivity & State Management: Signals First
- **Primary Reactive Primitive:** **Angular Signals** are the primary mechanism for managing all application state.
- **RxJS Integration:** RxJS is reserved for handling complex asynchronous operations (e.g., orchestrating multiple HTTP requests). Use `rxjs-interop` utilities like `toSignal` to integrate RxJS streams into the signal-based state model.
- **Details:** See [`design/angular/guides/04-state-management-and-rxjs.md`](./guides/04-state-management-and-rxjs.md)

### 2.4. Routing: Lazy Loading with Standalone Components
- **Strategy:** We will utilize Angular's router with **lazy loading** as the default for all feature routes to ensure optimal initial load performance.
- **Implementation:** Routes will be configured to lazy-load standalone components (`loadComponent`) or entire sets of routes (`loadChildren`).
- **Details:** See [`design/angular/guides/06-routing-and-navigation.md`](./guides/06-routing-and-navigation.md)

### 2.5. Styling: Component-Scoped SCSS
- **Approach:** Styles will be component-scoped using Angular's view encapsulation and written in SCSS.
- **Global Styles:** A minimal set of global styles (e.g., CSS resets, theme variables) is defined in `src/styles.scss`.
- **Details:** See [`design/angular/guides/01-coding-style-guide.md`](./guides/01-coding-style-guide.md)

### 2.6. HTTP Communication: Typed `HttpClient`
- **Client:** Angular's `HttpClient` is used for all HTTP communication, configured via `provideHttpClient(withInterceptors([...]))`.
- **Interceptors:** Use modern, functional HTTP interceptors for cross-cutting concerns like authentication and error handling.
- **Details:** See [`design/angular/guides/07-http-and-data-loading.md`](./guides/07-http-and-data-loading.md)

### 2.7. Performance: Proactive Optimization
- **Key Techniques:**
    - **Zoneless:** The foundation of our performance strategy.
    - **`@defer` Blocks:** Extensive use of deferrable views for non-critical UI sections.
    - **`@for` with `track`:** Use of the built-in control flow's `track` function to optimize list rendering.
    - **SSR/SSG & Hydration:** Server-Side Rendering (SSR) with hydration will be implemented to improve SEO and perceived performance.
- **Details:** See [`design/angular/guides/08-ssr-and-performance.md`](./guides/08-ssr-and-performance.md)

## 3. Directory and File Structure

The Angular application in `src/app/` is organized by **feature**. This structure promotes scalability and modularity by grouping related files together. The canonical structure is as follows:

```
src/app/
├── app.config.ts         # Core application providers (routing, http, etc.)
├── app.component.ts      # Root application component
├── app.routes.ts         # Top-level application routes
|
├── core/                 # Singleton services, guards, and truly global logic.
│   ├── services/         # App-wide singleton services (e.g., auth, logging)
│   ├── guards/           # App-wide route guards
│   └── models/           # App-wide data models
|
├── features/             # Feature-specific modules. Each feature is self-contained.
│   └── contracts/        # Example: Contracts Feature
│       ├── contract-list/  # Example: Smart component for listing contracts
│       │   ├── contract-list.component.html
│       │   ├── contract-list.component.scss
│       │   └── contract-list.component.ts
│       │
│       ├── contract-details/ # Example: Smart component for contract details
│       │   └── ...
│       │
│       ├── contract.api.ts   # Service for this feature's backend communication
│       ├── contract.model.ts # TypeScript interfaces for this feature
│       └── contracts.routes.ts # Routes specific to this feature, lazy-loaded
|
└── shared/               # Reusable, presentation-agnostic code.
    ├── components/       # Reusable "dumb" UI components (e.g., button, card)
    ├── pipes/            # Reusable custom pipes
    ├── directives/       # Reusable custom directives
    └── utils/            # Reusable helper functions
```

**File Naming Conventions:**
- Components: `*.component.ts`
- Services / APIs: `*.api.ts` or `*.service.ts`. The class name should omit the `Service` suffix (e.g., `class Auth` in `auth.service.ts`, not `class AuthService`). The context is provided by the file location and usage.
- Models / Interfaces: `*.model.ts`
- Guards: `*.guard.ts`
- Pipes: `*.pipe.ts`
- Directives: `*.directive.ts`
- Routes: `*.routes.ts`

## 4. Coding Style and Conventions

All Angular code will adhere to the guidelines specified in [`design/angular/guides/01-coding-style-guide.md`](./guides/01-coding-style-guide.md). This includes naming conventions, DI patterns (preferring the `inject` function), and strong typing.

## 5. Living Document

This architecture document is a living document and will be updated as the project evolves and as new Angular features or best practices emerge. All significant deviations or new patterns must be discussed and documented here.
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
