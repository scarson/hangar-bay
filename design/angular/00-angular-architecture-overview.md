# Hangar Bay - Angular Frontend Architecture

## 1. Introduction

This document outlines the high-level architecture for the Hangar Bay Angular frontend. Our goal is to build a modern, scalable, performant, and maintainable application by leveraging the latest Angular features and best practices.

This document serves as an umbrella, providing concise summaries for key architectural areas. For in-depth details, please refer to the specific guideline documents located in the `design/angular/guides/` directory.

## 2. Core Architectural Tenets

Our frontend architecture is built upon the following core principles, which together enable a high-performance, **zoneless** application.

### 2.1. Change Detection: Zoneless by Default
- **Primary Approach:** The application will be **zoneless**. We will bootstrap Angular without `zone.js` to achieve better performance, smaller bundle sizes, and clearer stack traces.
- **Mechanism:** Change detection is triggered automatically by Angular's modern reactivity primitives. This means relying on **Signals** for state management and using the `async` pipe for RxJS observables in templates.
- **Compatibility:** This approach requires adherence to patterns that work without Zone.js's automatic change detection. All new code must be written with this in mind.

### 2.2. Component Model: Standalone by Default
- **Primary Approach:** We will exclusively use **Standalone Components, Directives, and Pipes**. This approach simplifies the component model by completely removing the need for `NgModules` for component declaration.
- **Benefits:** Enhances modularity, improves tree-shakability, simplifies dependency management at the component level, and is the standard for modern Angular applications.
- **Details:** See [`design/angular/guides/02-component-and-directive-deep-dive.md`](./guides/02-component-and-directive-deep-dive.md)

### 2.3. Reactivity & State Management: Signals First
- **Primary Reactive Primitive:** **Angular Signals** are the primary mechanism for managing all application state. This includes `signal`, `computed`, and `effect`.
- **Benefits:** Provides fine-grained reactivity, which is essential for a zoneless architecture. It offers excellent performance by default and a more intuitive developer experience.
- **RxJS Integration:** RxJS will be used for handling complex asynchronous operations and event streams. We will leverage `rxjs-interop` utilities like `toSignal` for seamless integration into the Signal-based state model.
- **Details:** See [`design/angular/guides/04-state-management-and-rxjs.md`](./guides/04-state-management-and-rxjs.md)

### 2.4. Routing: Lazy Loading with Standalone Components
- **Strategy:** We will utilize Angular's router with **lazy loading** as the default for all feature routes to ensure optimal initial load performance.
- **Implementation:** Routes will be configured to lazy-load standalone components directly using `loadComponent` or route groups using `loadChildren` that, in turn, load a set of routes.
- **Details:** See [`design/angular/guides/06-routing-and-navigation.md`](./guides/06-routing-and-navigation.md)

### 2.5. Styling: Component-Scoped
- **Approach:** Styles will be component-scoped using Angular's view encapsulation. This prevents style leakage and promotes modularity.
- **Global Styles:** A minimal set of global styles (e.g., base typography, resets, theme variables) will be defined in `src/styles.scss`.
- **Details:** See coding style guidelines in [`design/angular/guides/01-coding-style-guide.md`](./guides/01-coding-style-guide.md)

### 2.6. HTTP Communication: Typed `HttpClient` with Functional Interceptors
- **Client:** Angular's `HttpClient`, configured using `provideHttpClient(withInterceptors([...]))`, will be used for all HTTP communication.
- **Interceptors:** We will use modern, functional HTTP interceptors for tasks like authentication, caching, and error handling.
- **Details:** See [`design/angular/guides/07-http-and-data-loading.md`](./guides/07-http-and-data-loading.md)

### 2.7. Forms: Reactive Forms with Strong Typing
- **Primary Approach:** **Reactive Forms** will be used for all forms due to their scalability, testability, and explicit, signal-friendly control model.
- **Details:** See [`design/angular/guides/05-forms-and-validation.md`](./guides/05-forms-and-validation.md)

### 2.8. Performance: Proactive Optimization
- **Key Techniques:**
    - **Zoneless:** The foundation of our performance strategy.
    - **Lazy Loading & `@defer` Blocks:** Extensive use of lazy loading for routes and deferrable views (`@defer`) for non-critical UI sections.
    - **`track` Function:** Use of the `track` function in the new `@for` control flow to optimize list rendering.
    - **SSR/SSG & Hydration:** Server-Side Rendering (SSR) with hydration will be implemented to improve SEO and perceived performance.
- **Details:** See [`design/angular/guides/08-ssr-and-performance.md`](./guides/08-ssr-and-performance.md)

## 3. Directory Structure

The Angular application within `src/app/` will be organized by **feature**. Avoid top-level directories like `components` or `services`. A typical feature directory will contain all its own components, services, routes, and type definitions.

- `src/app/`
    - `app.config.ts`
    - `app.component.ts`
    - `app.routes.ts`
    - `features/`
        - `hangar-management/`
        - `user-profile/`
    - `shared/`
        - `ui/` (Reusable, stateless UI components)
        - `data-access/` (Reusable services)
        - `utils/` (Helper functions)

## 4. Coding Style and Conventions

All Angular code will adhere to the guidelines specified in [`design/angular/guides/01-coding-style-guide.md`](./guides/01-coding-style-guide.md). This includes naming conventions, file organization, DI patterns (preferring the `inject` function), and more.

## 5. Living Document

This architecture document is a living document and will be updated as the project evolves and as new Angular features or best practices emerge.

**Last Updated:** 2025-06-08
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
