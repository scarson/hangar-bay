## AI Analysis Guidance for Cascade

This file is over 200 lines long. Unless you are only looking for a specific section, you should read the entire file, which may require multiple tool calls.

# Angular Components & Directives: Deep Dive (Hangar Bay)

**Last Updated:** 2025-06-09

## 1. Introduction

This document provides an in-depth look at component and directive development within the Hangar Bay Angular project. It builds upon the high-level architectural decisions in `../angular-frontend-architecture.md` and the style conventions in `01-coding-style-guide.md`. Our primary goal is to leverage modern Angular features for creating modular, maintainable, and performant UI elements.

Key Angular AI Resource: `llms-full.txt` (positions 9-14 for components, 15-16 for directives)

## 2. Components: The Building Blocks

### 2.1. Standalone Components: The Default
- **Core Principle:** As stated in the architecture, **Standalone Components are the default** for Hangar Bay.
- **Benefits:**
    - **Simplified Dependencies:** Components declare their own dependencies (other components, directives, pipes) directly in the `imports` array of the `@Component` decorator. This eliminates the need for NgModules for most component organization.
    - **Improved Tree-Shakability:** Makes it easier for build tools to remove unused code.
    - **Enhanced Reusability:** Standalone components are easier to share and reuse across different parts of the application or in different projects.
- **Example:**
  ```typescript
  import { Component } from '@angular/core';
  import { CommonModule } from '@angular/common'; // For NgIf, NgFor, etc.
  import { MatButtonModule } from '@angular/material/button'; // Example Material component

  @Component({
    selector: 'hb-action-button',
    standalone: true,
    imports: [CommonModule, MatButtonModule], // Import necessary modules/components/pipes
    template: `
      <button mat-raised-button color="primary" (click)="onClick.emit()">
        {{ label() }}
      </button>
    `,
    styleUrls: ['./action-button.component.scss']
  })
  export class ActionButtonComponent {
    label = input.required<string>();
    onClick = output<void>();
  }
  ```

### 2.2. Inputs: Passing Data to Components

Angular offers two primary ways to define component inputs: the `input()` signal function (preferred) and the `@Input()` decorator.

#### 2.2.1. Signal Inputs (`input()`, `input.required()`)
- **Preferred Approach:** Use signal-based inputs for new components.
- **Benefits:**
    - **Reactivity:** Inputs are signals, integrating seamlessly with Angular's signal-based reactivity model.
    - **Type Safety & Explicitness:** `input.required<Type>()` clearly marks mandatory inputs.
    - **Transform Functions:** Allows transforming input values directly.
- **Usage:**
  ```typescript
  import { Component, input } from '@angular/core';

  @Component({ /* ... */ })
  export class UserProfileComponent {
    // Required input
    userId = input.required<string>();

    // Optional input with a default value
    theme = input<'light' | 'dark'>('light');

    // Optional input with a transform function
    userNameTransformed = input<string, string>('', {
      transform: (value) => value.trim().toUpperCase()
    });
  }
  ```

#### 2.2.2. Decorator Inputs (`@Input()`)
- **Usage:** May be encountered in older code or third-party libraries.
- **Considerations:**
    - Less direct integration with signals (can be converted using `toSignal`).
    - Requires manual handling for required inputs (e.g., runtime checks or assertions).
- **Example:**
  ```typescript
  import { Component, Input } from '@angular/core';

  @Component({ /* ... */ })
  export class LegacyCardComponent {
    @Input() title: string; // Optional
    @Input({ required: true }) content: string; // "required" option available since Angular 16
  }
  ```

### 2.3. Outputs: Emitting Events from Components

Similar to inputs, outputs can be defined using the `output()` signal function (preferred) or the `@Output()` decorator.

#### 2.3.1. Signal Outputs (`output()`)
- **Preferred Approach:** Use signal-based outputs for new components.
- **Benefits:**
    - **Type Safety:** `output<PayloadType>()`.
    - **Simplicity:** Clear and concise syntax.
- **Usage:**
  ```typescript
  import { Component, output } from '@angular/core';

  @Component({ /* ... */ })
  export class ItemSelectorComponent {
    itemSelected = output<string>(); // Emits the ID of the selected item
    selectionCleared = output<void>(); // Emits when selection is cleared

    selectItem(id: string) {
      this.itemSelected.emit(id);
    }

    clear() {
      this.selectionCleared.emit();
    }
  }
  ```

#### 2.3.2. Decorator Outputs (`@Output()`)
- **Usage:** May be encountered in older code.
- **Considerations:** Requires manual instantiation of `EventEmitter`.
- **Example:**
  ```typescript
  import { Component, Output, EventEmitter } from '@angular/core';

  @Component({ /* ... */ })
  export class LegacyButtonComponent {
    @Output() readonly clicked = new EventEmitter<MouseEvent>();
  }
  ```

### 2.4. Two-Way Binding: `model()` Signal
- **Preferred Approach:** Use the `model()` signal function for two-way data binding.
- **Benefits:**
    - Simplifies scenarios where a child component needs to read and update a parent's property.
    - Built on signals, providing fine-grained reactivity.
- **Usage:**
  ```typescript
  // Child Component (e.g., custom-input.component.ts)
  import { Component, model } from '@angular/core';

  @Component({
    selector: 'hb-custom-input',
    standalone: true,
    template: `<input [value]="value()" (input)="onInput($event)" />`
  })
  export class CustomInputComponent {
    value = model<string>(''); // Required model
    // value = model.required<string>(); // For required model
    // value = model<string>('initial value'); // With initial value

    onInput(event: Event) {
      this.value.set((event.target as HTMLInputElement).value);
    }
  }

  // Parent Component Template
  // <hb-custom-input [(value)]="parentProperty"></hb-custom-input>
  ```

### 2.5. Content Projection (`<ng-content>`)
- **Purpose:** Allows creating flexible components that can accept and render content provided by the parent component.
- **Single Slot:**
  ```html
  <!-- child-card.component.html -->
  <div class="card">
    <div class="card-header">{{ title() }}</div>
    <div class="card-body">
      <ng-content></ng-content> <!-- Default slot -->
    </div>
  </div>
  ```
  ```html
  <!-- parent.component.html -->
  <hb-child-card [title]="'User Details'">
    <p>This content will be projected into the card body.</p>
  </hb-child-card>
  ```
- **Multi-Slot (Named Slots):** Use the `select` attribute on `<ng-content>`.
  ```html
  <!-- advanced-panel.component.html -->
  <div class="panel">
    <div class="panel-header">
      <ng-content select="[panelTitle]"></ng-content>
    </div>
    <div class="panel-body">
      <ng-content select=".panel-content-main"></ng-content>
    </div>
    <div class="panel-footer">
      <ng-content select="[panelFooter]"></ng-content>
    </div>
  </div>
  ```
  ```html
  <!-- parent.component.html -->
  <hb-advanced-panel>
    <h2 panelTitle>My Panel Title</h2>
    <div class="panel-content-main">Main content goes here.</div>
    <button panelFooter mat-button>Close</button>
  </hb-advanced-panel>
  ```

### 2.6. View and Content Queries

Queries allow components to get references to elements or other components/directives within their template (view queries) or projected content (content queries). Signal-based queries are preferred.

#### 2.6.1. Signal Queries (`viewChild`, `viewChildren`, `contentChild`, `contentChildren`)
- **Preferred Approach:** Use signal-based queries.
- **Benefits:**
    - Reactive: The query result is a signal that updates automatically.
    - Simpler API compared to decorator-based queries, especially regarding timing (`{ static: ... }` is not needed).
- **Usage:**
  ```typescript
  import { Component, viewChild, viewChildren, ElementRef, afterNextRender } from '@angular/core';
  import { ItemComponent } from './item.component'; // Assuming ItemComponent exists

  @Component({
    selector: 'hb-item-list',
    standalone: true,
    imports: [ItemComponent],
    template: `
      <div #container>Container Div</div>
      <hb-item #firstItem></hb-item>
      <hb-item></hb-item>
    `
  })
  export class ItemListComponent {
    // Query for a single element in the view
    containerDiv = viewChild<ElementRef<HTMLDivElement>>('container');
    firstItemCmp = viewChild<ItemComponent>('firstItem'); // Can also query by component type

    // Query for multiple components in the view
    allItems = viewChildren<ItemComponent>(ItemComponent);

    constructor() {
      afterNextRender(() => { // Access query results after rendering
        if (this.containerDiv()) {
          console.log('Container div:', this.containerDiv()?.nativeElement);
        }
        console.log('All items count:', this.allItems().length);
      });
    }
  }
  ```
  - **Content Queries:** `contentChild` and `contentChildren` work similarly but query elements projected via `<ng-content>`.

#### 2.6.2. Decorator Queries (`@ViewChild`, `@ContentChild`, etc.)
- **Usage:** May be encountered in older code.
- **Considerations:**
    - Requires understanding of query timing (`{ static: true/false }`).
    - Less direct integration with signals.
- **Example:**
  ```typescript
  import { Component, ViewChild, ElementRef, AfterViewInit } from '@angular/core';

  @Component({ /* ... */ })
  export class LegacyChartComponent implements AfterViewInit {
    @ViewChild('chartCanvas', { static: true }) chartCanvas: ElementRef<HTMLCanvasElement>;

    ngAfterViewInit() {
      // Access chartCanvas here
    }
  }
  ```

### 2.7. Component Lifecycle Hooks
- **Purpose:** Allow tapping into key moments in a component's lifecycle (creation, updates, destruction).
- **Common Hooks:**
    - `constructor()`: Dependency injection, initial property setup (avoid heavy logic).
    - `ngOnInit()`: Initialization logic after inputs are set (less critical with signal inputs which are available earlier).
    - `ngAfterViewInit()`: After component's view and child views are initialized (often used with decorator-based `@ViewChild`). `afterNextRender` or `afterRender` are preferred for signal components.
    - `ngOnDestroy()`: Cleanup logic (unsubscribe observables, detach event listeners, clear timers/intervals).
- **Signal-based Lifecycle:**
    - `afterNextRender()`: Executes once after the next change detection cycle. Good for one-time DOM interactions.
    - `afterRender()`: Executes after every change detection cycle. Use with caution due to performance implications.
    - `effect()`: Can be used for reactions to state changes, often replacing some lifecycle logic. Ensure effects are cleaned up if they create subscriptions or long-lived resources.
- **`OnDestroy` is Crucial:** Always implement `OnDestroy` to clean up subscriptions and prevent memory leaks, especially when using RxJS observables manually or effects that need explicit cleanup.
  ```typescript
  import { Component, OnInit, OnDestroy, effect, inject } from '@angular/core';
  import { SomeService } from './some.service';
  import { Subscription } from 'rxjs';

  @Component({ /* ... */ })
  export class DataDisplayComponent implements OnInit, OnDestroy {
    private someService = inject(SomeService);
    private dataSubscription: Subscription;

    constructor() {
      // Example of an effect that might need cleanup if it registered global listeners, etc.
      // For simple signal-based reactions, explicit cleanup is often not needed if the effect
      // only depends on signals within the component's scope.
      effect(() => {
        console.log('User ID changed:', this.someService.userId());
      });
    }

    ngOnInit() {
      this.dataSubscription = this.someService.getData().subscribe(data => {
        // ... process data
      });
    }

    ngOnDestroy() {
      if (this.dataSubscription) {
        this.dataSubscription.unsubscribe();
      }
    }
  }
  ```

## 3. Directives: Modifying Behavior and Structure

Directives are used to add behavior to elements or transform the DOM structure.

### 3.1. Attribute Directives
- **Purpose:** Change the appearance or behavior of an element, component, or another directive.
- **Usage:** Applied as attributes to elements.
- **Example (`hbHighlight` directive):**
  ```typescript
  // highlight.directive.ts
  import { Directive, ElementRef, HostListener, Input, inject } from '@angular/core';

  @Directive({
    selector: '[hbHighlight]',
    standalone: true,
  })
  export class HighlightDirective {
    private el = inject(ElementRef);
    @Input('hbHighlight') highlightColor: string = 'yellow'; // Alias input to directive selector

    @HostListener('mouseenter') onMouseEnter() {
      this.highlight(this.highlightColor || 'yellow');
    }

    @HostListener('mouseleave') onMouseLeave() {
      this.highlight(''); // Or original color
    }

    private highlight(color: string) {
      this.el.nativeElement.style.backgroundColor = color;
    }
  }

  // Usage in a component template
  // <p [hbHighlight]="'lightblue'">Highlight me on hover!</p>
  // <p hbHighlight>Highlight me with default yellow!</p>
  ```

### 3.2. Structural Directives
- **Purpose:** Shape or reshape the DOM's structure, typically by adding, removing, or manipulating elements.
- **Prefix:** Structural directive selectors are prefixed with an asterisk (`*`) as syntactic sugar for a more complex `<ng-template>` expansion.
- **Common Examples:** `*ngIf`, `*ngFor`, `*ngSwitch`.
- **Creating Custom Structural Directives:** Involves `TemplateRef` and `ViewContainerRef`. This is an advanced topic.
  - **`TemplateRef`:** Represents the embedded template (the content the directive is applied to).
  - **`ViewContainerRef`:** Represents the container where the template can be instantiated.
- **Example (Simplified `*hbDelayRender`):**
  ```typescript
  // delay-render.directive.ts
  import { Directive, Input, TemplateRef, ViewContainerRef, inject } from '@angular/core';

  @Directive({
    selector: '[hbDelayRender]',
    standalone: true,
  })
  export class DelayRenderDirective {
    private templateRef = inject(TemplateRef<any>);
    private viewContainer = inject(ViewContainerRef);

    @Input('hbDelayRender') set delay(ms: number) {
      this.viewContainer.clear();
      setTimeout(() => {
        this.viewContainer.createEmbeddedView(this.templateRef);
      }, ms);
    }
  }

  // Usage in a component template
  // <div *hbDelayRender="1000">This content will render after 1 second.</div>
  ```

## 4. Best Practices for Components and Directives

- **Single Responsibility Principle (SRP):** Keep components and directives focused on a single task or piece of functionality.
- **Reusability:** Design for reusability where appropriate. Parameterize with inputs and emit events with outputs.
- **Performance:**
    - Use `OnPush` change detection strategy (less critical with signal components, as signals manage fine-grained updates).
    - Be mindful of expensive computations in templates or lifecycle hooks.
    - Optimize list rendering with `trackBy` (for `*ngFor`) or `track` (for `@for`).
- **Accessibility (A11y):** Ensure components are accessible (ARIA attributes, keyboard navigation, etc.).
- **Testing:** Write unit tests for component logic and interaction.
- **Clear API:** Define a clear and concise public API for your components and directives (inputs, outputs, public methods).
