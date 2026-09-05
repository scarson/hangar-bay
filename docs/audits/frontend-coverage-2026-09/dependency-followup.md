<!-- ABOUTME: Records the installed dependency paths behind two GitHub Dependabot alerts reported during frontend coverage work. -->
<!-- ABOUTME: Bounds runtime conclusions and defines verification for a separate dependency-maintenance follow-up. -->

# Frontend dependency alert follow-up

## Remediation status

Sam authorized the two-alert fix on 2026-09-05. [PR 188 — patch Nano ID and js-yaml dependency alerts](https://github.com/scarson/hangar-bay/pull/188)
resolves Nano ID to `3.3.18`, js-yaml to `4.3.1`, and its exact-pinning Redocly parent to
`1.34.19`, entirely within existing dependency ranges. The
[dependency remediation record](../dependencies/2026-09-05-frontend-alert-remediation.md)
contains the lockfile scope, passing build/code-generation/frontend checks, fresh independent
review, converged committed-patch Codex review, and integration gates. GitHub alert closure remains a post-merge check owned by the
coordinating agent. The full npm audit also surfaced an unchanged `browserslist@4.28.6` residual,
recorded there for separate maintenance; it is outside these two alerts.

## Initial inspection

GitHub reported both alerts as high severity. That severity is GitHub alert metadata; this note did
not independently validate exploitability or reproduce either advisory behavior.

## Baseline installed versions and paths

### `nanoid`

- Alert: [Dependabot alert 9](https://github.com/scarson/hangar-bay/security/dependabot/9),
  reported for custom generators with a size of zero and patched in `3.3.18`.
- Installed and locked: `nanoid@3.3.17`.
- Dependency path: `web` -> `@tailwindcss/vite@4.3.2` -> `vite@8.1.4` ->
  `postcss@8.5.25` -> `nanoid@3.3.17`.
- Classification: build/development tooling. `vite.config.ts` loads `@tailwindcss/vite`, and the
  package scripts run Vite for development, build, and preview. No project source imports
  `nanoid`. `npm ls --omit=dev` still retains this path because `@tailwindcss/vite` is declared in
  root `dependencies`, so npm classifies it as production-installable even though its project use
  is Node-side asset building. The inspection did not establish a browser-shipped runtime path or
  whether PostCSS reaches the affected custom-generator API.

### `js-yaml`

- Alert: [Dependabot alert 8](https://github.com/scarson/hangar-bay/security/dependabot/8),
  reported for quadratic CPU behavior while parsing `!!omap` and patched in `4.3.1`.
- Installed and locked: one deduplicated `js-yaml@4.3.0`.
- Dependency paths:
  - `web` -> `eslint@9.39.5` -> `@eslint/eslintrc@3.3.6` -> `js-yaml@4.3.0`.
  - `web` -> `openapi-typescript@7.13.0` -> `@redocly/openapi-core@1.34.18` ->
    `js-yaml@4.3.0`.
- Classification: development tooling. Both direct parents are root `devDependencies`, the
  lockfile marks `js-yaml` as `dev: true`, and the paths support linting and generated API-client
  work. No project source imports `js-yaml`. This inspection did not establish that Hangar Bay
  supplies attacker-controlled YAML containing `!!omap` to either tool.

## Completed baseline verification plan

The version resolution, dependency-tree checks, frontend validation, production build, and
generated-client check requested by this baseline inspection have been completed in PR 188.
The [dependency remediation record](../dependencies/2026-09-05-frontend-alert-remediation.md)
is authoritative for commands, results, review, and remaining integration work. Do not repeat
the baseline plan as unstarted implementation work.

The coordinating agent still must verify GitHub closes alerts 9 and 8 after merge to the default
branch; local package remediation alone does not establish repository alert closure. The initial
inspection recorded here made no dependency, lockfile, source, or configuration change.
