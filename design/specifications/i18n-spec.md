# Hangar Bay - Internationalization (i18n) Specification

## 1. Introduction and Goals

Internationalization (i18n) is the process of designing and developing Hangar Bay in a way that enables easy localization for different languages and regions without engineering changes. While the initial primary language will be English (en), incorporating i18n from the outset is crucial for future scalability, broader user accessibility, and reaching EVE Online's global player base.

**AI Coding Assistant Goal:** Ensure all user-facing text is externalized and handled through i18n mechanisms. Implement locale-aware formatting and support language switching.

> **Milestone-1 status (2026-07):** The React rebuild ships **hardcoded English strings by explicit decision** (see the Milestone-1 spec's Non-goals). No i18n runtime is wired into the frontend yet. The externalization requirements in this document remain the target and MUST be revisited before any feature milestone; the frontend implementation guidance below (originally written for Angular) is superseded and will be re-specified for React when i18n work is scheduled. The framework-agnostic principles and the backend (FastAPI/Babel) guidance still apply.

## 2. Core i18n Principles

*   **Externalize Strings:** All user-interface text (labels, buttons, messages, errors, etc.) must be stored in external resource files (e.g., `.po` for Python/FastAPI, a message catalog for the frontend), not hardcoded in the application code.
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

### 3.2. Frontend (React)

> **Deferred in Milestone 1 (see the status note in Section 1).** The frontend currently ships hardcoded English strings and wires no i18n runtime. When i18n is scheduled, this section will specify the React approach — a message-catalog library, locale-aware `Intl` formatting for dates/numbers/currency, a language switcher with a persisted preference, and a dynamically-set `<html lang>` attribute. The original Angular i18n tooling guidance no longer applies.

The framework-agnostic requirement stands: **all user-facing strings must be externalizable.** Do not bury hardcoded copy in ways that make later extraction impractical, and keep locale-aware formatting (dates, numbers, currency) going through `Intl`/a formatting layer rather than hand-rolled string concatenation, so the eventual i18n retrofit is mechanical rather than a rewrite.

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

*   [ ] Ensure the `<html>` element's `lang` attribute is dynamically updated to reflect the current page language. (To be handled by the frontend i18n approach when scheduled — see Section 3.2.)
*   [ ] All `aria-label`, `aria-labelledby`, `aria-describedby`, and `title` attributes containing translatable text must be processed by the i18n system (framework-agnostic requirement; the React mechanism is TBD — see Section 3.2).
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
*   **Frontend (React):** deferred in Milestone 1 (see the Section 1 status note); a message-catalog library plus `Intl` formatting to be selected when i18n is scheduled.
*   **Translation Management:** (Future) Consider tools like Weblate, Crowdin, or Transifex if manual `.po`/message-catalog file management becomes cumbersome.

## 7. Future Considerations

*   Right-to-Left (RTL) language support (e.g., Arabic, Hebrew).
*   Adding more languages based on user demand.
*   Regional locale variations (e.g., `en-US` vs. `en-GB`).

---
*AI: This specification provides the guidelines for implementing internationalization in Hangar Bay. Ensure all new and existing user-facing components and text adhere to these principles.*
