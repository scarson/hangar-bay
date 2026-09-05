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
- [x] Establish a clean installed baseline.
- [x] Resolve only supported patch versions and inspect the complete lockfile diff.
- [x] Verify installed trees, audit results, frontend lanes, build, and generated-client stability.
- [x] Obtain an independent review of the final patch.
- [x] Complete the handoff-prescribed Codex CLI adversarial review on the committed patch.
- [x] Commit and open a PR to `dev`; hand integration to the coordinating agent.
- [x] Confirm repository alerts close after the fix reaches the default branch.

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
observation for Redocly `1.34.19` was supplied by the implementing agent. The installed package's
version and exact js-yaml `4.3.1` dependency were subsequently verified against that observation.

## Verification and integration

The npm-generated diff changes only three dependency records, with 10 insertions and 10
deletions. The direct dependency manifest is unchanged. The lockfile SHA-256 is
`349aa3ade679fb7263b2d0f8af6481a9ed13cf8d2c6c007a9f4d0839acb2f78a`.

Commands run from `app/frontend/web`:

| Gate | Command or check | Result |
| --- | --- | --- |
| Baseline | `npm ci --no-audit --no-fund`; `npm test` | 480 installed packages; 33 files, 509 passing tests |
| Resolution | `npm update nanoid js-yaml @redocly/openapi-core --package-lock-only --ignore-scripts --no-audit --no-fund --registry=https://registry.npmjs.org` | Only the three supported patch updates |
| Clean installation | `npm ci --no-fund` | Exit 0; 480 installed packages |
| Dependency validity | `npm ls nanoid js-yaml @redocly/openapi-core postcss --all` | Exit 0; patched versions, no invalid ranges |
| Production installation scope | `npm ls nanoid js-yaml --all --omit=dev` | Exit 0; only Nano ID remains, at `3.3.18`, through Tailwind/Vite/PostCSS |
| Complete lock inspection | Enumerate every matching package path and assert the version, registry, and SHA-512 field; inspect the installed Redocly manifest | Exactly one copy each of Nano ID `3.3.18`, js-yaml `4.3.1`, and Redocly `1.34.19`; installed Redocly requires js-yaml `4.3.1` |
| Advisory scan | `npm audit --json` | Neither requested package appears; exit 1 for the separate Browserslist residual described below |
| Generated client | `npm run generate:api`; `git diff --exit-code -- src/lib/api/schema.d.ts openapi.json` | Exit 0; generated API client and input schema unchanged |
| TypeScript and production assets | `npm run build` | Exit 0; `tsc -b` and Vite production build succeeded |
| Lint | `npm run lint` | Exit 0; no warnings or errors |
| Unit/component tests | `npm test` | 33 files, 509 passed |
| Future-clock tests | `npm run test:future-clock` | 33 files, 509 passed; clock `2027-10-10T10:52:03.271Z` |
| Existing browser tests | `npm run e2e -- --workers=4` | Exit 0; 146 passed, 7 expected skips; 46.6 seconds |
| Scope and whitespace | `git diff --check`; inspect manifest/generated-file diffs | No substantive source or manifest changes; no whitespace errors |

Browser skips are the existing three opt-in live-smoke cases and four viewport-inapplicable
cases. No browser fixtures or mocks were added or changed. The browser command ran with normal
Windows child-process permissions after verifying port 5173 was free; it released that port at
completion. Inherited `NO_COLOR` was removed because Playwright sets `FORCE_COLOR`. Generated
client/router files acquired only line-ending status from normal tools, and those artifacts were
restored after confirming their substantive diffs were empty.

The strongest focused evidence for remediation is removal of all affected installed/locked
versions plus absence of the two requested packages from the npm audit result. No exploit
reproduction was performed. Legitimate asset processing, linting, code generation, and existing
frontend behavior passed their applicable checks. Backend tests and live production smoke were
not rerun for this dependency-only patch; the PR's OpenAPI drift job remains the complete
backend-export/client-generation gate.

### Fresh patch review

A fresh read-only reviewer returned **CONVERGED — no findings** against the lockfile diff from
`74cb0f6e26c882c31fea033ce25e72cb2e1677dc`. It independently verified single patched copies,
incoming dependency ranges, unchanged manifest, registry tarball URLs and integrity fields,
and recomputed the cached tarballs' SHA-512 values. It inspected PostCSS's Nano ID caller,
ESLint's YAML callers, and Redocly's parsing/code-generation integration. No tests, applications,
installations, or exploit payloads were run by that reviewer. Its registry verification used
cached metadata and archives; a separate coordinating review also checked live registry metadata.
Neither review found a concrete surviving affected copy, range violation, or regression.

### Committed-patch Codex review and PR

The handoff-prescribed Codex CLI review used `gpt-5.6-sol` with high reasoning effort in read-only,
ephemeral mode, with its prompt supplied on standard input and output redirected to task-local
files. It completed with exit 0 and **CONVERGED — no blocking findings**, reviewing base
`d43da7c9313de7ce19aa9de21242b07949da4364` through implementation commit
`4dafe78a2cb533ce8093ff038adfe62bfea6f05e`.

The reviewer checked the complete four-file diff, all tracked manifests/lockfiles, every matching
package copy and incoming range, installed tooling callers, registry URLs and integrity metadata,
cached tarball SHA-512 values, and the documented lockfile SHA-256. It confirmed the manifest,
OpenAPI input, generated schema, and generated router remained unchanged and `git diff --check`
passed with a clean tracked worktree. It accepted the documented Browserslist residual and the
limits on application exploitability and GitHub closure. It did not execute tests, builds,
applications, installs, audits, code generation, or exploit payloads.

[PR 188 — patch Nano ID and js-yaml dependency alerts](https://github.com/scarson/hangar-bay/pull/188)
contains the implementation and final documentation evidence. Its classification is **Routine**:
supported transitive patch updates to frontend build/lint/code-generation tooling, with no project
security-boundary code, public interface, schema, or data-integrity behavior change. The
coordinating agent owns final-head CI verification, merge, and default-branch alert-closure checks.
The PR is the authoritative source for current integration state; only documentation changed
after the reviewed implementation commit.

PR 188 merged on 2026-09-05 at `11:20:34Z`, producing
`f457acb2877ff0e33da8ff3419cd3b0d6a4554e9`. A subsequent GitHub API read reports both alerts
8 and 9 as `fixed`, each with `fixed_at: 2026-09-05T11:20:37Z`, on default branch `dev`.

### Separate Browserslist residual recorded during this review

The full npm audit at this patch's head reported one high-severity vulnerable package, `browserslist@4.28.6`, with
[unbounded-query-cache advisory GHSA-c83g-rgw3-j3cx](https://github.com/advisories/GHSA-c83g-rgw3-j3cx)
and [custom-stats advisory GHSA-73wf-gq98-2v4g](https://github.com/advisories/GHSA-73wf-gq98-2v4g).
Both reported affected ranges include `<=4.28.6`. The version, registry URL, integrity, and
development-only marker are identical in the pre-patch `d43da7c` lockfile; this patch did not
introduce the exposure. The installed path is `@tanstack/router-plugin` -> `@babel/core` ->
`@babel/helper-compilation-targets` -> `browserslist`, with a deduplicated reference from
`update-browserslist-db`. An attacker-controlled project input path was not established and no
advisory behavior was reproduced.

Per the repository's out-of-scope journal rule, the coordinating agent retained this as a separate
maintenance follow-up rather than expanding Sam's two-alert request. It does not invalidate
the two-package remediation; the audit at this patch's head was not entirely clean.

That separate follow-up is complete through
[PR 189 — update Browserslist to 4.28.9](https://github.com/scarson/hangar-bay/pull/189). The
[Browserslist verification record](2026-09-05-browserslist-verification.md) preserves the complete
six-package review, zero-vulnerability audit, legitimate-workflow validation, restored CodeQL
analysis, and observed alert closure. No advisory reproduction or application-exploitability
claim was added.
