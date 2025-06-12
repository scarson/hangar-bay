## AI Analysis Guidance for Cascade

This file is over 200 lines long. Unless you are only looking for a specific section, you should read the entire file, which may require multiple tool calls.

# Angular Routing & Navigation (Hangar Bay)

**Last Updated:** 2025-06-09

## 1. Introduction

Routing is essential for Single Page Applications (SPAs) like Hangar Bay, enabling navigation between different views or features without full page reloads. Angular's Router is a powerful module that handles client-side navigation. This document outlines our approach to routing, emphasizing lazy loading of standalone components, route parameters, child routes, and route guards.

Referenced from: Angular Docs, `llms-full.txt` (positions 30-34), `../angular-frontend-architecture.md` (Section 2.3).

## 2. Setting Up the Router

For standalone applications, the router is typically configured in `app.config.ts` (or a dedicated `app.routes.ts` file imported there) using `provideRouter`.

### 2.1. Defining Routes (`Routes` array)

Routes are defined as an array of `Route` objects. Each route maps a URL path to a component.

```typescript
// app.routes.ts (example)
import { Routes } from '@angular/router';

export const APP_ROUTES: Routes = [
  {
    path: 'dashboard',
    // Lazy load a standalone component
    loadComponent: () => import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent),
    title: 'Hangar Bay Dashboard' // Set page title (optional, good practice)
  },
  {
    path: 'hangars',
    loadChildren: () => import('./features/hangar-management/hangar.routes').then(m => m.HANGAR_ROUTES),
    title: 'Hangar Management'
  },
  {
    path: 'profile/:userId',
    loadComponent: () => import('./features/user-profile/user-profile.component').then(m => m.UserProfileComponent),
    // Example: CanActivateFn guard
    // canActivate: [authGuardFn] 
  },
  {
    path: '', // Default route
    redirectTo: '/dashboard',
    pathMatch: 'full' // Important for default route redirects
  },
  {
    path: '**', // Wildcard route for 404 Not Found
    loadComponent: () => import('./core/components/not-found/not-found.component').then(m => m.NotFoundComponent),
    title: 'Page Not Found'
  }
];
```

### 2.2. Providing the Router (`app.config.ts`)

```typescript
// app.config.ts
import { ApplicationConfig } from '@angular/core';
import { provideRouter, withComponentInputBinding, withViewTransitions, TitleStrategy } from '@angular/router';
import { APP_ROUTES } from './app.routes';
import { CustomTitleStrategy } from './core/services/custom-title-strategy.service'; // Example

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(
      APP_ROUTES,
      withComponentInputBinding(), // Enables binding route params directly to component inputs
      withViewTransitions()        // Enables view transitions API (optional)
      // Other features: withPreloading(PreloadAllModules), withDebugTracing(), etc.
    ),
    // Provide a custom title strategy or use the default PageTitleStrategy
    { provide: TitleStrategy, useClass: CustomTitleStrategy }
  ]
};
```
- **`withComponentInputBinding()`:** Allows route parameters, query parameters, and route data to be bound directly to component inputs (using `@Input()` or `input()`). This is highly recommended.
- **`withViewTransitions()`:** Enables smooth visual transitions between routes using the browser's View Transitions API.

## 3. Lazy Loading

Lazy loading is crucial for initial application performance. It means loading feature areas (components or sets of routes) only when they are navigated to.

### 3.1. Lazy Loading Standalone Components (`loadComponent`)
- **Preferred Method:** For Hangar Bay, we will primarily lazy load standalone components directly.
  ```typescript
  {
    path: 'settings',
    loadComponent: () => import('./features/settings/settings.component').then(m => m.SettingsComponent)
  }
  ```

### 3.2. Lazy Loading Child Routes (`loadChildren`)
- **Usage:** When a feature area has its own set of child routes, `loadChildren` can be used to lazy load an entire routing configuration for that feature.
  ```typescript
  // In parent routes (e.g., app.routes.ts)
  {
    path: 'admin',
    loadChildren: () => import('./features/admin/admin.routes').then(m => m.ADMIN_ROUTES),
    // canActivate: [adminGuardFn] // Protect the whole admin section
  }

  // In ./features/admin/admin.routes.ts
  // import { Routes } from '@angular/router';
  // export const ADMIN_ROUTES: Routes = [
  //   { path: '', loadComponent: () => import('./admin-dashboard/admin-dashboard.component').then(m => m.AdminDashboardComponent) },
  //   { path: 'users', loadComponent: () => import('./manage-users/manage-users.component').then(m => m.ManageUsersComponent) },
  //   // ... other admin child routes
  // ];
  ```

## 4. Route Parameters

Route parameters allow passing data as part of the URL path.

### 4.1. Defining Routes with Parameters
- Use the colon (`:`) syntax in the path definition.
  ```typescript
  { path: 'hangar/:id/details', component: HangarDetailComponent }
  { path: 'search/:category/:term', component: SearchResultsComponent }
  ```

### 4.2. Accessing Route Parameters in Components

#### 4.2.1. With `withComponentInputBinding()` (Preferred)
If `withComponentInputBinding()` is enabled in `provideRouter`, route parameters can be bound directly to component inputs.
```typescript
// hangar-detail.component.ts
import { Component, input } from '@angular/core';

@Component({
  selector: 'hb-hangar-detail',
  standalone: true,
  template: `<p>Details for Hangar ID: {{ id() }}</p>`
})
export class HangarDetailComponent {
  id = input.required<string>(); // Route param 'id' binds here
  // If param name differs: @Input('paramName') componentProp: string;
}
```

#### 4.2.2. Using `ActivatedRoute` Service (Traditional)
```typescript
import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';

@Component({ /* ... */ })
export class LegacyHangarDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  hangarId$: Observable<string | null>;
  hangarIdSnapshot: string | null;

  ngOnInit() {
    // Observable for reactive updates if param changes without component re-creation
    this.hangarId$ = this.route.paramMap.pipe(
      map(params => params.get('id'))
    );

    // Snapshot for initial value (use with caution if component can be re-used for same route with different params)
    this.hangarIdSnapshot = this.route.snapshot.paramMap.get('id');

    this.hangarId$.subscribe(id => {
      // console.log('Hangar ID:', id);
      // Load hangar data based on id
    });
  }
}
```

### 4.3. Query Parameters and Fragments
- **Query Parameters:** Accessed via `ActivatedRoute.queryParamMap` (Observable) or `ActivatedRoute.snapshot.queryParamMap` (snapshot).
  - Example URL: `/search?query=angular&sort=asc`
- **Fragments:** Accessed via `ActivatedRoute.fragment` (Observable) or `ActivatedRoute.snapshot.fragment` (snapshot).
  - Example URL: `/docs#section-one`
- **Binding:** With `withComponentInputBinding()`, query parameters can also be bound to component inputs if the input name matches the query parameter name.

## 5. Child Routes (Nested Routing)

Child routes allow defining routes relative to a parent route, often used for master-detail views or tabbed navigation within a feature area.

```typescript
// feature.routes.ts
import { Routes } from '@angular/router';
import { FeatureComponent } from './feature.component';
import { OverviewComponent } from './overview/overview.component';
import { SpecsComponent } from './specs/specs.component';

export const FEATURE_ROUTES: Routes = [
  {
    path: '', // Parent path for this feature (e.g., /feature)
    component: FeatureComponent, // Parent component with <router-outlet>
    children: [
      { path: 'overview', component: OverviewComponent, title: 'Feature Overview' },
      { path: 'specs', component: SpecsComponent, title: 'Feature Specifications' },
      { path: '', redirectTo: 'overview', pathMatch: 'full' }
    ]
  }
];
```
- The `FeatureComponent` template must include its own `<router-outlet></router-outlet>` for child components to render into.

## 6. Route Guards

Route guards are functions that control access to routes. They can allow or deny navigation based on certain conditions (e.g., authentication, permissions, unsaved changes).

Guards are functions that return `boolean | UrlTree | Promise<boolean | UrlTree> | Observable<boolean | UrlTree>`.
- `true`: Navigation proceeds.
- `false`: Navigation is cancelled.
- `UrlTree`: Redirects to a different route (e.g., `router.parseUrl('/login')`).

### 6.1. `CanActivateFn`
- **Purpose:** Controls if a route can be activated.
- **Usage:** Check if a user is logged in or has permissions.
  ```typescript
  // auth.guard.ts
  import { inject } from '@angular/core';
  import { CanActivateFn, Router, UrlTree } from '@angular/router';
  import { AuthService } from './auth.service'; // Example service

  export const authGuardFn: CanActivateFn = (route, state): boolean | UrlTree => {
    const authService = inject(AuthService);
    const router = inject(Router);

    if (authService.isLoggedInSignal()) { // Assuming isLoggedInSignal is a signal
      return true;
    }
    // Redirect to login page
    return router.parseUrl('/login');
  };

  // In route definition:
  // { path: 'admin', component: AdminComponent, canActivate: [authGuardFn] }
  ```

### 6.2. `CanActivateChildFn`
- **Purpose:** Controls if child routes of a route can be activated. Applied to a parent route.

### 6.3. `CanDeactivateFn<T>`
- **Purpose:** Controls if a route can be deactivated. Useful for preventing navigation away from a component with unsaved changes.
- **Usage:** The component being deactivated must implement an interface or have a method that the guard can call.
  ```typescript
  // unsaved-changes.guard.ts
  import { CanDeactivateFn } from '@angular/router';

  export interface CanComponentDeactivate {
    canDeactivate: () => boolean | Promise<boolean> | Observable<boolean>;
  }

  export const unsavedChangesGuardFn: CanDeactivateFn<CanComponentDeactivate> = (component) => {
    return component.canDeactivate ? component.canDeactivate() : true;
  };

  // In component with unsaved changes (e.g., a form component):
  // export class MyFormComponent implements CanComponentDeactivate {
  //   canDeactivate(): boolean {
  //     if (this.form.dirty) {
  //       return confirm('You have unsaved changes. Are you sure you want to leave?');
  //     }
  //     return true;
  //   }
  // }
  // In route definition:
  // { path: 'edit-item/:id', component: MyFormComponent, canDeactivate: [unsavedChangesGuardFn] }
  ```

### 6.4. `ResolveFn<T>`
- **Purpose:** Pre-fetches data required for a route before the route is activated. The resolved data is made available via `ActivatedRoute.data` or bound to component inputs if `withComponentInputBinding` is used and the input name matches the resolver key.
  ```typescript
  // item.resolver.ts
  import { inject } from '@angular/core';
  import { ResolveFn, ActivatedRouteSnapshot } from '@angular/router';
  import { ItemService } from './item.service'; // Example service
  import { Item } from './item.model';

  export const itemResolverFn: ResolveFn<Item | null> = (route: ActivatedRouteSnapshot) => {
    const itemService = inject(ItemService);
    const itemId = route.paramMap.get('id');
    return itemId ? itemService.getItem(itemId) : null;
  };

  // In route definition:
  // { 
  //   path: 'item/:id', 
  //   component: ItemDetailComponent, 
  //   resolve: { item: itemResolverFn } // 'item' is the key for resolved data
  // }

  // In ItemDetailComponent (with withComponentInputBinding):
  // @Input() item: Item | null; // Resolved data bound here
  ```

## 7. Navigation

### 7.1. `RouterLink` Directive
- **Purpose:** Declarative navigation in templates.
  ```html
  <a routerLink="/users">Users List</a>
  <a [routerLink]="['/user', userId()]">User Profile</a>
  <a [routerLink]="['/product', productId()]" [queryParams]="{ version: '2.0' }" fragment="details">
    Product Details
  </a>
  ```
- **`routerLinkActive` Directive:** Adds CSS classes to an active `RouterLink`.
  ```html
  <a routerLink="/home" routerLinkActive="active-link" [routerLinkActiveOptions]="{ exact: true }">Home</a>
  ```

### 7.2. Programmatic Navigation (`Router` service)
- **Purpose:** Navigating from component TypeScript code.
  ```typescript
  import { Component, inject } from '@angular/core';
  import { Router } from '@angular/router';

  @Component({ /* ... */ })
  export class MyComponent {
    private router = inject(Router);

    navigateToUser(userId: string): void {
      this.router.navigate(['/user', userId]);
    }

    navigateToSearch(term: string): void {
      this.router.navigate(['/search'], { queryParams: { query: term } });
    }

    goBack(): void {
      // Requires Location service from @angular/common
      // this.location.back();
    }
  }
  ```

## 8. Best Practices for Routing

- **Lazy Load:** Aggressively lazy load feature modules/components.
- **`withComponentInputBinding()`:** Use it to simplify component code by binding route data directly to inputs.
- **Route Guards:** Secure and manage access to routes effectively.
- **Resolvers:** Pre-fetch critical data to improve user experience, but be mindful of initial load time if resolvers are slow.
- **Clear URL Structure:** Design logical and user-friendly URL paths.
- **Title Strategy:** Implement a `TitleStrategy` to update the browser tab title dynamically for better UX and SEO.
- **Wildcard Route:** Always include a wildcard route (`**`) at the end of your main route configuration to handle 404 scenarios gracefully.
