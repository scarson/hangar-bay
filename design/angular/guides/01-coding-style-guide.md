# Angular Coding Style Guide (Hangar Bay)

**Last Updated:** 2025-06-09

## 1. Introduction

This guide details the coding style conventions for Angular application code within the Hangar Bay project. These recommendations are derived from the official Angular style guide, the `llms-full.txt` resource provided by Angular for AI assistants, and project-specific preferences. Adherence to these styles promotes consistency, readability, and maintainability, making it easier to collaborate and scale the project.

This guide complements the overarching architectural decisions outlined in `../angular-frontend-architecture.md`.

When in doubt, prefer consistency within a file over strictly adhering to a rule if it causes a jarring mix of styles.

## 2. Naming Conventions

Referenced from: Angular Style Guide (`llms-full.txt` positions 6+)

### 2.1. File Names

-   **General:** Separate words in file names with hyphens (`-`). Example: `user-profile.component.ts`.
-   **Components:** `[name].component.ts`, `[name].component.html`, `[name].component.scss`.
    -   Example: `hangar-bay-status.component.ts`
-   **Directives:** `[name].directive.ts`.
    -   Example: `highlight-on-hover.directive.ts`
-   **Pipes:** `[name].pipe.ts`.
    -   Example: `truncate-text.pipe.ts`
-   **Services:** `[name].service.ts`.
    -   Example: `hangar-data.service.ts`
-   **Standalone Routes/Configuration:** `[feature].routes.ts` or `[feature].config.ts`.
    -   Example: `hangar-management.routes.ts`
-   **Models/Interfaces:** `[name].model.ts` or `[name].interface.ts` (though often interfaces can be co-located if small and specific to one consumer, or grouped by feature).
    -   Example: `hangar.model.ts`
-   **Unit Tests:** Append `.spec` to the name of the file being tested. Example: `user-profile.component.spec.ts`.

### 2.2. TypeScript Identifiers

-   **Classes, Interfaces, Enums, Type Aliases:** Use PascalCase. Examples: `UserProfileComponent`, `Hangar`, `LoadingState`, `AppConfig`.
-   **Functions, Methods, Properties, Variables:** Use camelCase. Examples: `getUserProfile`, `hangarName`, `isLoading`, `appTitle`.
-   **Constants:** Use `UPPER_SNAKE_CASE` for true constants (immutable, globally available values). For `readonly` properties or configuration values, camelCase is often preferred if they are not global constants in the traditional sense.
    -   Example: `MAX_HANGAR_CAPACITY = 100;`
    -   Example (preferred for service config): `readonly defaultPageSize = 20;`
-   **Selector Prefixes:** All component and directive selectors should be prefixed to avoid collisions with native HTML elements or third-party libraries. For Hangar Bay, our prefix is `hb`.
    -   Component Example: `selector: 'hb-user-profile'`
    -   Directive Example: `selector: '[hbTooltip]'`

### 2.3. Component and Directive Members

-   **Inputs:** Use camelCase. See `../angular-frontend-architecture.md` and `02-component-and-directive-deep-dive.md` for details on signal-based vs. `@Input()`.
    -   Example (Signal): `user = input<User>();`
    -   Example (@Input): `@Input() userName: string;`
-   **Outputs:** Use camelCase. Event names should describe what *happened*. See `../angular-frontend-architecture.md` and `02-component-and-directive-deep-dive.md`.
    -   Example (Signal): `itemSelected = output<string>();`
    -   Example (@Output): `@Output() saveClicked = new EventEmitter<void>();`
-   **Event Handlers:** Name event handlers for what they *do*, not for the triggering event. Prefix with `on`.
    -   Example: `onSaveProfile() { ... }` (handles a click that means 'save profile') not `onSaveButtonClick()`.

## 3. Project Structure

Referenced from: Angular Style Guide (`llms-full.txt` position 7), `../angular-frontend-architecture.md` Section 4.

-   **`src/` Directory:** All application code (TypeScript, HTML, SCSS) resides within `src/`.
-   **`main.ts`:** Application bootstrap logic is in `src/main.ts`.
-   **Feature-Based Organization:** Organize the `src/app/` directory by features, not by type. See `../angular-frontend-architecture.md` for the high-level structure (`core/`, `features/`, `shared/`).
-   **Co-location:** Group closely related files for a feature or component together in the same directory (e.g., component TS, HTML, SCSS, and spec file).
-   **One Concept Per File:** Prefer one primary concept (e.g., one component, one service) per file. Small, closely related interfaces or types can be co-located if they aren't widely shared.

## 4. Dependency Injection (DI)

Referenced from: Angular Style Guide (`llms-full.txt` position 8), `../angular-frontend-architecture.md` Section 2.2.

-   **Prefer `inject()` Function:** For injecting dependencies into classes (components, services, directives), prefer using the `inject()` function over constructor parameter injection.
    -   **Rationale:** More readable for many dependencies, easier to add comments, better type inference, avoids issues with `useDefineForClassFields`.
    -   **Example:**
        ```typescript
        import { Component, inject } from '@angular/core';
        import { UserService } from './user.service';

        @Component({...})
        export class UserProfileComponent {
          private userService = inject(UserService);
          // ...
        }
        ```
-   **`providedIn: 'root'`:** For singleton services, use `providedIn: 'root'` in the `@Injectable` decorator unless a more specific provider scope is intentionally needed.

## 5. Component and Directive Style

Referenced from: Angular Style Guide (`llms-full.txt` positions 9+)

### 5.1. Property and Method Organization

-   Group Angular-specific properties (inputs, outputs, queries, injected dependencies) near the top of the class, before other properties and methods.
-   Follow with public, then protected, then private properties/methods if not strictly ordered by Angular decorators.

### 5.2. Focus and Complexity

-   **Presentation Focus:** Components and directives should primarily focus on UI presentation and interaction. Complex business logic, data transformations, or validation rules should be delegated to services or utility functions.
-   **Template Logic:** Keep template expressions relatively simple. If logic becomes complex (multiple conditions, complex transformations), move it into the component's TypeScript code, often using a `computed` signal or a method.

### 5.3. Access Modifiers

-   **`protected` for Template Members:** Use `protected` for class members (properties or methods) that are only accessed by the component's template and are not part of its public API for other components/services.
    ```typescript
    @Component({
      template: `<p>{{ fullName() }}</p>`
    })
    export class UserProfileComponent {
      firstName = input.required<string>();
      lastName = input.required<string>();

      protected fullName = computed(() => `${this.firstName()} ${this.lastName()}`);
    }
    ```
-   **`readonly` for Angular-Initialized Properties:** Mark properties initialized by Angular (inputs, model inputs, outputs, queries) as `readonly` where appropriate to prevent accidental reassignment.
    -   For signal-based inputs/outputs (`input()`, `output()`, `model()`), the signal itself is the reference and is typically not reassigned, so `readonly` on the signal variable is natural.
    -   For decorator-based `@Output()` and queries (`@ViewChild`, `@ContentChild` etc.), `readonly` is highly recommended.
    ```typescript
    // Signal-based
    readonly userId = input<string>();
    readonly userSaved = output<void>();

    // Decorator-based
    @Output() readonly itemClicked = new EventEmitter<string>();
    @ViewChild('myChart') readonly chart?: ElementRef;
    ```

### 5.4. Template Bindings

-   **Prefer `[class]` and `[style]` Bindings:** Over `[ngClass]` and `[ngStyle]` directives for better readability and performance.
    ```html
    <!-- PREFER -->
    <div [class.active]="isActive" [style.color]="textColor">

    <!-- AVOID -->
    <div [ngClass]="{'active': isActive}" [ngStyle]="{'color': textColor}">
    ```

### 5.5. Lifecycle Hooks

-   **Implement Interfaces:** When using lifecycle hooks (e.g., `OnInit`, `OnDestroy`), implement the corresponding interface (e.g., `implements OnInit`).
-   **Keep Simple:** Lifecycle hook methods should be kept lean. Delegate complex logic to other methods or services.
-   **`ngOnChanges`:** Use sparingly. Signals often provide a more direct way to react to input changes. If used, ensure logic is efficient as it can fire frequently.

## 6. Modularity and Single Responsibility

-   **Components:** Aim for small, focused components. If a component becomes too large or handles too many responsibilities, decompose it into smaller, child components.
-   **Services:** Services should have a clear, single responsibility (e.g., data fetching for a specific resource, authentication logic, UI notifications).

## 7. Code Comments

-   **Clarity:** Write clear, concise comments to explain complex logic, non-obvious decisions, or important workarounds.
-   **Avoid Redundant Comments:** Do not comment code that is self-explanatory (e.g., `// increment i by 1`).
-   **TODOs:** Use `// TODO:` for tasks that need to be done, and `// FIXME:` for known issues that need fixing. Include a brief explanation.

## 8. Imports

-   **Organize:** Group imports: Angular imports first, then third-party library imports, then application-specific imports. Within groups, sort alphabetically if desired (IDE can often automate this).
-   **Path Aliases:** Utilize TypeScript path aliases (configured in `tsconfig.json`) for cleaner import paths to shared modules or core services (e.g., `@core/services`, `@shared/components`).

This style guide is a living document and may be updated as the project evolves or new Angular best practices emerge.
