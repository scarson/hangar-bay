<!-- ABOUTME: Preserves the independent Codex CLI verdict for the immutable Browserslist dependency patch. -->
<!-- ABOUTME: Separates the reviewer's CI evidence limits from the author's separately executed local checks. -->

# Browserslist Codex CLI review

The prescribed review used `gpt-5.6-sol` with high reasoning, a read-only sandbox, and a frozen
PR 189 checkout. The process exited 0. Its final response follows; only its temporary local
lockfile link was replaced with the corresponding immutable GitHub link for this archive.

Author's evidence clarification: the reviewer describes the hosted CI lane, which does not
run `vite build`. A separate local `npm run build` at the same exact head completed
successfully, as recorded in the [dependency verification results](2026-09-05-browserslist-verification.md#exact-head-verification).
The CLI's production-bundling sentence must not be read as claiming that this local check was
absent. No implementation change resulted from this review.

## Archived verdict

**DONE — CONVERGED**

Exact review range:

- Base: `f457acb2877ff0e33da8ff3419cd3b0d6a4554e9`
- Head: `3f38a4c72b46dd40e395eefda95643fc19f6d57b`
- Head is a direct child of base.
- Only [package-lock.json](https://github.com/scarson/hangar-bay/blob/3f38a4c72b46dd40e395eefda95643fc19f6d57b/app/frontend/web/package-lock.json#L2666) changed: 23 insertions, 23 deletions.
- Supplied patch SHA-256 matched `6adf826723ca09a11ceb1be3ac437b20434372addd7d769af77443318f62975c` and matched the canonical 99-line Git diff line-for-line.

### (a) Blocking findings

None.

The repository has one tracked JavaScript lockfile and one Browserslist record. The candidate replaces `4.28.6` with `4.28.9`, removing every tracked copy affected by the supplied `<=4.28.6` advisory ranges.

All incoming and downstream constraints remain valid:

- `@babel/helper-compilation-targets`: `browserslist ^4.24.0`
- `update-browserslist-db`: peer `browserslist >=4.21.0`
- Browserslist’s five updated dependencies all satisfy its declared ranges:
  `baseline-browser-mapping 2.11.21`, `caniuse-lite 1.0.30001810`, `electron-to-chromium 1.5.422`, `node-releases 2.0.54`, and `update-browserslist-db 1.3.2`.

Every changed record uses `https://registry.npmjs.org`. All six candidate tarballs were already present in the npm content-addressed cache; their recomputed SHA-512 hashes matched the lockfile SRI values, and their embedded names, versions, dependencies, entry points, and engine requirements matched the lock metadata.

### (b) Adjacent, never-claimed concerns

None found.

Application exploitability remains unproven. The review does not infer exploitability from advisory severity and did not reproduce advisory behavior.

### Compatibility assessment

The reachable tooling paths are:

- Configured TanStack Router Vite plugin → Babel core → compilation-target helper → Browserslist.
- Configured React Hooks ESLint plugin → Babel core → compilation-target helper → Browserslist.
- OpenAPI TypeScript generation has no dependency path to Browserslist.

Cached source inspection found the router plugin uses Babel traversal, while the lint plugin’s Babel transform disables external Babel configuration and supplies no browser targets. No tracked `.browserslistrc`, manifest `browserslist` field, or equivalent configuration exists.

Browserslist’s default query and its browser entry, CLI, and TypeScript declarations are unchanged between `4.28.6` and `4.28.9`. The refreshed datasets can change results for queries that consume current browser/Node data, but no project-specific target contract or observed caller establishes such a behavior change here.

### Validation limits

No installs, tests, builds, applications, generation, audits, exploit payloads, edits, or network operations were performed.

The supplied exact-head CI evidence is relevant but bounded:

- Frontend success covers `npm ci`, lint, TypeScript checking, unit tests, future-clock tests, and Chromium E2E through the Vite development server.
- OpenAPI drift success covers backend schema export, frontend installation/code generation, and generated-file drift.
- Exact-head CI does not run `vite build`; therefore production bundling was not directly executed at this head. This is an evidence limitation, not a source-backed regression.
- The backend test job was intentionally filtered by the frontend-lockfile-only change. OpenAPI export is not a substitute for the backend suite.
- CodeQL’s four “default setup configuration not found” outcomes are neutral and provide no successful analysis evidence.

Final state remained clean and immutable at head `3f38a4c72b46dd40e395eefda95643fc19f6d57b`. PR classification, body, CI merge gating, and merge action remain with the parent as requested.
