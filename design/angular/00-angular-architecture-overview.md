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

### 2.6. HTTP Communication: Typed `HttpClient` with Fetch
- **Client:** Angular's `HttpClient` is used for all HTTP communication.
- **Transport Layer:** It is a project-wide standard to configure `HttpClient` to use the modern `fetch` API as its transport mechanism. This improves stability, especially in proxied development environments, and is configured once in `app.config.ts` via `provideHttpClient(withFetch())`.
- **Interceptors:** Modern, functional HTTP interceptors are used for cross-cutting concerns like authentication and error handling.
- **Details:** See [`design/angular/guides/07-http-and-data-loading.md`](./guides/07-http-and-data-loading.md)

### 2.7. Performance: Proactive Optimization
- **Key Techniques:**
    - **Zoneless:** The foundation of our performance strategy.
    - **`@defer` Blocks:** Extensive use of deferrable views for non-critical UI sections.
    - **`@for` with `track`:** Use of the built-in control flow's `track` function to optimize list rendering.
    - **SSR/SSG & Hydration:** Server-Side Rendering (SSR) with hydration will be implemented to improve SEO and perceived performance.
- **Details:** See [`design/angular/guides/08-ssr-and-performance.md`](./guides/08-ssr-and-performance.md)

## 3. Directory and File Structure

The Angular application in `src/app/` is organized by **feature**. This structure promotes scalability and modularity by grouping related files together. The canonical structure is as follows, and is also maintained as a persistent AI memory for reference.

```
/src
|-- /app
|   |-- /core                 # Singleton services, guards, and truly global logic.
|   |   `-- /layout           # Components that define the main page structure (e.g., header, footer).
|   |       |-- /footer
|   |       |   |-- footer.ts       # Footer component class
|   |       |   |-- footer.html     # Footer component template
|   |       |   |-- footer.scss     # Footer component styles
|   |       |   `-- footer.spec.ts  # Tests for the footer component
|   |       `-- /header
|   |           |-- header.ts       # Header component class
|   |           |-- header.html     # Header component template
|   |           |-- header.scss     # Header component styles
|   |           `-- header.spec.ts  # Tests for the header component
|   |-- /features             # Feature-specific modules. Each feature is self-contained.
|   |   `-- /contracts        # Example: Contracts Feature
|   |       |-- /contract-browse-page # A "smart" routed component for this feature.
|   |       |   |-- contract-browse-page.ts
|   |       |   |-- contract-browse-page.html
|   |       |   |-- contract-browse-page.scss
|   |       |   `-- contract-browse-page.spec.ts
|   |       |-- contract.models.ts # TypeScript interfaces for this feature's data models.
|   |       |-- contract.state.ts  # State management service for this feature.
|   |       `-- contract-search.ts # Model for the feature's search/filter parameters.
|   |-- /shared               # Reusable, presentation-agnostic code.
|   |   ├── /components       # Reusable "dumb" UI components (e.g., button, card)
|   |   ├── /directives       # Reusable custom directives
|   |   ├── /pipes            # Reusable custom pipes
|   |   |   |-- isk.ts          # Pipe to format numbers as ISK currency.
|   |   |   `-- isk.spec.ts     # Tests for the ISK pipe.
|   |   `── /utils            # Reusable helper functions
|   |-- app.config.ts         # Core application providers (routing, http, zoneless, etc.)
|   |-- app.config.spec.ts    # Tests for app.config.ts
|   |-- app.routes.ts         # Top-level application routes
|   |-- app.ts                # Root application component class
|   |-- app.html              # Root application component template
|   |-- app.scss              # Root application component styles
|   `-- app.spec.ts           # Tests for the root application component
|-- /environments           # Environment-specific configuration files.
|   |-- environment.prod.ts   # Production environment configuration
|   `-- environment.ts        # Development environment configuration
|-- index.html              # The main HTML page that is served.
|-- main.ts                 # The main entry point for the application, bootstraps Angular.
`-- styles.scss             # Global application styles and CSS variable definitions.
```

**File Naming Conventions:**
- Components: `*.ts`. The class name **must also omit** the `Component` suffix (e.g., `class UserProfile` in `user-profile.ts`).
- Services / APIs: `*.api.ts` or `*.service.ts`. The class name should omit the `Service` suffix (e.g., `class Auth` in `auth.service.ts`).
- Pipes: `*.ts`. The class name should omit the `Pipe` suffix (e.g., `class Isk` in `isk.ts`).
- Models / Interfaces: `*.model.ts`
- Guards: `*.guard.ts`
- Directives: `*.directive.ts`
- Routes: `*.routes.ts`

## 4. Coding Style and Conventions

All Angular code will adhere to the guidelines specified in [`design/angular/guides/01-coding-style-guide.md`](./guides/01-coding-style-guide.md). Key highlights include:

*   **Strong Typing:** Avoid the `any` type. Define interfaces or classes for all data structures.
*   **Readonly Properties:** Mark Angular-initialized properties (like those from `inject()`, `input()`, `viewChild()`) as `readonly` if they are not reassigned.
*   **Event Handlers:** Name event handlers for their action/intent (e.g., `onSaveContract()` instead of `onClickSave()`).
*   **Linting & Formatting:** ESLint and Prettier are configured to enforce standards and consistent style.

## 5. Key Code Review Guidelines (Architectural)

In addition to general code quality, pay specific attention to these architectural aspects during reviews, ensuring they align with our **zoneless, standalone, and signal-first** architecture.

*   **Service Provision & Scoping:**
    *   Services intended to be singletons should be `providedIn: 'root'`.
    *   For feature-specific services, provide them directly in the feature's routing configuration or within the component that requires them, not at the root level.
    *   Avoid providing services in shared, presentational components.

*   **Component Design:**
    *   **Signal-Based Inputs:** Prefer `input()` for component inputs over `@Input()` decorators to leverage signal-based reactivity.
    *   **State Encapsulation:** Component state should be managed with signals (`signal`, `computed`).
    *   **Adherence to SRP:** Components should have a single responsibility and not be overly complex.
    *   **Smart/Dumb Pattern:** Use the "Smart/Container" and "Dumb/Presentational" component pattern where it clarifies data flow. Presentational components should receive all data via inputs and emit events via outputs.

*   **State Management & Reactivity:**
    *   **Signals First:** Signals are the default for all state management.
    *   **RxJS for Complex Async:** Reserve RxJS for orchestrating complex asynchronous events (e.g., websockets, multi-step async flows). Use `toSignal` from `@angular/core/rxjs-interop` to bridge RxJS streams back into the signal ecosystem.
    *   **Lean Subscriptions:** If `subscribe()` is used, the block should be minimal, typically just updating a signal. Avoid nested subscriptions.
    *   **Avoid Exposed Subjects:** Do not expose RxJS Subjects publicly from services. Expose signals or observables instead.

## 6. Living Document

This architecture document is a living document and will be updated as the project evolves and as new Angular features or best practices emerge. All significant deviations or new patterns must be discussed and documented here.

*   **Performance:**
    *   **`@for` with `track`:** Always use `track` with the built-in `@for` block for list rendering to ensure optimal performance. The legacy `*ngFor` with `trackBy` should not be used.
    *   **`@defer` for Non-Critical UI:** Use deferrable views (`@defer`) extensively to lazy-load components and UI sections that are not critical for the initial view.
    *   **Pure Pipes:** Prefer pure pipes for data transformation in templates.

*   **Coding Style & Conventions:**
    *   **`inject()` Function:** Use the `inject()` function for dependency injection within the constructor or at the class field level. Avoid `constructor(private ...)` where possible.
    *   **Strong Typing:** Strictly avoid the `any` type. Define interfaces or classes for all data structures.
    *   **Adherence to Guides:** Follow all conventions outlined in this document and the linked guides in `design/angular/guides/`.

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
