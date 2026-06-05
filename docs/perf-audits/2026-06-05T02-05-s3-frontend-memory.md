# Frontend Performance Audit — Memory & Rendering Lifecycle

**Dimension:** memory & rendering lifecycle (subscriptions, signals, pipes, change detection)
**Stack:** Angular 20 (zoneless + signals), RxJS 7.8, TS 5.8 — STATIC-ONLY
**Date:** 2026-06-05

## Reachability context (applies to every finding below)

`app/frontend/angular/src/app/app.routes.ts:3` is `export const routes: Routes = [];`. No route
loads any feature component, and a content search confirms neither pipe (`isk`, `timeLeft`) nor
either service (`ContractSearch`, `ContractApi`) is referenced from any template or component —
only from their own definitions, `*.spec.ts`, `*.spec.ts.bak`, and the filter resolver. Both
services are `providedIn: 'root'` singletons.

Consequence: everything in scope is **latent**. `ContractSearch`'s constructor pipeline fires only
once the service is first injected; the pipes run only once a list template renders them. The
findings below describe what happens **once these are wired into a route** — none represents a
runtime cost today. I have explicitly avoided manufacturing leaks/churn over the unreachable code.

---

## Findings

### [MINOR impact] `JSON.stringify`-based `distinctUntilChanged` allocates two strings per filter change
**Location:** `app/frontend/angular/src/app/features/contracts/contract-search.ts:61`
**Problem:** The filter-dedup guard is
`distinctUntilChanged((prev, curr) => JSON.stringify(prev) === JSON.stringify(curr))`. Each
comparison serializes both the previous and current `ContractSearchFilters` object to a string and
compares the strings. `ContractSearchFilters` is a small flat object (≤6 scalar keys), so each
`stringify` is cheap and short-lived, but the pattern allocates two transient strings per emission.
It also carries a latent correctness foot-gun: `JSON.stringify` is key-order-sensitive, so two
semantically-equal filter objects built with different key insertion order would compare as
different and not be deduped (here the object is always built via `{ ...current, ...newFilters }`
so order is stable, so this is not currently a bug — noted only as fragility).
**Impact:** Two short-lived string allocations per `updateFilters()` call, gated behind
`debounceTime(300)`. Frequency is at most a few per second of active typing; per-occurrence cost is
trivial for a 6-field object. No retained memory. Latent until the service is routed.
**Confidence:** Strong-static
**Effort:** Localized — replace with a field-wise equality comparator over the known keys, or a
shallow-equal helper; no API change.
**Verification plan:** A structural/shallow comparator over the fixed `ContractSearchFilters` keys
produces identical dedup behavior for all stably-built objects while eliminating the allocations and
the key-order fragility. Guard: keep a test that two distinct filter values still pass through and an
identical one is suppressed.

### [MINOR impact] `timeLeft` is a pure pipe over a moving clock — memoization caps recompute at one-per-input but the value goes stale (rendering-lifecycle note)
**Location:** `app/frontend/angular/src/app/shared/pipes/time-left.ts:3-8`
**Problem:** `timeLeft` is a pure (default) standalone pipe whose output depends on `Date.now()` via
`new Date()` at line 14, not only on its input `value`. A pure pipe is memoized per input reference:
once a row's `date_expired` string is rendered, the pipe will **not** re-run for that row until the
input reference changes. From the **memory/rendering** lens this is the *good* outcome — it does
**not** re-run every change-detection cycle and creates no per-cycle churn (correctly leaning on
purity in a zoneless app). The flip side is a correctness issue, not a memory one: the countdown
will not tick down on its own. I am classifying the staleness as a suspected bug (below), and noting
here only that the pipe is correctly pure from a CD-cost standpoint — do **not** "fix" it by marking
it `pure: false`, which would convert it into a per-row, per-CD-cycle `Date` allocation and a real
churn source on a rendered list.
**Impact:** Zero per-cycle recompute today (latent). The hazard is a future `pure: false`
"fix" that would run `new Date()` plus several arithmetic/`Math.floor` ops per visible row per CD
pass.
**Confidence:** Strong-static
**Effort:** Localized — if live ticking is wanted, drive it from a single shared `interval`/signal
timebase passed as an input (so purity and memoization are preserved), not from pipe impurity.
**Verification plan:** Confirm via the `@Pipe` decorator that `pure` is unset (defaults to `true`)
and that `transform` reads `new Date()` internally; the combination proves "memoized but stale."
Guard against regression: any change to live-updating must not introduce per-row `Date` allocation
in a `pure:false` transform.

---

## Items examined and found NOT to be memory concerns (stated honestly, not padding)

- **`ContractSearch` constructor subscription has no `takeUntilDestroyed`/teardown
  (`contract-search.ts:55-94`).** This is **not** a leak. `ContractSearch` is a
  `providedIn: 'root'` singleton; it lives for the whole application lifetime, so its single
  long-lived subscription to `filterTrigger$` is expected to live just as long. There is no
  destroy event to leak across, and exactly one subscription is ever created. The standard
  "subscribe without teardown" flag does not apply to a root-singleton's own internal stream.
  The inner `this.http.get(...)` is run via `switchMap`, which unsubscribes the prior in-flight
  request on each new emission — no per-request subscription accumulation.

- **`ContractApi.getContracts()` calls `.subscribe()` with no explicit teardown
  (`contract.api.ts:94`).** Each call subscribes to a fresh `HttpClient.get` observable. Angular's
  `HttpClient` observables complete after one emission (success or error), which auto-tears-down the
  subscription; `finalize` runs on completion. So these are self-completing, not retained. The one
  caveat is that overlapping `getContracts()` calls are not cancelled (no `switchMap` here, since
  it is imperative) — that is a request-ordering/race concern, not a memory leak, and belongs to a
  data-access lens, not this one.

- **Signals/computed in `ContractSearch` (`:44-47`).** `loading`/`error`/`data` are `computed`
  over a single `#state` signal. They recompute only when `#state` is `.update()`d (once per
  loading toggle / response). No high-frequency recomputation churn; each `computed` reads one slice
  and is cached until the dependency notifies. This is the recommended fine-grained pattern, not a
  churn source.

- **Retained large response objects in signal state (`#state.data`, `_state.contracts`).** State
  holds at most **one page** of results (`ContractSearch` default `size: 20` at `:41`;
  `ContractApi` stores `response.items`). Each fetch **replaces** the prior data via
  `update((s) => ({ ...s, data: response }))` / `contracts: response.items` rather than appending,
  so there is no unbounded growth. The `{ ...s, ... }` spread clones only the small wrapper state
  object (5 scalar/array-ref fields), not the contract array elements — bounded, acceptable.

- **`isk` pipe (`isk.ts`).** Pure, standalone, stateless, no allocation beyond the returned string;
  memoizes per `(value, precision)` input. Correct choice for per-row currency formatting in a list
  — exactly what a pure pipe is for. No concern.

- **`app.component.ts`.** Stateless standalone shell (`title` literal + `RouterOutlet`). No
  subscriptions, signals, pipes, timers, or listeners. Nothing in this dimension.

---

## Suspected Bugs (for follow-up)

- **`timeLeft` never updates after first render.** `app/shared/pipes/time-left.ts:8-40` — pure pipe
  reads the wall clock but is memoized per input, so a rendered countdown will display its
  first-render value indefinitely (until the input reference changes or the row re-renders). This is
  a correctness/UX bug, not a memory bug. Correct fix preserves purity (feed a shared ticking
  timebase as an input); do not switch to `pure: false`.
- **`JSON.stringify` dedup is key-order-sensitive.** `contract-search.ts:61` — not a live bug given
  the always-stable object construction, but a latent fragility if filters ever get built with
  varying key order. Flagged for the same follow-up as the allocation finding above.
