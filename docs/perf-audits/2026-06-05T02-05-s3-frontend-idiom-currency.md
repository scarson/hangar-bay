# Frontend Performance Audit — Framework-Idiom Currency (Angular 20)

**Lane:** framework-idiom currency (Angular)
**Date:** 2026-06-05
**Scope:** Static-only. Files under `app/frontend/angular/src` named in the brief.
**Stack confirmed:** Angular 20 (`package.json`: `@angular/core ^20.0.0`, `@angular/cdk ^20.0.4`), RxJS `~7.8.0`, TypeScript `~5.8.2`. Zoneless + signals + standalone in use.

## Index basis / currency caveat

Index relied on: `version-indexes/javascript-typescript.md`, `covered_through: "React 19 / Angular 19 (zoneless GA in 21) / Vue 3.5 / Node.js 22 LTS"`, built 2026-06-04.

The index covers Angular **signals** (line 79), **signal inputs** (80), **`linkedSignal`/`resource`** as **Angular 19 experimental** (81), **`OnPush`** (82), **zoneless** as **experimental ~18 / default ~21** (83), and **control flow `@if`/`@for`/`track`** (87). It does **not** cover Angular 20 release specifics: it has no entry for `httpResource`, no entry for `rxResource`, and does not record the Angular-20 stabilization/promotion status of `resource`/`linkedSignal` or of the zoneless scheduler. Because this app targets Angular 20 — one major past `covered_through` — any finding whose recommendation depends on the exact Angular-20 stability of `resource`/`httpResource`/`rxResource` is marked **Heuristic** and flagged for manual currency check. No live currency brief was available, so no Angular-20-specific stability claims are asserted as fact below.

Per the support-cadence note (index lines 38-40): Angular supports each major ~18 months; "currency" here is about whether the code uses the idioms current **for the version the app already targets (20)**, not a separate LTS track. No version upgrade is recommended.

---

## Findings

### [MINOR impact] Hand-rolled `Subject` + `switchMap` → signal bridge instead of Angular 20 resource/`toSignal` idiom
**Location:** `app/features/contracts/contract-search.ts:53-94` (pipeline), `:34-47` (signal state)
**Problem:** The service runs a manual reactive pipeline — `filterTrigger$ = new Subject<void>()` (`:53`) piped through `startWith` / `debounceTime` / `map(() => this.#filters())` / `distinctUntilChanged` / `switchMap(http.get)` (`:56-88`), with the result imperatively pushed into a `signal` via `.subscribe(... #state.update())` (`:90-94`). The lens flags the corrective direction toward push-based signal idioms (profile-pack lines 23-29, 61-68) and the index records the `resource` API for "async data loading with built-in request/loading state" that "supersedes manual `computed` + `effect` data-loading patterns" (index line 81). In a zoneless + signals app, the current Angular-20 idiom for "signal of filters → async fetch → signal of {data, loading, error}" is a `resource`/`rxResource`/`httpResource` (or at minimum `toSignal` over the stream) rather than a Subject-to-signal bridge that re-derives `loading`/`error`/`data` through three separate `computed`s (`:44-46`). The hand-rolled path also manually re-implements loading/error state that the resource idiom provides built-in.
**Impact:** Idiom-currency / maintenance gap, not a hot-path CPU cost. The bridge itself is cheap; per fetch it is one debounce + one HTTP round-trip, identical work to the resource idiom. The cost is (a) more surface to get wrong (manual `loading` reset on error at `:84`, `distinctUntilChanged` correctness — see Suspected Bugs) and (b) divergence from the version's first-class data-loading primitive. **Latent:** `app.routes.ts` is `routes = []`, so this service is not wired into any route today; fires only once the contracts route exists. No measurable runtime win from migrating — this is a currency/idiom finding, not a perf hotspot.
**Confidence:** Heuristic — the *direction* (signals-first data loading) is grounded in the index (line 81) and lens, but the specific recommendation (`rxResource`/`httpResource`) depends on Angular-20 stability that the index (`covered_through` Angular 19) does not confirm. Flag for manual currency check against angular.dev/guide/signals#resource and the httpResource guide for the 20.x line.
**Effort:** Contained — rewriting the service's reactive core and updating the consuming component's read sites; the public signal surface (`loading`/`error`/`data`/`filters`) can be preserved to limit blast radius.
**Verification plan:** Confirm against Angular 20.x docs that `rxResource`/`httpResource` is the recommended (stable or intended) data-loading primitive on this line before migrating; if still experimental in 20.x, keep the current pipeline and only flag. Correctness guard: preserve debounce-300 + dedup semantics and the loading/error transitions; add a test that filter updates produce exactly one in-flight request (switchMap cancellation) before and after.

---

### [MINOR impact] Second contracts service uses imperative `getContracts()` + bare `.subscribe()` rather than the signal/resource idiom
**Location:** `app/features/contracts/contract.api.ts:44-94`
**Problem:** `ContractApi.getContracts()` is an imperative command that builds `HttpParams`, then `http.get(...).pipe(tap/catchError/finalize).subscribe()` (`:64-94`), writing results into a `signal` `_state` (`:27-36`). This is the older "method that fires a fetch and side-effects into state" shape. The index's `resource` entry (line 81) and the lens's preference for push-based signal data loading (profile-pack 23-29) point at the same modernization as the finding above: a request derived from a signal feeding a `resource`/`httpResource`, rather than an imperatively-invoked `subscribe()`. The bare `.subscribe()` with no `takeUntilDestroyed()`/teardown (`:94`) is the subscription pattern the lens calls out (profile-pack 61-68) — here it is request-scoped and self-completing, so not a leak, but it is the non-current idiom.
**Impact:** Idiom-currency gap; negligible runtime cost (one HTTP request per call). Note this is a **second, parallel** contracts service (distinct models `contract.model` vs `contract.models`, distinct state shape) alongside `ContractSearch` — duplicate idiom surface to keep current. **Latent:** not reachable (`routes = []`); no consumer wired today.
**Confidence:** Heuristic — same Angular-20 stability caveat on the recommended replacement as the prior finding.
**Effort:** Contained — same migration class as `contract-search.ts`; or Localized if the only change is `.subscribe()` → `takeUntilDestroyed()` hygiene.
**Verification plan:** Same Angular-20 currency check on resource APIs. If keeping RxJS, the request-scoped subscription is acceptable; no correctness change required. Guard: verify `finalize` loading-reset semantics are preserved if migrated.

---

### [MINOR impact] `timeLeft` as a **pure** pipe will not recompute as wall-clock advances (pure-vs-impure tradeoff)
**Location:** `app/shared/pipes/time-left.ts:3-7` (declared pure — no `pure: false`), `:13-15` (reads `new Date()` at call time)
**Problem:** `TimeLeft` is a pure pipe (default; `@Pipe({ name: 'timeLeft', standalone: true })`, no `pure: false`) but its output depends on `now = new Date()` (`:14`), a value that is **not** one of its inputs. The lens describes exactly this class: a pure pipe "called only when the input reference changes" vs an impure pipe that "re-run[s] every cycle" (profile-pack lines 42-49). For a relative-time display, a pure pipe is the *performant* choice but the *incorrect-over-time* choice: given a fixed `value` input, Angular will not re-invoke `transform`, so a rendered "5h 12m" stays frozen until the input reference changes or the component is otherwise re-rendered — it never ticks down on its own. This is the documented perf-vs-correctness tradeoff of pure vs impure for time-relative values.
**Impact:** Correctness-leaning, with a real perf tradeoff on the fix. The *current* pure form has near-zero CD cost (memoized on input identity) — good for perf, wrong for a live countdown. Making it `pure: false` to tick would re-run `transform` on **every** CD pass for **every** row (profile-pack 42-49), which under zoneless is rare today but becomes per-pass-per-row cost on a contracts list. The current-idiom fix for a zoneless+signals app is neither pure-frozen nor impure-every-cycle but a single shared interval signal/timer that the value derives from (computed off a `signal` clock), so one tick re-renders all rows without per-row impure evaluation. **Latent:** no template uses this pipe yet (no list template exists; `routes = []`), so neither the staleness nor any impure cost is observable today — fires once a contracts list renders it.
**Confidence:** Strong-static for the pure-pipe-won't-recompute behavior (grounded in profile-pack 42-49, and the code plainly reads a non-input `Date`). Heuristic on the recommended signal-clock remedy being the Angular-20-current shape.
**Effort:** Localized — the pipe itself plus introducing one shared clock signal; or Localized to flip `pure: false` if correctness is prioritized over per-row cost.
**Verification plan:** Decide the requirement first: if the displayed value must tick, a pure pipe is wrong; if it only needs to be correct at render time, the pure pipe is fine and this is a no-op. If a live countdown is required, prefer a shared interval `signal` feeding a `computed` over `pure: false`, and measure CD-pass count on a rendered list (impure pipe = N transform calls per pass). Correctness guard: assert the rendered string advances across a simulated clock tick.

---

## Items checked and found current (no finding)

- **`app.config.ts:11-18`** — `provideZonelessChangeDetection()`, `provideHttpClient(withFetch())`, `provideRouter(routes, withComponentInputBinding(), withViewTransitions())`, `provideBrowserGlobalErrorListeners()`. These are the current Angular 20 bootstrap idioms (index lines 83, 79; zoneless is the forward-default per index line 83). Reachable today; no idiom-currency problem. `provideClientHydration()` is absent, but the lens's hydration guidance (profile-pack 82-90) applies to SSR — this is a `bootstrapApplication` SPA, so not applicable.
- **`main.ts:3-17`** — standalone `bootstrapApplication`, current idiom (index line 89). No finding.
- **`app.component.ts:1-13` / `app.component.html:1`** — standalone component, `inject`-ready, `imports: [RouterOutlet]`, single `<router-outlet>`. Under zoneless, omitting `OnPush` is moot — the lens's `OnPush` guidance (profile-pack 14-21) is superseded by zoneless, so its absence is not a finding. No template expressions, getters, or impure pipes. Current.
- **`isk.ts:19-58`** — pure pipe, pure function of its `value`/`precision` inputs, cheap arithmetic. Correct and current idiom (profile-pack 42-49 endorses pure pipes for input-derived values). No finding.
- **`contract-filter.resolver.ts:11-31`** — functional `ResolveFn` with `inject()` (current router idiom over class resolvers). Synchronous param parse + signal set; no blocking I/O. No idiom-currency or startup cost. No finding.
- **`@for`/`track` and `@if` control flow** — no list/conditional template exists yet (the only template is `<router-outlet>`). The index's `track`-mandatory guidance (line 87; profile-pack 51-59) cannot be evaluated statically and will apply once a contracts list template is authored. Noted as a forward expectation, not a finding.

---

## Suspected Bugs (for follow-up)

- **`contract-search.ts:61` — `distinctUntilChanged` via `JSON.stringify` is key-order-sensitive.** `(prev, curr) => JSON.stringify(prev) === JSON.stringify(curr)` treats objects with identical contents but different key insertion order as different, and is brittle to `undefined`-valued keys being dropped. Combined with `map(() => this.#filters())` reading the latest signal (`:60`), two rapid `updateFilters` calls that net to the same filter object can still pass `distinctUntilChanged` and issue a redundant fetch, or vice-versa. Correctness/dedup follow-up, not this lane.
- **`contract-search.ts:84` vs `:90-94` — error path leaves stale `data`, success path on `response === null` is skipped.** On HTTP error, `catchError` sets `loading:false, error:...` but does not clear stale `data` (`:84`); the outer `.subscribe` only updates state when `response` is truthy (`:91`), so a `null` from `catchError` is silently dropped — intended, but means loading/error transitions live in two places. Correctness follow-up, not this lane.
