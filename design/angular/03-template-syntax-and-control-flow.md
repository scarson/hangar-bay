## AI Analysis Guidance for Cascade

This file is over 200 lines long. Unless you are only looking for a specific section, you should read the entire file, which may require multiple tool calls.

# Angular Template Syntax & Control Flow (Hangar Bay)

**Last Updated:** 2025-06-09

## 1. Introduction

Angular templates are HTML with added Angular-specific syntax that allows you to bind to component properties and events, iterate over data, conditionally render content, and more. This document details the template syntax and control flow mechanisms used in Hangar Bay, emphasizing modern built-in control flow and best practices.

Referenced from: Angular Docs, `llms-full.txt` (positions 10-12, 22)

## 2. Data Binding

Data binding is a core concept in Angular, allowing communication between your component's TypeScript logic and its HTML template.

### 2.1. Interpolation `{{ ... }}`
- **Purpose:** Renders component property values as text within the template.
- **Syntax:** `{{ expression }}`
- **Usage:** Primarily for displaying string values or simple expressions that resolve to strings.
  ```html
  <p>User Name: {{ user().name }}</p>
  <p>Total Items: {{ items().length }}</p>
  <p>Welcome, {{ getGreetingMessage() }}</p>
  ```
- **Note:** Expressions should be kept simple. Complex logic should reside in the component class.

### 2.2. Property Binding `[property]="expression"`
- **Purpose:** Sets the property of an HTML element, component, or directive to the value of a component expression.
- **Syntax:** `[targetProperty]="sourceExpression"`
- **Usage:** For binding to element properties like `id`, `src`, `href`, or custom component inputs.
  ```html
  <img [src]="imageUrl()" [alt]="imageAltText()">
  <hb-user-profile [user]="currentUser()"></hb-user-profile>
  <button [disabled]="isSaving()">Save</button>
  ```

### 2.3. Event Binding `(event)="statement"`
- **Purpose:** Listens for events on an element (e.g., click, input, submit) or custom events from child components, and executes a component method in response.
- **Syntax:** `(targetEvent)="handlerStatement()"`
- **Usage:**
  ```html
  <button (click)="onSave()">Save Profile</button>
  <input (input)="onSearchTermChange($event)">
  <hb-item-selector (itemSelected)="handleItemSelected($event)"></hb-item-selector>
  ```
- **`$event` Object:** Provides access to event-specific data (e.g., `event.target.value` for input events, or the payload emitted by a custom event).

### 2.4. Two-Way Binding `[(property)]="expression"`
- **Purpose:** Combines property binding (data flow from component to template) and event binding (data flow from template to component) into a single notation.
- **Traditional Syntax:** `[(targetProperty)]="sourceProperty"`
  - This is syntactic sugar for `[targetProperty]="sourceProperty"` and `(targetPropertyChange)="sourceProperty = $event"`.
  - Requires the child component to have an input named `targetProperty` and an output named `targetPropertyChange`.
- **Modern Approach with `model()` Signal:** The `model()` signal in components simplifies creating two-way bindable properties. See `02-component-and-directive-deep-dive.md`.
  ```html
  <!-- Using model() signal in child component 'hb-custom-input' -->
  <hb-custom-input [(value)]="searchTerm"></hb-custom-input>
  <!-- searchTerm is a writable signal in the parent component -->
  ```

### 2.5. Attribute Binding `[attr.attribute-name]="expression"`
- **Purpose:** Binds to HTML attributes directly, especially when there's no corresponding DOM element property (e.g., ARIA attributes, SVG attributes).
- **Syntax:** `[attr.attribute-name]="expression"`
- **Usage:**
  ```html
  <button [attr.aria-label]="'Close dialog'">X</button>
  <svg:rect [attr.width]="barWidth()" />
  ```

### 2.6. Class Binding `[class.class-name]="booleanExpression"`
- **Purpose:** Conditionally adds or removes a CSS class based on a boolean expression.
- **Syntax:** `[class.my-class]="isMyClassActive()"`
- **Usage:**
  ```html
  <div [class.active]="isActive()" [class.error]="hasError()">
    Status Message
  </div>
  ```
- **Multiple Classes:** Can also bind to an object: `[class]="{ 'active': isActive(), 'error': hasError() }"` or a string of classes: `[class]="'base-class ' + (isActive() ? 'active-class' : '')"`.
  However, individual `[class.name]` bindings are often clearer for multiple conditional classes.

### 2.7. Style Binding `[style.style-property]="expression"`
- **Purpose:** Sets an inline style property based on a component expression.
- **Syntax:** `[style.property-name]="expression"` (e.g., `[style.color]`, `[style.font-size.px]`).
- **Usage:**
  ```html
  <p [style.color]="isError() ? 'red' : 'green'">
    {{ statusMessage() }}
  </p>
  <div [style.width.px]="itemWidth()">Item</div>
  ```
- **Multiple Styles:** Can bind to an object: `[style]="{ 'color': textColor(), 'font-weight': fontWeight() }"`.
  Prefer component-scoped CSS or class bindings for complex styling; use style bindings for dynamic, specific cases.

## 3. Template Reference Variables `#var`
- **Purpose:** Provides a direct reference to an HTML element, component, or directive instance within the template.
- **Syntax:** `#variableName` on an element, or `#variableName="exportAsName"` for components/directives that export themselves.
- **Usage:**
  ```html
  <input #searchInput (input)="logValue(searchInput.value)" placeholder="Search...">
  <button (click)="searchInput.focus()">Focus Search</button>

  <hb-user-form #userForm (ngSubmit)="onSubmit(userForm.getFormValue())"></hb-user-form>
  <p>Form Valid: {{ userForm.isValid() }}</p>
  ```
- **Scope:** Template reference variables are scoped to the template where they are declared.

## 4. Control Flow

Angular has introduced new built-in control flow syntax starting from v17, which is the **preferred way** to handle conditional rendering and list iteration. Traditional structural directives (`*ngIf`, `*ngFor`, `*ngSwitch`) are still available and may be encountered in older code or specific scenarios.

### 4.1. Built-in Control Flow (Preferred)

These are part of the template syntax itself, not directives.

#### 4.1.1. Conditional Rendering: `@if`, `@else if`, `@else`
- **Purpose:** Conditionally renders blocks of HTML.
- **Syntax:**
  ```html
  @if (user().isLoggedIn) {
    <p>Welcome, {{ user().name }}!</p>
    <button (click)="logout()">Logout</button>
  } @else if (isLoading()) {
    <hb-spinner></hb-spinner>
  } @else {
    <p>Please log in.</p>
    <button (click)="login()">Login</button>
  }
  ```
- **Benefits:** More readable, type-safe, and better performance characteristics than `*ngIf`.

#### 4.1.2. List Rendering: `@for` (with `track`)
- **Purpose:** Iterates over a collection and renders a template for each item.
- **Syntax:**
  ```html
  <ul>
    @for (item of items(); track item.id; let i = $index, isFirst = $first, isLast = $last, isEven = $even, isOdd = $odd; empty) {
      <li [class.highlight]="isEven">{{ i + 1 }}. {{ item.name }}</li>
    } @empty {
      <li>No items found.</li>
    }
  </ul>
  ```
- **`track` Expression:** **Crucial for performance.** It helps Angular identify and update items efficiently. Always use `track` with a unique identifier for each item (e.g., `item.id`).
- **Implicit Variables:** `$index`, `$first`, `$last`, `$even`, `$odd`, `$count` are available.
- **`@empty` Block:** Renders when the collection is empty.
- **Benefits:** More efficient and ergonomic than `*ngFor`.

#### 4.1.3. Switch-Case Logic: `@switch`, `@case`, `@default`
- **Purpose:** Renders different blocks of HTML based on the value of an expression.
- **Syntax:**
  ```html
  @switch (accessLevel()) {
    @case ('admin') {
      <hb-admin-panel></hb-admin-panel>
    }
    @case ('editor') {
      <hb-editor-tools></hb-editor-tools>
    }
    @default {
      <p>Standard user view.</p>
    }
  }
  ```
- **Benefits:** Clearer syntax and better type checking than `*ngSwitch`.

### 4.2. Structural Directives (Legacy/Alternative)

These directives manipulate the DOM structure.

#### 4.2.1. `*ngIf`
- **Purpose:** Conditionally adds or removes an element from the DOM.
- **Syntax:**
  ```html
  <div *ngIf="user().isLoggedIn; else loggedOutContent">
    Welcome, {{ user().name }}!
  </div>
  <ng-template #loggedOutContent>
    <p>Please log in.</p>
  </ng-template>
  ```
- **`async` Pipe:** Often used with `*ngIf` to subscribe to observables: `<div *ngIf="user$ | async as user">{{ user.name }}</div>`.

#### 4.2.2. `*ngFor`
- **Purpose:** Repeats a template for each item in a collection.
- **Syntax:**
  ```html
  <ul>
    <li *ngFor="let item of items(); let i = index; trackBy: trackById">
      {{ i + 1 }}. {{ item.name }}
    </li>
  </ul>
  ```
- **`trackBy` Function:** Essential for performance. It's a function in the component class that returns a unique identifier for each item.
  ```typescript
  // In component.ts
  trackById(index: number, item: Item): string { return item.id; }
  ```

#### 4.2.3. `*ngSwitch`
- **Purpose:** Conditionally renders one of several templates based on a switch expression.
- **Syntax:**
  ```html
  <div [ngSwitch]="accessLevel()">
    <hb-admin-panel *ngSwitchCase="'admin'"></hb-admin-panel>
    <hb-editor-tools *ngSwitchCase="'editor'"></hb-editor-tools>
    <p *ngSwitchDefault>Standard user view.</p>
  </div>
  ```

## 5. Operators and Pipes

### 5.1. Safe Navigation Operator `?.`
- **Purpose:** Prevents null and undefined errors when accessing properties of an object that might be null or undefined.
- **Syntax:** `object?.property?.subProperty`
- **Usage:**
  ```html
  <p>User's City: {{ user()?.address?.city }}</p>
  <!-- If user() or user().address is null/undefined, evaluation stops and returns undefined. -->
  ```

### 5.2. Non-Null Assertion Operator `!.`
- **Purpose:** Tells the TypeScript compiler that an expression is not null or undefined, even if its type suggests it could be. **Use with extreme caution.**
- **Syntax:** `expression!.property`
- **Usage:** Only use when you are absolutely certain that the value will not be null or undefined at runtime. Overuse can hide bugs.
  ```html
  <!-- Use only if user() is guaranteed to be non-null here -->
  <p>User Name: {{ user()!.name }}</p>
  ```

### 5.3. Pipes `|`
- **Purpose:** Transform data in templates (e.g., formatting dates, currency, uppercasing text).
- **Syntax:** `{{ expression | pipeName : arg1 : arg2 }}`
- **Built-in Pipes:** `DatePipe`, `CurrencyPipe`, `UpperCasePipe`, `LowerCasePipe`, `DecimalPipe`, `JsonPipe`, etc.
- **`async` Pipe:** Subscribes to an Observable or Promise and returns the latest emitted value. Signals often reduce the need for `async` pipe for simple state display.
  ```html
  <p>Last Login: {{ lastLoginDate() | date:'medium' }}</p>
  <p>Price: {{ productPrice() | currency:'USD':'symbol' }}</p>
  <p>User Details (JSON): {{ user() | json }}</p>

  <!-- Async pipe example (less common with signals for direct state) -->
  <div>{{ userObservable$ | async as user; else loading }} {{ user.name }}</div>
  <ng-template #loading>Loading user...</ng-template>
  ```
- **Custom Pipes:** You can create custom pipes for reusable transformations. See `01-coding-style-guide.md` for naming.

## 6. Template Best Practices

- **Keep Logic Minimal:** Templates should primarily be for presentation. Complex logic, data manipulation, or heavy computations belong in the component class (often using `computed` signals).
- **Readability:** Format templates clearly. Use indentation and line breaks for readability.
- **Performance:**
    - Use `track` with `@for` (or `trackBy` with `*ngFor`).
    - Avoid calling functions directly in template expressions if they are computationally expensive or have side effects, as they can be called many times during change detection. Prefer binding to properties or computed signals.
- **Accessibility (A11y):** Ensure templates produce accessible HTML (semantic elements, ARIA attributes where needed).
