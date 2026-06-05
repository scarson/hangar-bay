# Frontend Payload / Startup / Build Audit — Hangar Bay Angular SPA

**Date:** 2026-06-05
**Lane:** frontend-payload-startup (payload / startup / build dimension)
**Scope:** `/home/user/hangar-bay/app/frontend/angular` — Angular 20 standalone, zoneless, `@angular/build` (esbuild/application builder).
**Mode:** STATIC-ONLY. No `ng build` was run; byte estimates are heuristic.

## Context / posture

This is an early-stage SPA. `app.routes.ts` is `routes = []` — **no routes, no lazy-loading, no eagerly-routed feature components yet**. The bootstrap path is `main.ts → bootstrapApplication(AppComponent)` where `AppComponent` imports only `RouterOutlet`. There is essentially nothing in the initial bundle beyond the Angular framework runtime (core + router + http + platform-browser) plus the `@angular/localize/init` polyfill.

The build posture is mostly the clean Angular 20 default and is reasonable: production is the default configuration; `optimization`/minification/tree-shaking are on by default for the `@angular/build:application` builder (only explicitly *disabled* in the `development` config); `outputHashing: "all"` is set; source maps are off in production (only enabled under `development`); `importHelpers: true` + `tslib` keeps TS helpers deduped; `target: ES2022` is modern (no legacy polyfill bloat); zoneless change detection is enabled, so the ~14 kB Zone.js payload is **not** shipped. No `@angular/cdk` or `@angular/material` is actually imported anywhere in `src` (confirmed by grep), so neither lands in the bundle despite `@angular/cdk` being a declared dependency.

Against the stated budgets (initial < 500 kB, lazy < 200 kB), the current initial bundle is almost certainly well under 500 kB. The findings below are config-posture gaps and latent risks that fire as features get wired in, plus one real eager-payload item shipping today.

---

### [MINOR impact] `@angular/localize/init` polyfill ships eagerly with zero `$localize` usage in the codebase

**Location:** `angular.json:37-39` (`"polyfills": ["@angular/localize/init"]`), also `src/main.ts:1` and `tsconfig.app.json:7-9` (`types: ["@angular/localize"]`)
**Problem:** `@angular/localize/init` is registered as a build polyfill, meaning it is bundled into the initial/main chunk unconditionally and executed at startup (it installs the global `$localize` function). A repo-wide grep for `$localize` / `i18n` / `localize` usage finds **only** the type reference comment in `main.ts:1` and the type/polyfill registrations themselves — no template `i18n` attributes, no `$localize` tagged-template calls, no localized messages anywhere in `src`. The app is not actually internationalized yet, so the polyfill is dead weight in the initial bundle today.
**Impact:** The `@angular/localize/init` runtime adds roughly ~10-15 kB minified to the initial bundle (heuristic; the localize polyfill is one of the larger Angular polyfills). On a SPA whose initial bundle is otherwise just framework runtime, this is a measurable fraction of startup payload that delivers no current feature, and it executes during bootstrap before first paint. Small in absolute terms vs the 500 kB initial budget, but it is pure waste until i18n is actually adopted.
**Confidence:** Strong-static (the polyfill registration and the absence of any `$localize`/`i18n` usage are both directly verifiable in-tree). Heuristic only on the exact byte figure.
**Effort:** Localized — remove the polyfill entry from `angular.json` (and the matching entry in the `test` target), the `types` entry in `tsconfig.app.json`, and the `/// <reference>` in `main.ts`; re-add when i18n work begins. Note it is also duplicated in the `test` builder options (`angular.json:108-110`).
**Verification plan:** `ng build --configuration production` and compare main-chunk size in the build stats before/after removal; confirm no `$localize` references remain (`grep -rn '\$localize\|i18n=' src`); guard: app still boots (`ng serve`) and `ng test` passes, since nothing references the localize runtime.

---

### [MINOR impact] No lazy-loading / code-splitting convention established for the feature that already exists

**Location:** `src/app/app.routes.ts:3` (`routes = []`); existing un-routed feature at `src/app/features/contracts/` (`contract-search.ts`, `contract.api.ts`, `contract-filter.resolver.ts`)
**Problem:** A `contracts` feature already exists in `src/app/features/contracts/` but is not wired into any route. When it (and future features) get added, the routing table is the single point that decides eager vs. lazy. There is currently no `loadComponent`/`loadChildren` convention in place and no example to copy. The risk is that, with an empty `routes` array as the only precedent, the first feature wired in gets added as an eager component import on a top-level route (or imported directly into `AppComponent`), pulling its entire dependency graph — including the `ContractSearch` service's RxJS operator chain and the contracts API/model code — into the initial bundle instead of a per-route lazy chunk. The project's own budget model (lazy modules < 200 kB) presumes route-level splitting that does not yet exist.
**Impact:** Latent. Fires once features are wired in: each feature added eagerly instead of via `loadComponent` adds its full graph to the initial bundle, eroding the 500 kB initial budget and pushing TTI/FCP toward the 1.8 s / 5 s ceilings. With lazy routes, the same code lands in a < 200 kB per-route chunk loaded on demand. Zero impact at this exact moment because `routes` is empty.
**Confidence:** Heuristic — this is an architecture-posture gap, not a shipping regression; the magnitude depends entirely on how features are added.
**Effort:** Contained — establish the convention now: lazy `loadComponent` routes for feature roots, reserving eager imports for the shell only. Cheap to set as a pattern with the first route; cross-cutting to retrofit if eager imports proliferate first.
**Verification plan:** When the first feature route is added, confirm via `ng build` stats that a separate lazy chunk is emitted for `features/contracts` (it should appear as its own hashed chunk, not folded into `main`); a bundle analyzer (e.g. `esbuild-visualizer` / `source-map-explorer` on the prod build) confirms contracts code is not in the initial chunk.

---

### [MINOR impact] Initial-bundle budget has no warning headroom below the 500 kB target and no lazy/bundle-level budget for the documented < 200 kB lazy ceiling

**Location:** `angular.json:43-54` (`budgets`)
**Problem:** Two gaps relative to the project's stated targets. (1) The `initial` budget is `maximumWarning: 500kB` / `maximumError: 1MB`. The project's performance-spec target *is* 500 kB for the main bundle, so the warning threshold equals the target — the build only warns once the budget is already spent, giving no early-warning headroom, and the hard error allows the bundle to grow to **2x** the stated target (1 MB) before failing. (2) There is no `bundle`-type or per-lazy-chunk budget, so the documented "lazy modules < 200 kB" target is unenforced — a lazy route can grow past 200 kB silently once lazy loading is introduced. Only `initial` and `anyComponentStyle` budgets exist.
**Impact:** Process/guardrail gap rather than a shipped byte cost. Without a sub-target warning and a lazy-chunk budget, regressions against the 500 kB / 200 kB targets land without CI signal until they cross loose thresholds. Directly ties to the stated budgets being only partially encoded in the build.
**Confidence:** Strong-static (the budget config is fully visible; the targets are stated).
**Effort:** Localized — add an `"all"` or `"allScript"` budget for total script weight and a `"bundle"`/`"anyScript"` budget near 200 kB for lazy chunks, and consider lowering the initial `maximumError` toward the real ceiling (e.g. warn 450 kB / error 500 kB) so the build fails at the target rather than at 2x it.
**Verification plan:** Add the budgets, run `ng build --configuration production`, confirm the build reports against the new thresholds; intentionally over-import in a scratch branch to confirm the budget error fires.

---

## Suspected Bugs (for follow-up)

- **`tsconfig.app.json:13` includes three `.bak` files in the compilation `include` array** (`contract-filter-resolver.ts.bak`, `contract-filter-resolver.spec.ts.bak`, `contract-search.spec.ts.bak`). These `.bak` files exist on disk (confirmed). TypeScript include globs normally match by extension and `.bak` is non-standard, but they are listed by explicit path. This is a correctness/build-hygiene smell (stale backup files referenced by the build config, and `.bak` spec files that duplicate logic now living in non-`.bak` files). Not a payload finding — flagging for the correctness lane to confirm whether these are compiled/error and to remove the references. Several other `.bak` files also sit in `src` (`app.spec.ts.bak`, `contract-search.spec.ts.bak`) and should not ship to a source tree.
- **Two near-duplicate model files** `contract.model.ts` and `contract.models.ts` exist in `features/contracts/`. Potential dead/duplicate code; correctness lane to dedupe. Mentioned here only because dead code that gets imported can pad bundles — not currently reachable.
