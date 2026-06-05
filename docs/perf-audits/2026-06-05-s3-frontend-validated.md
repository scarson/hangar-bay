# S3 — Frontend Angular SPA · Cross-Validated Findings (cycle Phase 3)

**Source:** `2026-06-05T02-05-s3-frontend-consolidated.md` + 5 raw lane reports.
**Validation:** every finding re-checked against source (read directly during scoping); reachability
re-confirmed by grep (`routes=[]`, no consumer of the feature services/pipes — **latent**). Static-only.

**Completeness:** 10 unique findings (FP1–FP10) + 8 suspected bugs. All dispositioned. **Headline: the
slice is correctly assessed as low-yield because the code is latent — and the lanes reported that
honestly rather than padding (the anti-padding stress test passed).**

## Confirmed (default: FIX — but all gated on the feature being wired, see note)

| ID | Title | Impact (latent caveat) | Effort | Blast radius |
|----|-------|------------------------|--------|--------------|
| FP1 | Two overlapping `/contracts/` services, divergent shapes/URLs | MAJOR once wired | Contained | consolidating resolves SB-S3-1/3/4; touches the whole feature data layer |
| FP2 | 300 ms debounce on discrete pagination/sort actions | MINOR once wired | Localized | split the trigger; type-ahead debounce preserved |
| FP3 | `JSON.stringify` `distinctUntilChanged` | MINOR | Localized | field comparator |
| FP4 | No request sharing / no transfer cache | MINOR | Contained | **design call** (freshness) |
| FP5 | Hand-rolled Subject+switchMap vs Angular 20 resource idiom | MINOR (Heuristic) | Contained | currency; verify against Angular 20 docs first |
| FP6 | `timeLeft` pure-pipe stale snapshot (don't go impure) | MINOR | Localized | shared signal clock; co-located with SB-S3-6 |
| FP7 | Eager `@angular/localize/init` with zero i18n usage | MINOR | Localized | drop polyfill; re-add at i18n start |
| FP8 | No lazy-loading/code-splitting convention | MINOR (Heuristic) | Contained | set convention before features land |
| FP9 | Loose budgets (no warning headroom, no lazy budget) | MINOR | Localized | tighten `angular.json` budgets |
| FP10 | Per-row pipe cost on list render; `size` URL-unbounded | MINOR once wired | Contained | CDK virtual scroll + `track` + clamp `size` when list lands |

**Disposition note (important nuance):** the disposition discipline says default = FIX, no
severity-deferral. Here the honest constraint is **reachability, not severity**: FP1/FP2/FP3/FP6/FP10
are gated on the contracts feature actually being wired (it isn't yet). Per the finding model, latent
code is "fires once wired in" — so these are scheduled **as part of wiring the feature**, not deferred
to no one. FP7/FP8/FP9 (build/budget posture) are **actionable now** and should be done now while
cheap. None is dropped on severity grounds; FP4 and FP5 carry explicit design/verify caveats.

## Design decisions needing user input
1. **Consolidate to one contracts service + model (FP1)** — *Recommendation:* keep the signal+RxJS
   `ContractSearch` (it has the debounce/cancel pipeline) or migrate it to `httpResource`; delete the
   duplicate `ContractApi`/`contract.model.ts`. Resolves the response-shape and base-URL bugs too.
2. **Adopt the Angular 20 resource idiom (FP5)?** — *Recommendation:* verify `httpResource`/`rxResource`
   stability in the project's exact Angular 20.x against current docs (our version index only covers
   through Angular 19), then adopt for the consolidated service; it subsumes FP2/FP3 hand-rolled logic.
3. **HTTP caching / transfer cache (FP4)** — *Recommendation:* defer until SSR or measured refetch pain;
   it's a freshness tradeoff, not a clear win for a frequently-changing contracts list.

## False positives / correctly rejected (no action — recorded as anti-padding evidence)
- Root-singleton subscription flagged as a leak — **rejected** (lives for app lifetime; switchMap cancels).
- `pure:false` as the `timeLeft` fix — **rejected** (would create per-row/per-CD churn).
- `@angular/cdk`/`material` charged to the bundle — **rejected** (grep-confirmed unimported).
- Render/`@for`/`trackBy` nits over the not-yet-existent list template — **not manufactured** (forward note only).

## Out-of-scope / pre-existing
- All 8 suspected bugs are correctness, handed to `bug-hunt-cycle`. **SB-S3-1 and SB-S3-2**
  (response-shape + `sort_order`/`sort_direction` mismatches against the backend contract) are the
  highest-value — the frontend would render zeros and silently ignore sort the moment it's wired. They
  also intersect the **backend** S1 work (the `ContractSchema`/response contract), so coordinate the
  fix across slices (see the roll-up).
- `.bak` files in `tsconfig` include (SB-S3-7) — build hygiene, not perf.

## Blast-radius summary
Nothing here is reachable in production today, so no live regression risk. The build-posture items
(FP7/FP8/FP9) are safe, immediate, `ng build`-verifiable wins. The data-layer items are best done **as
part of** wiring the contracts feature — and that wiring must align the frontend request params and
response model with the backend contract (the cross-slice theme — see the whole-repo roll-up).
