<!-- ABOUTME: Assesses the immutable Browserslist dependency patch in Dependabot PR 189. -->
<!-- ABOUTME: Records source evidence, regression boundaries, validation, and advisory merge eligibility. -->

# Browserslist dependency patch risk review

## Review checklist

- [x] Bind the supplied patch to its base, head, and SHA-256.
- [x] Inspect all changed locked copies, incoming ranges, and existing registry coordinates.
- [x] Trace build, lint, and target-resolution callers and challenge their boundaries.
- [x] Incorporate the coordinating agent's exact-head validation evidence.
- [x] Assign final ratings and validate the companion JSON assessment.

## Immutable subject

Repository: `https://github.com/scarson/hangar-bay`; [Dependabot PR 189](https://github.com/scarson/hangar-bay/pull/189).
Base: `f457acb2877ff0e33da8ff3419cd3b0d6a4554e9`.
Head: `3f38a4c72b46dd40e395eefda95643fc19f6d57b`.
Canonical patch: `.cache/browserslist/pr189.patch` in this evidence checkout.
SHA-256: `6adf826723ca09a11ceb1be3ac437b20434372addd7d769af77443318f62975c`.
The coordinating agent re-read the provider comparison identity after retrieval and reported a match.
The reviewer independently verified the patch hash, head, and one-file comparison: 23 insertions and 23 deletions in `app/frontend/web/package-lock.json`.

The selected checkout is preserved. The reviewer performs source and metadata inspection only; executable validation is supplied by the coordinating agent. Review artifacts live outside the selected checkout and its Git directories.

## Source evidence

Both lockfiles contain 481 package records and identical package paths. Exactly six existing development dependencies change; no package namespace, registry host, direct manifest, engine requirement, install-script marker, application source, generated API contract, or persistence schema changes.

| Package | Base | Head |
| --- | --- | --- |
| browserslist | 4.28.6 | 4.28.9 |
| baseline-browser-mapping | 2.10.43 | 2.11.21 |
| caniuse-lite | 1.0.30001805 | 1.0.30001810 |
| electron-to-chromium | 1.5.389 | 1.5.422 |
| node-releases | 2.0.51 | 2.0.54 |
| update-browserslist-db | 1.2.3 | 1.3.2 |

There is one locked copy of each. Browserslist satisfies `@babel/helper-compilation-targets`'s `^4.24.0` dependency and the updater's `>=4.21.0` peer; all five refreshed children satisfy Browserslist's declared ranges. All six tarballs retain the established `registry.npmjs.org` namespace and SHA-512 integrity fields.

The Vite configuration enables TanStack router code splitting; its compiler uses Babel. React Hooks lint rules also call Babel. Babel's target helper loads Browserslist and resolves nonempty browser queries from explicit options, environment, or discovered configuration. With no discovered query, the helper uses an empty list and skips query evaluation. No Browserslist configuration, custom stats, or direct application imports are committed. This establishes tooling use without claiming an attacker-controlled application path.

Installed Browserslist source contains bounded result and parse caches plus own-property checks and null-prototype stats normalization. Both advisory ranges include `<=4.28.6` and name `4.28.7` as patched: [query-cache advisory GHSA-c83g-rgw3-j3cx](https://github.com/advisories/GHSA-c83g-rgw3-j3cx) and [custom-stats advisory GHSA-73wf-gq98-2v4g](https://github.com/advisories/GHSA-73wf-gq98-2v4g). The selected [4.28.9 release changes query parsing performance](https://github.com/browserslist/browserslist/releases/tag/4.28.9), so data and parser compatibility are part of this review. No advisory behavior was reproduced.

The coordinating agent separately queried version, tarball URL, and integrity metadata for all six changed npm coordinates; every result matched the candidate lock. The final lockfile SHA-256 is `bc1787aa07a7aca0cb5c34c467c2920c93a4d70003e356b777dcc2fcfaa40f8d`.

## Recommendation and ratings

**Merge; workflow label: `human_review_required`.** No actionable patch defect was established. This is the assessment skill's advisory label, not merge authorization or a replacement for the repository's separate merge-classification policy.

| Dimension | Rating | Evidence and implication |
| --- | --- | --- |
| Impact if wrong | Moderate | A regression could block frontend tooling or affect emitted assets; containment is the static frontend component. No backend route, application security guard, serialized contract, schema, or persistent state changes. |
| Regression likelihood | Moderate | Supported dependency ranges and applicable checks pass. Six dependency versions include parser and browser-data changes; upstream suites and a complete production-browser matrix remain untested. |
| Regression protection | Partial | Build/lint/client generation and application suites pass at the exact head. Existing browser fixtures run against Vite development mode and do not establish advisory semantics or every production browser engine. |
| Recoverability | Easy | Revert the lockfile commit and rebuild/redeploy prior static assets; no data migration. Rollback restores the affected version and therefore requires a subsequent patched resolution. |
| Confidence | Moderate | Immutable identity, complete graph, installed source and exact-head checks are evidenced. Bounded upstream/browser and CodeQL gaps remain explicit. |

The strict automatic-merge gate fails on moderate impact/likelihood, partial protection, moderate confidence, and explicit unknowns. Successful tests do not reduce the consequence of a build or frontend regression.

## Affected callers and boundary challenges

The owned roots are [frontend build scripts](https://github.com/scarson/hangar-bay/blob/3f38a4c72b46dd40e395eefda95643fc19f6d57b/app/frontend/web/package.json), [Vite router integration](https://github.com/scarson/hangar-bay/blob/3f38a4c72b46dd40e395eefda95643fc19f6d57b/app/frontend/web/vite.config.ts), and [React Hooks lint configuration](https://github.com/scarson/hangar-bay/blob/3f38a4c72b46dd40e395eefda95643fc19f6d57b/app/frontend/web/eslint.config.js). [Render's static deployment definition](https://github.com/scarson/hangar-bay/blob/3f38a4c72b46dd40e395eefda95643fc19f6d57b/render.yaml) runs `npm ci && npm run build` and serves `dist`.

Installed caller inspection traces router `compilers.ts` through `babel.parse`, and React Hooks through `transformFromAstSync`, into Babel's `config/partial.js`, `resolve-targets.js`, and `helper-compilation-targets/lib/index.js`. Vite 8.1.4 has fixed default targets of Chrome/Edge 111, Firefox 114, Safari/iOS 16.4; the Browserslist data refresh does not directly recompute those constants. The updater CLI's package-manager operations require explicit invocation; ordinary Browserslist stale-data handling only prints update guidance.

| Boundary/invariant | Strongest concrete counterexample | Legitimate control and source trace | Result |
| --- | --- | --- | --- |
| Complete patched graph and trusted resolution | An affected nested copy remains, a child range is invalid, or registry identity changes. | Enumerating all 481 records finds no added/removed paths and one patched copy. All incoming ranges, registry metadata, installation integrity and `npm ls` pass. | Supported |
| Supported frontend tooling and compilation target | An ordinary configured browser query or generated split route breaks after the parser/data refresh. | Unchanged Babel query/configuration handling and fixed Vite targets remain intact; the repository commits no query/stats configuration. Exact-head build, lint and application checks pass. Arbitrary external configuration is not covered. | Supported, with partial executable coverage |
| Correct query results when cache entries expire | A recurring ordinary query receives another query's result after eviction. | Installed `browserslist/index.js` binds result entries to queries/context and parse entries to queries; a miss recomputes through the normal resolver before bounded insertion. | Supported by source; upstream suite not run |
| Legitimate custom usage remains usable | Null-prototype normalized data breaks consumers expecting inherited methods. | Installed `node.js` preserves own browser/version usage mappings; `index.js`'s `fillUsage` enumerates and reads values without inherited object methods. No custom statistics are committed. | Supported by source; upstream suite not run |

## Exact-head validation

The coordinating agent ran the executable checks below on `3f38a4c72b46dd40e395eefda95643fc19f6d57b`. The reviewer independently inspected the patch, lock graph, installed source, audit artifact and final subject identity; it did not execute project code, installs, builds, tests, applications or exploit payloads.

| Check | Result and what it protects |
| --- | --- |
| Clean installation and dependency validity | `npm ci --ignore-scripts --no-audit --no-fund`: 480 packages; complete `npm ls` valid. Registry metadata for all six changed packages matches. |
| Known dependency advisories | `npm audit --json`: exit 0, `vulnerabilities: {}`, total 0; independently read `.cache/browserslist/audit.json`. Does not prove absence of all security defects. |
| Production build and lint | `tsc -b` plus Vite production build: 202 modules; lint passes. |
| API generation | `generate:api` passes, committed schema/OpenAPI have no semantic changes. |
| Unit and future clock | 509 tests in 33 files pass in each run; future clock `2027-10-10T11:49:48.813Z`. |
| Existing browser suite | 146 pass, 7 expected skips, exit 0 in 37.7 seconds; existing Chromium fixtures verify frontend requests and rendering through the development server. |
| [Application CI run 33963128487](https://github.com/scarson/hangar-bay/actions/runs/33963128487) | Frontend and OpenAPI drift pass at the assessed head; lockfile classification selects frontend and correctly excludes backend tests. |
| CodeQL check 101298392582 | **Unavailable**: neutral/skipping result with missing default-setup configurations for actions, JavaScript/TypeScript, Python and Rust. It is not a passed security analysis. |
| Subject preservation | Generated line-ending status was verified semantically empty and restored by the coordinating agent. Final tracked checkout is clean; head and patch identity are unchanged. |

## Remaining risk and evidence limits

Not merging leaves the confirmed affected `4.28.6` dependency in frontend tooling. The coordinator reported alert 11 as `auto_dismissed` and alert 10 as open; auto-dismissal does not replace the vulnerable graph. The status-quo risk is moderate for this bounded tooling use. Application exploitability and attacker-controlled query/statistics reachability remain unproven, and repository alert closure requires processing the integrated default-branch dependency graph.

CodeQL did not run successfully, and upstream cache/statistics suites, all browser engines against emitted production assets, and an actual Render rollout were not run. These gaps limit confidence and automatic-merge eligibility. They are not decision-critical for this lockfile-only recommendation: complete resolution/provenance checks, known-advisory removal, inspected caller/configuration boundaries, and applicable application checks provide direct evidence for the change. There is no unresolved source-visible regression or failed relevant check.

The companion `2026-09-05-browserslist-risk-review.json` is the machine-readable assessment. It is validated with the installed `assess-patch-risk` schema and semantic validator; review artifacts remain outside the selected subject checkout.
