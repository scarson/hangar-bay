# Hangar Bay - Internationalization (i18n) Specification

## 1. Introduction and Goals

Internationalization (i18n) is the process of designing and developing Hangar Bay in a way that enables easy localization for different languages and regions without engineering changes. While the initial primary language will be English (en), incorporating i18n from the outset is crucial for future scalability, broader user accessibility, and reaching EVE Online's global player base.

**AI Coding Assistant Goal:** Ensure all user-facing text is externalized and handled through i18n mechanisms. Implement locale-aware formatting and support language switching.

## 2. Core i18n Principles

*   **Externalize Strings:** All user-interface text (labels, buttons, messages, errors, etc.) must be stored in external resource files (e.g., `.xlf` for Angular, `.po` for Python/FastAPI), not hardcoded in the application code.
*   **Locale-Aware Formatting:** Dates, times, numbers, and currencies must be formatted according to the user's selected locale. (Note: EVE Online's currency, ISK, may have a standard representation, but general numeric formatting still applies).
*   **UTF-8 Encoding:** All text data, including source files, database content, and API communications, must use UTF-8 encoding.
*   **UI Adaptability:** Design UIs to accommodate varying text lengths and directions (though Right-to-Left (RTL) is a future consideration, not MVP). Use flexible layouts.
*   **Language Selection:** Provide a user-friendly mechanism for language selection and persistence of this choice.
*   **Default Application Language:** English (`en`) will be the default and fallback language for application-generated UI text.
*   **Default ESI API Fallback Language:** `en-us` is the designated fallback language when requesting localized data from the EVE ESI API if the user's preferred language is not supported by ESI for a given endpoint.

## 3. AI Actionable Checklists & Implementation Patterns

### 3.1. Backend (FastAPI)

**Technology Choice: Babel (with `fastapi-babel` and `pybabel`)**

While other libraries like `python-i18n` offer simplicity, Babel was chosen for Hangar Bay due to its robustness, comprehensive feature set, strong framework integration, and mature tooling, which are better suited for a project aiming for a global audience and requiring reliable, scalable localization.

*   **Babel Advantages for Hangar Bay:**
    *   **Industry Standard & Rich Features:** Based on `gettext`, providing excellent support for complex pluralization rules and locale-specific formatting.
    *   **Strong FastAPI Integration:** `fastapi-babel` offers seamless integration (e.g., locale detection, request-scoped translations).
    *   **Powerful Tooling:** `pybabel` CLI for automated string extraction and compilation, facilitating AI-assisted development.
    *   **Scalability & Maintainability:** Well-suited for larger applications and managing many languages.
*   **`python-i18n` (Considered but Not Selected):**
    *   **Pros:** Simpler for basic needs, flexible translation formats (YAML, JSON).
    *   **Cons for Hangar Bay:** Limited advanced features, more manual string management, potentially more boilerplate for deep FastAPI integration.

**AI Actionable Checklist:**

*   [ ] Integrate `fastapi-babel` for i18n support.
*   [ ] Configure `Babel` with supported locales (initially `en`, placeholder for `de`, `fr`, `ja`, `ru`, `zh`).
*   [ ] Ensure all user-facing strings returned by API endpoints (e.g., error messages, status messages) are translatable using `_()` or `gettext()` from Babel.
*   [ ] Extract translatable strings into `.po` files using `pybabel extract`.
*   [ ] Compile translations into `.mo` files using `pybabel compile`.
*   [ ] Implement locale determination from `Accept-Language` HTTP header and/or a user profile setting (if available).
*   [ ] Ensure database schemas and interactions correctly handle UTF-8 encoded text.

**AI Implementation Pattern (FastAPI Error Message):**

```python
# Example: app/exceptions.py
from fastapi import HTTPException, status
from fastapi_babel import _ # Assuming Babel integration

class ItemNotFoundException(HTTPException):
    def __init__(self, item_id: int):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_("Item with ID {item_id} not found.").format(item_id=item_id)
        )

# AI: When defining custom exceptions or direct error responses,
# AI: ensure the 'detail' message is wrapped with `_()` for translation.
```

### 3.2. Frontend (Angular)

**AI Actionable Checklist:**

*   [ ] Initialize Angular's built-in i18n (`@angular/localize`) for the project.
*   [ ] Mark all translatable text in HTML templates with the `i18n` attribute.
    *   For attributes, use `i18n-attributeName` (e.g., `i18n-title`, `i18n-aria-label`).
*   [ ] For strings in component TypeScript code, prepare them for extraction (e.g., by using `$localize` tagged template literals if needed, though template-driven is preferred).
*   [ ] Extract translatable strings into XLIFF (`.xlf`) files using `ng extract-i18n`.
*   [ ] Configure `angular.json` for different locale builds (e.g., `en`, `de`).
*   [ ] Implement a language switcher component that allows users to select their preferred language.
*   [ ] Ensure the selected language preference is persisted (e.g., in `localStorage` or user profile).
*   [ ] Dynamically set the `lang` attribute on the `<html>` tag based on the current locale.
*   [ ] Use Angular pipes for locale-aware formatting: `DatePipe`, `CurrencyPipe`, `DecimalPipe`, `PercentPipe`.

**AI Implementation Pattern (Angular Template):**

```html
<!-- Example: src/app/components/some-component/some-component.html -->
<div>
  <h1 i18n="Page title for user dashboard|Meaning: Main heading on the dashboard@@userDashboardTitle">User Dashboard</h1>
  <p i18n="Welcome message for the user|Meaning: A friendly greeting@@welcomeUserMessage">Welcome to Hangar Bay!</p>
  <button i18n-title="Button hint for logout|Meaning: Tooltip for logout button@@logoutButtonTitle" i18n="Logout button text|Meaning: Text on the button to log out@@logoutButton">Log Out</button>
  
  <p i18n="Item count display|Meaning: Shows how many items are available@@itemCount">You have {itemCount, plural, =0 {no items} =1 {one item} other {# items}}.</p>
  <p>Last login: {{ lastLoginDate | date:'medium' }}</p>
</div>

<!-- AI: Use 'i18n' attribute for all static text elements. -->
<!-- AI: Provide a description and a custom ID (e.g., 'userDashboardTitle') for clarity and stability. -->
<!-- AI: Use ICU expressions for plurals and selections within i18n blocks. -->
<!-- AI: Use Angular's date/number/currency pipes for dynamic data formatting. -->
```

### 3.3. Data Handling (ESI vs. Application-Specific)

**AI Actionable Checklist:**

*   [ ] **ESI Data:**
    *   [ ] When making ESI API calls for localized data (e.g., item names, descriptions), include the `language` query parameter corresponding to the user's selected Hangar Bay locale (e.g., `en-us`, `de`, `fr`, `ja`, `ru`, `zh-cn`). Map Hangar Bay locales to ESI supported locales. The primary ESI language to target is `en-us`.
    *   [ ] If ESI does not support a user's selected locale for a specific endpoint/data, fall back gracefully to the **default ESI language `en-us`**. Ensure this fallback mechanism is robust.
    *   [ ] Clearly indicate if displayed ESI data is not available in the user's selected language.
*   [ ] **Application-Specific Data:**
    *   [ ] Ensure all text generated and stored by Hangar Bay (e.g., user-defined tags, saved search names - if these become features) that might need translation is designed with i18n in mind (e.g., by not storing user-generated text that is then presented to *other* users as if it were UI text).
    *   [ ] UI elements, labels, and messages generated by Hangar Bay itself are primary candidates for translation using the mechanisms in 3.1 and 3.2.

### 3.4. UI/Layout Considerations

**AI Actionable Checklist:**

*   [ ] Use flexible and responsive layout techniques (e.g., CSS Flexbox, Grid) that can adapt to varying text lengths without breaking the UI.
*   [ ] Avoid fixed-width containers for text elements where possible.
*   [ ] Test UI with pseudo-localization (e.g., longer strings, special characters) to identify potential layout issues early.
*   [ ] Ensure interactive elements (buttons, links) remain usable and accessible when text length changes.

## 4. Integration with Accessibility (`accessibility-spec.md`)

**AI Actionable Checklist:**

*   [ ] Ensure the `<html>` element's `lang` attribute is dynamically updated to reflect the current page language. (Covered in Angular checklist).
*   [ ] All `aria-label`, `aria-labelledby`, `aria-describedby`, and `title` attributes containing translatable text must be processed by the i18n system.
    *   *Pattern:* In Angular, use `i18n-aria-label`, `i18n-title`, etc.
*   [ ] Text alternatives for images (`alt` text) must be translatable.
*   [ ] Ensure that changing language does not negatively impact keyboard navigation or focus management.

## 5. Testing i18n

Refer to `test-spec.md` for overall testing strategy. i18n-specific tests should include:

**AI Actionable Checklist:**

*   [ ] **Translation Verification:** Test that all strings are correctly translated for each supported locale (can be partially automated by checking for missing translations, but requires human review for quality).
*   [ ] **Locale Formatting:** Verify that dates, times, numbers, and currencies are displayed correctly according to the selected locale.
*   [ ] **UI Adaptability:** Test UIs with different languages (especially those known for longer text) to ensure layouts do not break.
*   [ ] **Language Switching:** Test the language selection mechanism and persistence of the selected language.
*   [ ] **ESI Data Localization:** Verify that data fetched from ESI respects the language parameter and fallbacks work as expected.
*   [ ] **Accessibility with i18n:** Ensure `lang` attribute updates and translatable ARIA attributes function correctly.

## 6. Tooling

*   **Backend (FastAPI):** `Babel`, `fastapi-babel`
*   **Frontend (Angular):** `@angular/localize`, `ng extract-i18n`
*   **Translation Management:** (Future) Consider tools like Weblate, Crowdin, or Transifex if manual `.xlf`/`.po` file management becomes cumbersome.

## 7. Future Considerations

*   Right-to-Left (RTL) language support (e.g., Arabic, Hebrew).
*   Adding more languages based on user demand.
*   Regional locale variations (e.g., `en-US` vs. `en-GB`).

---
*AI: This specification provides the guidelines for implementing internationalization in Hangar Bay. Ensure all new and existing user-facing components and text adhere to these principles.*
