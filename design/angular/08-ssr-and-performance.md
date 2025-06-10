# Angular SSR & Performance (Hangar Bay)

**Last Updated:** 2025-06-09

## 1. Introduction

Application performance is critical for user experience, engagement, and SEO. Hangar Bay aims to be a fast and responsive application. This document outlines strategies for performance optimization, including Server-Side Rendering (SSR), Static Site Generation (SSG), the new `@defer` block for deferrable views, and other general best practices.

Referenced from: Angular Docs, `llms-full.txt` (positions 39-42 for SSR/Universal, 22 for `@defer`), `../angular-frontend-architecture.md` (Section 2.8).

## 2. Server-Side Rendering (SSR) & Static Site Generation (SSG)

Angular Universal allows rendering Angular applications on the server, sending fully formed HTML to the browser. This can be done per-request (SSR) or at build time (SSG/prerendering).

### 2.1. Benefits

-   **Improved Perceived Performance:** Users see meaningful content faster because the browser doesn't have to wait for the client-side app to bootstrap and render.
-   **Better SEO:** Search engine crawlers can more easily index content that is present in the initial HTML response.
-   **Enhanced Core Web Vitals:** Particularly First Contentful Paint (FCP) and Largest Contentful Paint (LCP).

### 2.2. When to Consider SSR/SSG for Hangar Bay

-   **Public-Facing Pages:** If Hangar Bay has marketing pages, landing pages, or content that needs to be highly discoverable by search engines, SSR/SSG is beneficial.
-   **Content-Rich Pages:** Pages displaying significant amounts of data that can be fetched server-side.
-   **Authenticated Areas:** SSR can still be used for authenticated areas, but requires careful handling of user-specific data and authentication state on the server.

### 2.3. Setting Up Angular Universal (SSR)

Adding SSR to an existing Angular CLI project is typically done with:
`ng add @angular/ssr` (or `ng add @nguniversal/express-engine` for older versions, but `@angular/ssr` is the modern approach).

This command will:
-   Add necessary dependencies.
-   Create server-side entry files (e.g., `server.ts`).
-   Update `angular.json` with build configurations for server and prerendering.
-   Modify `app.module.ts` or `app.config.ts` to include server-specific providers.

### 2.4. Hydration

-   **Concept:** After the server-rendered HTML is delivered to the browser, Angular client-side code takes over (hydrates) the existing DOM, making it interactive without destroying and re-rendering it.
-   **Enabling:** Hydration is typically enabled by default with `@angular/ssr` or can be configured with `provideClientHydration()` in `app.config.ts`.
-   **Benefits:** Smoother transition from server-rendered content to a fully interactive client-side app, improving LCP and reducing flicker.
-   **Considerations:** Ensure your components are hydration-friendly (avoid direct DOM manipulation that conflicts with server-rendered content before hydration).

### 2.5. Prerendering (SSG)

-   For pages that don't change frequently, you can prerender them at build time into static HTML files.
-   Define routes to prerender in `angular.json` or a separate routes file.
-   Command: `ng build && ng run <project-name>:prerender`

## 3. Deferrable Views (`@defer`)

The `@defer` block is a powerful template syntax feature (introduced in Angular v17) for client-side progressive lazy loading of UI sections. It allows you to defer the loading and rendering of non-critical parts of a component's template until certain conditions are met.

### 3.1. Benefits

-   **Improved Initial Load Time:** Reduces the initial JavaScript bundle size and rendering workload by deferring less critical content.
-   **Enhanced Core Web Vitals:** Can significantly improve LCP and Time to Interactive (TTI).
-   **Granular Control:** Provides fine-grained control over what and when to lazy load within a component.

### 3.2. Basic Syntax

```html
@defer (on <trigger>) {
  <hb-heavy-component [data]="someData()"></hb-heavy-component>
  <p>This content is deferred.</p>
} @placeholder (minimum <duration>) {
  <p>Placeholder content while loading...</p>
} @loading (minimum <duration>; after <duration>) {
  <hb-spinner></hb-spinner>
  <p>Loading deferred content...</p>
} @error {
  <p>Failed to load the deferred content. <button (click)="retry()">Retry</button></p>
}
```

-   **Main Block (`@defer`):** Contains the content to be lazy-loaded. The components, directives, and pipes used exclusively within this block are bundled into separate chunks and loaded only when the trigger condition is met.
-   **`@placeholder`:** (Optional) Displays content immediately until the defer condition is met and loading begins. `minimum` specifies a minimum display time for the placeholder.
-   **`@loading`:** (Optional) Displays content while the deferred dependencies are being fetched. `minimum` and `after` control its display timing relative to loading start.
-   **`@error`:** (Optional) Displays content if loading the deferred block fails.

### 3.3. Triggers

Triggers determine when the deferred block should load and render.

-   **`on immediate`:** Loads as soon as the browser is idle (default if no trigger is specified).
-   **`on interaction`:** Loads when the user interacts with the placeholder block or a specified trigger element.
    ```html
    <button #triggerBtn>Load Comments</button>
    @defer (on interaction(triggerBtn)) { ... }
    ```
-   **`on hover`:** Loads when the user hovers over the placeholder or a specified trigger element.
-   **`on timer(<duration>)`:** Loads after a specified duration.
    ```html
    @defer (on timer(5s)) { ... }
    ```
-   **`on viewport`:** Loads when the placeholder or a specified trigger element enters the viewport.
    ```html
    <div #commentsSection></div>
    @defer (on viewport(commentsSection)) {
      <hb-comment-list></hb-comment-list>
    }
    ```
-   **`when <condition>`:** Loads when a boolean expression (often based on a signal) becomes true.
    ```html
    @defer (when commentsVisible()) {
      <hb-comment-list></hb-comment-list>
    }
    ```
-   **Multiple Triggers:** You can combine triggers (e.g., `on interaction, timer(3s)`). The first one to fire will load the block.

### 3.4. Prefetching

-   You can instruct Angular to prefetch the resources for a deferred block before the main trigger condition is met.
    ```html
    @defer (on interaction; prefetch on idle) { ... }
    @defer (when showDetails(); prefetch when canPrefetchDetails()) { ... }
    ```

### 3.5. Usage in Hangar Bay

-   Identify non-critical sections of pages (e.g., comment sections, related articles, complex charts, user reviews, non-essential widgets).
-   Use `@defer` with appropriate triggers to improve initial page rendering performance.
-   Provide meaningful `@placeholder` and `@loading` states for better UX.

## 4. Other Performance Best Practices

### 4.1. Lazy Loading Routes
-   As detailed in `06-routing-and-navigation.md`, always lazy load feature modules/components at the route level. This is a fundamental performance optimization.

### 4.2. `track` / `trackBy` for Lists
-   When rendering lists with `@for` (new control flow) or `*ngFor` (legacy), always use `track item.id` or a `trackBy` function respectively. This helps Angular efficiently update the DOM when list items change, are added, or removed.

### 4.3. Optimized Change Detection (Signals)
-   Angular Signals inherently provide more fine-grained reactivity, leading to more optimized change detection by default compared to traditional Zone.js-based change detection for all components.
-   For components still using Zone.js (e.g., older components or those not fully migrated to signals), `ChangeDetectionStrategy.OnPush` can be beneficial, but Signals are the more modern and often more effective approach.

### 4.4. Bundle Analysis
-   Regularly analyze your application's bundle size using tools like `source-map-explorer` or `webpack-bundle-analyzer` (via `ng build --stats-json`).
-   Identify large dependencies or chunks that could be optimized, code-split, or lazy-loaded.

### 4.5. Code Splitting
-   Beyond route-level lazy loading and `@defer`, ensure your codebase is structured to allow Webpack (Angular CLI's bundler) to effectively split code into smaller, manageable chunks.

### 4.6. Optimize Assets
-   Compress images (use appropriate formats like WebP).
-   Minify CSS and JavaScript (done by default in production builds by Angular CLI).
-   Consider lazy loading images that are off-screen (`loading="lazy"` attribute).

### 4.7. Web Workers for Heavy Computations
-   For CPU-intensive tasks that could block the main thread and make the UI unresponsive, consider offloading them to Web Workers.

### 4.8. Caching
-   Utilize browser caching for static assets.
-   Implement data caching strategies in services for API responses that don't change frequently (see `07-http-and-data-loading.md`).

### 4.9. Environment Configuration
-   Ensure production builds (`ng build --configuration production` or `ng build`) enable all built-in optimizations (minification, tree-shaking, AOT compilation).

By combining SSR/SSG for initial delivery, `@defer` for client-side progressive rendering, and adhering to general performance best practices, Hangar Bay can achieve excellent performance and provide a smooth user experience.
