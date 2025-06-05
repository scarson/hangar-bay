# Hangar Bay - Accessibility Specification (A11y)

## 1. Introduction & Philosophy

This document outlines the accessibility standards and guidelines for the Hangar Bay application. Accessibility (A11y) is a core requirement, ensuring that the application is usable by people with a wide range of disabilities, including visual, auditory, motor, and cognitive impairments.

Our goal is to create an inclusive experience. This specification will guide development, particularly for AI-assisted coding, to build accessibility in from the start, rather than as an afterthought.

**Guiding Principle:** All users, regardless of ability, should be able to perceive, understand, navigate, and interact with Hangar Bay effectively.

## 2. Conformance Target

*   **Minimum Standard:** Hangar Bay MUST meet **Web Content Accessibility Guidelines (WCAG) 2.1 Level AA** conformance.
*   **Aspiration:** Where feasible and beneficial, strive for Level AAA criteria, particularly if they significantly improve usability for a broad range of users without imposing undue burdens.

## 3. General Principles (POUR)

Development MUST adhere to the four core principles of accessibility (POUR):

### 3.1. Perceivable

Information and user interface components must be presentable to users in ways they can perceive.

*   **Text Alternatives (WCAG 1.1):**
    *   Provide text alternatives (e.g., `alt` attributes) for all non-text content (images, icons, charts). Decorative images should have empty `alt=""`.
    *   AI Guidance: When generating image tags or icon components, always include a prop or slot for descriptive `alt` text. If an image is purely decorative, ensure the AI can designate it as such.

        *   **AI Actionable Checklist (Text Alternatives):**
            *   [ ] For `<img>` tags, ensure `alt` attribute is present.
            *   [ ] If image is decorative, `alt=""`.
            *   [ ] If image conveys information, `alt` describes the information.
            *   [ ] For icon fonts or SVG icons, ensure `aria-label` or visually hidden text provides a text alternative.
*   **Time-Based Media (WCAG 1.2):** (Currently not planned, but if introduced)
    *   Provide captions for pre-recorded audio content.
    *   Provide audio descriptions for pre-recorded video content.
*   **Adaptable (WCAG 1.3):**
    *   Create content that can be presented in different ways (e.g., simpler layout) without losing information or structure.
    *   **Semantic HTML:** Use HTML5 elements according to their semantic meaning (`<nav>`, `<main>`, `<article>`, `<aside>`, `<header>`, `<footer>`, `<button>`, `<a>` for navigation vs. actions, etc.).
    *   **ARIA Roles & Attributes:** Use Accessible Rich Internet Applications (ARIA) roles and attributes to define UI components (e.g., `role="dialog"`, `aria-label`, `aria-describedby`, `aria-expanded`, `aria-hidden`) when semantic HTML alone is insufficient, especially for dynamic content and custom Angular components.
        *   AI Guidance: For custom components, prompt for necessary ARIA attributes based on the component's function and state.

        *   **AI Implementation Pattern (Semantic HTML & ARIA):**
            *   Prioritize standard HTML elements: `<button>`, `<nav>`, `<a>`, `<input>`, etc.
            *   When creating custom Angular components that mimic standard controls (e.g., a custom dropdown), ensure appropriate `role` (e.g., `role="combobox"`, `role="listbox"`) and necessary ARIA states/properties (`aria-expanded`, `aria-selected`, `aria-owns`) are applied and dynamically updated.
    *   **Meaningful Sequence:** Ensure reading and navigation order is logical and intuitive.
*   **Distinguishable (WCAG 1.4):**
    *   Make it easier for users to see and hear content including separating foreground from background.
    *   **Color Contrast:** Minimum contrast ratios: 4.5:1 for normal text, 3:1 for large text (18pt or 14pt bold) and graphical objects/UI components. Use tools to verify.
    *   **Avoid Color Alone:** Do not use color as the sole means of conveying information, indicating an action, prompting a response, or distinguishing a visual element.
    *   **Text Resizing:** Text should be resizable up to 200% without loss of content or functionality.
    *   **Visual Presentation:** Provide sufficient spacing between lines and paragraphs. Avoid fully justified text.

        *   **AI Actionable Checklist (Distinguishable):**
            *   [ ] Verify text color contrast against background is at least 4.5:1 (3:1 for large text).
            *   [ ] Verify UI component/graphical object contrast is at least 3:1.
            *   [ ] Ensure information is not conveyed by color alone (e.g., error states also use icons/text).
            *   [ ] Test text resizing up to 200% without loss of content/functionality.

### 3.2. Operable

User interface components and navigation must be operable.

*   **Keyboard Accessible (WCAG 2.1):**
    *   All functionality MUST be operable through a keyboard interface without requiring specific timings for individual keystrokes.
    *   **No Keyboard Traps:** Ensure the keyboard focus can be moved away from any component using only the keyboard.
    *   **Visible Focus:** Keyboard focus indicators MUST be clearly visible and distinguishable.
        *   AI Guidance: Ensure CSS for focus states (`:focus`, `:focus-visible`) provides a strong visual cue.

        *   **AI Implementation Pattern (Visible Focus):**
            *   Define a clear, high-contrast focus outline/style for all interactive elements using `:focus-visible` to avoid styling non-keyboard focus where appropriate.
            *   Example CSS: `*:focus-visible { outline: 2px solid blue; outline-offset: 2px; }` (Adjust color/style to fit design).
*   **Enough Time (WCAG 2.2):** Provide users enough time to read and use content (e.g., for session timeouts, offer ways to extend).
*   **Seizures and Physical Reactions (WCAG 2.3):** Do not design content in a way that is known to cause seizures (e.g., no flashing content more than three times per second).
*   **Navigable (WCAG 2.4):**
    *   Provide ways to help users navigate, find content, and determine where they are.
    *   **Bypass Blocks:** Implement mechanisms like "skip to main content" links.
    *   **Page Titles:** Use clear and descriptive `<title>` elements for each page.
    *   **Link Purpose (In Context):** The purpose of each link should be clear from its text or its surrounding context.
    *   **Headings and Labels:** Use headings (`<h1>`-`<h6>`) to organize content logically. Provide clear labels for form inputs.

        *   **AI Actionable Checklist (Navigable):**
            *   [ ] Implement a "Skip to main content" link.
            *   [ ] Ensure all pages have unique and descriptive `<title>` elements.
            *   [ ] Verify link text clearly describes its purpose or destination.
            *   [ ] Check for logical heading structure (`<h1>` for main title, `<h2>` for major sections, etc.).
            *   [ ] Ensure all form inputs have associated `<label>` elements.

### 3.3. Understandable

Information and the operation of user interface must be understandable.

*   **Readable (WCAG 3.1):** Make text content readable and understandable (e.g., specify page language `lang="en"`).
*   **Predictable (WCAG 3.2):** Make web pages appear and operate in predictable ways.
    *   Consistent navigation and identification of components.
*   **Input Assistance (WCAG 3.3):** Help users avoid and correct mistakes.
    *   **Error Identification:** Clearly identify and describe input errors in text.
    *   **Labels or Instructions:** Provide labels or instructions for user inputs.
    *   **Error Prevention:** For sensitive actions (e.g., deletions), provide confirmation steps.

        *   **AI Implementation Pattern (Input Assistance - Angular Forms):**
            *   Associate error messages with form controls using `aria-describedby`.
            *   Set `aria-invalid="true"` on controls with errors.
            *   Provide clear, textual error messages next to the invalid field or in a summary.
            *   Example: `<input [formControl]="myControl" [attr.aria-describedby]="myControlError ? 'myControlErrorId' : null" [attr.aria-invalid]="myControl.invalid && myControl.touched">
                      <div id="myControlErrorId" *ngIf="myControl.invalid && myControl.touched">Error message here</div>`

### 3.4. Robust

Content must be robust enough that it can be interpreted reliably by a wide variety of user agents, including assistive technologies.

*   **Parsing (WCAG 4.1):** Ensure HTML is well-formed with complete start/end tags, nested correctly, and no duplicate IDs.
*   **Name, Role, Value (WCAG 4.1.2):** For all UI components (including custom Angular components), their name and role can be programmatically determined; states, properties, and values that can be set by the user can be programmatically set; and notification of changes is available to assistive technologies.

    *   **AI Actionable Checklist (Name, Role, Value):**
        *   [ ] For custom interactive components, ensure `role` is appropriate (e.g., `button`, `checkbox`, `tab`).
        *   [ ] Ensure components have an accessible name (via `aria-label`, `aria-labelledby`, or content).
        *   [ ] Ensure states (e.g., `aria-checked`, `aria-selected`, `aria-expanded`) are programmatically set and updated.
        *   [ ] Ensure values (e.g., `aria-valuenow` for sliders) are programmatically set and updated.

## 4. Technology-Specific Guidance (Angular)

*   **Angular Material / CDK:** Leverage built-in accessibility features of Angular Material components and the Component Dev Kit (CDK). Many components are designed with A11y in mind (e.g., `MatDialog`, `MatMenu`).
    *   AI Guidance: When using Angular Material, prefer its components over custom-built ones if they meet functional requirements, due to their built-in A11y.

        *   **AI Implementation Pattern (Angular Material):**
            *   When AI is tasked to create UI for forms, dialogs, menus, tables, etc., explicitly instruct it to use the corresponding Angular Material component (`MatInput`, `MatDialog`, `MatMenu`, `MatTable`) unless a custom solution is strictly necessary and its A11y can be guaranteed.
*   **ARIA Attributes in Components:** Dynamically bind ARIA attributes in Angular components based on component state (e.g., `[attr.aria-expanded]="isExpanded"`).

    *   **AI Implementation Pattern (Dynamic ARIA):**
        *   AI should generate code like: `<button [attr.aria-expanded]="isMenuOpen" (click)="toggleMenu()">Menu</button>`
        *   Ensure boolean values for ARIA states are correctly translated to string attributes 'true'/'false'.
*   **Focus Management:** Use Angular's `Renderer2` or the CDK's `FocusTrap` and `FocusMonitor` for managing focus in dynamic UIs, modals, and custom components.

    *   **AI Implementation Pattern (CDK FocusTrap):**
        *   For modal dialogs or similar overlay components: `<div cdkTrapFocus *ngIf="isModalOpen">...modal content...</div>`
        *   Instruct AI to import `A11yModule` and use `cdkTrapFocus` when creating modal-like experiences.
*   **Live Announcers:** Use `LiveAnnouncer` from `@angular/cdk/a11y` to announce changes to assistive technologies for dynamic content updates that don't shift focus.

    *   **AI Implementation Pattern (LiveAnnouncer):**
        *   Inject `LiveAnnouncer`: `constructor(private liveAnnouncer: LiveAnnouncer) {}`
        *   Announce message: `this.liveAnnouncer.announce("Item successfully added to cart", "polite");`
        *   Instruct AI to use this for status messages, search result updates, etc., that don't involve a page reload or focus shift.
*   **Router:** Ensure route changes announce page titles or main headings to screen readers.
*   **Forms:** Use Angular's reactive or template-driven forms with proper labeling (`<label for>`), error messages associated with inputs (`aria-describedby`), and validation states (`aria-invalid`).

    *   **AI Actionable Checklist (Angular Forms A11y):**
        *   [ ] Each form control (`<input>`, `<select>`, `<textarea>`) has an associated `<label>` (use `for` attribute linking to control's `id`).
        *   [ ] Error messages are linked to controls via `aria-describedby`.
        *   [ ] `aria-invalid` is set to `true` on invalid controls.
        *   [ ] Required fields are indicated with `aria-required="true"` or visually (e.g., asterisk) with a note.
        *   [ ] Group related controls using `<fieldset>` and `<legend>` where appropriate.

## 5. Testing & Validation

*   **Automated Tools:** Use tools like Axe-core (e.g., via `@axe-core/angular`), Lighthouse, and browser extensions during development and in CI/CD pipelines.
*   **Manual Testing:**
    *   **Keyboard-Only Navigation:** Test all interactive elements and user flows.
    *   **Screen Reader Testing:** Test with common screen readers (e.g., NVDA, JAWS, VoiceOver).
    *   **Zoom & Reflow:** Test up to 200% zoom and with browser reflow for small screens.
    *   **Color Contrast Checkers:** Use tools to verify color contrast.
*   **User Feedback:** Incorporate feedback from users with disabilities if possible.

## 6. Documentation & Training

*   Accessibility considerations should be part of component documentation.
*   AI coding assistants should be prompted/trained to consider these guidelines proactively.

## 7. Continuous Improvement

Accessibility is an ongoing effort. Regularly review and update practices as standards evolve and new insights are gained.

*(This document should be referenced by `design-spec.md`, `test-spec.md`, and individual feature specifications where UI/UX is involved.)*
