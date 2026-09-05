<!-- ABOUTME: Records the dependency paths, patch selection, and validation for two frontend dependency alerts. -->
<!-- ABOUTME: Separates installed-version remediation from unproven application exploitability and repository alert closure. -->

# Frontend dependency alert remediation

Sam authorized remediation of the Nano ID and js-yaml alerts on 2026-09-05. Work is isolated on
`codex/dependency-alerts`, based on `d43da7c9313de7ce19aa9de21242b07949da4364` (the frontend
coverage changes merged through PR 187). The root checkout and its pre-existing untracked
`.codex/config.toml` are outside this task's edits.

## Checklist

- [x] Inspect current alert metadata, locked paths, declared ranges, and project usage.
- [x] Obtain an independent read-only dependency and compatibility investigation.
- [ ] Establish a clean installed baseline.
- [ ] Resolve only supported patch versions and inspect the complete lockfile diff.
- [ ] Verify installed trees, audit results, frontend lanes, build, and generated-client stability.
- [ ] Obtain an independent review of the final patch.
- [ ] Commit and open a PR to `dev`; hand integration to the coordinating agent.
- [ ] Confirm repository alerts close after the fix reaches the default branch.

## Alert metadata and boundary assessment

The GitHub API reported both alerts as open and high severity on 2026-09-05. Severity is advisory
metadata; this investigation did not reproduce denial-of-service behavior or establish an
attacker-controlled input path in Hangar Bay.

| Alert | Locked package | Affected range | First patched version |
| --- | --- | --- | --- |
| [Nano ID custom-generator alert 9](https://github.com/scarson/hangar-bay/security/dependabot/9), GHSA-2v37-7h3g-55p8 | `nanoid@3.3.17` | `<3.3.18` | `3.3.18` |
| [js-yaml CPU-consumption alert 8](https://github.com/scarson/hangar-bay/security/dependabot/8), GHSA-5p4m-2wfm-xmqj | `js-yaml@4.3.0` | `>=4.0.0, <4.3.1` | `4.3.1` |

Version exposure is confirmed. Application exploitability remains unproven: production source
does not directly import either package. Nano ID is reached through Vite and PostCSS. It remains
in production-only npm installations because `@tailwindcss/vite` is a root dependency; the
observed project use is Node-side asset tooling, and deployment serves the generated static
`dist` directory. js-yaml supports ESLint and OpenAPI code generation through development
dependencies. ESLint uses JavaScript flat configuration, and code generation reads committed
`openapi.json` with internal references. These are bounded usage observations, not a claim that
all possible tool inputs are safe.

## Patch selection and provenance

Existing trusted coordinates come from
[`package-lock.json`](../../../app/frontend/web/package-lock.json), including
`https://registry.npmjs.org`. No package namespace, owner, or registry was invented. Registry
content was treated as dependency metadata, not instructions.

- PostCSS `8.5.25` accepts Nano ID `^3.3.16`, so `3.3.18` is permitted.
- ESLint's `@eslint/eslintrc@3.3.6` accepts js-yaml `^4.3.0`.
- `@redocly/openapi-core@1.34.18` pins js-yaml exactly `4.3.0`; changing only the js-yaml
  lock entry would violate this declared dependency.
- `openapi-typescript@7.13.0` accepts Redocly core `^1.34.6`. The existing npm registry reports
  Redocly core `1.34.19` with js-yaml `4.3.1`, allowing both to move by supported patches.

The selected boundary is dependency resolution: update Nano ID, Redocly core, and js-yaml in the
lockfile. No override, direct dependency, production-source change, or compatibility shim is
required. Configuration-only dependency updates are exempt from the repository's production-code
TDD requirement. Verification uses resolved versions and advisory scanning rather than exploit
payloads, plus the legitimate frontend and code-generation workflows.

## Independent investigation

A fresh read-only investigator independently verified the existing ranges and paths in the
lockfile, direct imports, flat ESLint configuration, committed OpenAPI input, and static deployment.
It agreed that a child-only js-yaml update would be invalid and that the compatible Redocly patch
is necessary. The investigator did not execute applications, tests, or exploit checks; the registry
observation for Redocly `1.34.19` was supplied by the implementing agent and will also be checked
against the actual resolved package during installation.

## Verification and integration

Results are recorded here by the implementing agent as each gate completes. Repository alert
closure can only be claimed after GitHub processes the merged default-branch dependency graph;
a clean local audit alone does not establish closure.
