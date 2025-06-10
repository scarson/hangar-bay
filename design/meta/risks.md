# Hangar Bay - Risk Register

This document tracks identified risks to the Hangar Bay project, their potential impacts, and mitigation strategies.

## Risk Categories

Risks can be categorized by the primary area they affect, such as:
*   Performance
*   Security
*   Data Integrity
*   Development Velocity
*   External Dependencies
*   Usability/Accessibility
*   Operational Stability

---

## Performance Risks

### PERF-001: Memory Leak in Transitive Dependency `inflight@1.0.6`

*   **Risk Description:** The `inflight` npm package (version 1.0.6), a transitive dependency in the frontend project, is deprecated and has a known memory leak. The deprecation message explicitly states: "This module is not supported, and leaks memory. Do not use it."
*   **Potential Impact:**
    *   Increased memory consumption by the Node.js processes involved in frontend development (e.g., dev server, build process).
    *   Potential for frontend development tools to become slow or crash over time, especially during long-running sessions.
    *   Unlikely to directly impact the *production* Angular application's runtime performance in the browser, as `inflight` is typically a dev-time or build-time dependency.
*   **Affected Cross-Cutting Concern(s):** Performance (of development environment), Observability (if dev tools crash).
*   **Priority:** Medium (for development environment stability).
*   **Mitigation/Addressing Strategy:**
    1.  **Identify Dependents:** Periodically run `npm ls inflight` in `app/frontend/angular` to identify which direct dependencies are pulling in `inflight`.
    2.  **Update Parent Packages:** The primary way to resolve this is to update the direct dependencies that rely on `inflight`. As these parent packages are updated, they will hopefully transition to newer versions of their own dependencies that no longer use the problematic `inflight` version or use a fixed version.
    3.  **Monitor `npm audit`:** While `npm audit` currently reports 0 vulnerabilities, monitor its output after package updates.
*   **Current Status & Reason if Unaddressed:**
    *   Currently unaddressed directly because `inflight` is a transitive dependency. We cannot remove or replace it without changes to the packages that depend on it.
*   **Suggested Future Actions:**
    *   Regularly update direct frontend dependencies (`npm update`).
    *   If development environment performance degrades significantly, investigate `inflight`'s impact more deeply using Node.js memory profiling tools on the dev server process.
    *   Monitor issue trackers of key direct dependencies (identified via `npm ls inflight`) for discussions related to `inflight` or its alternatives.

---
<!-- Add more risks under relevant categories as they are identified -->
