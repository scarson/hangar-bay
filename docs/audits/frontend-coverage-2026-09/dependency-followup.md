<!-- ABOUTME: Records the installed dependency paths behind two GitHub Dependabot alerts reported during frontend coverage work. -->
<!-- ABOUTME: Bounds runtime conclusions and defines verification for a separate dependency-maintenance follow-up. -->

# Frontend dependency alert follow-up

GitHub reported both alerts as high severity. That severity is GitHub alert metadata; this note did
not independently validate exploitability or reproduce either advisory behavior.

## Installed versions and paths

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

## Recommended follow-up verification

Handle both in a separate dependency-maintenance branch after the frontend coverage work:

1. Resolve the existing transitive package coordinates to at least `nanoid@3.3.18` and
   `js-yaml@4.3.1` with the smallest lockfile change available; inspect whether parent-package
   changes are necessary before considering an override.
2. Review the lockfile diff and rerun `npm ls nanoid js-yaml --all` plus
   `npm ls nanoid js-yaml --all --omit=dev` to confirm the installed versions and paths.
3. Run the complete frontend verification lanes and a production build. Run API-client generation
   and confirm it produces no unexpected schema diff because one `js-yaml` path belongs to
   `openapi-typescript`.
4. After the dependency change is pushed, confirm GitHub closes alerts 9 and 8 rather than treating
   a locally clean audit as evidence that the repository alerts are resolved.

No dependency, lockfile, source, or configuration change was made during this inspection.
