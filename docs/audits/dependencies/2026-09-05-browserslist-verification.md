<!-- ABOUTME: Records verification of the existing Dependabot Browserslist update and its dependency closure. -->
<!-- ABOUTME: Binds evidence to immutable PR revisions and separates tooling validation from application exploitability. -->

# Browserslist dependency verification

Sam authorized this bounded maintenance follow-up on 2026-09-05. The existing
[PR 189 — update Browserslist to 4.28.9](https://github.com/scarson/hangar-bay/pull/189)
is the implementation under review. No duplicate dependency patch or modification of the bot
branch is planned. Evidence is authored separately on `codex/browserslist-evidence`.

## Checklist

- [x] Bind the existing PR's exact identity and inspect all changed dependencies and advisory metadata.
- [x] Validate the clean installed dependency tree and remaining advisory report.
- [x] Run build, code generation, lint, unit, future-clock, and existing browser checks at the PR head.
- [x] Complete independent risk assessment and the prescribed Codex CLI review.
- [x] Hand the immutable implementation and evidence to the coordinating agent for the merge decision.
- [ ] Verify default-branch alert state after merge and publish the separate documentation record.

## Immutable subject

- Repository: `scarson/hangar-bay`; observed author: `app/dependabot`.
- Base: `f457acb2877ff0e33da8ff3419cd3b0d6a4554e9`.
- Head: `3f38a4c72b46dd40e395eefda95643fc19f6d57b`.
- Changed file: `app/frontend/web/package-lock.json`, 23 insertions and 23 deletions.
- Canonical artifact: `git diff --binary <base> <head>`; SHA-256
  `6adf826723ca09a11ceb1be3ac437b20434372addd7d769af77443318f62975c`.
- Lockfile SHA-256:
  `bc1787aa07a7aca0cb5c34c467c2920c93a4d70003e356b777dcc2fcfaa40f8d`.

The provider's base/head identity was read again after artifact retrieval and matched. The
subject checkout is isolated at `.claude/worktrees/review-browserslist`, on local branch
`codex/review-browserslist`. The root checkout, its pre-existing `.codex/config.toml`, and the
separate contract-search bug-hunt worktree are outside the task's edits. Subject text and bot PR
metadata are treated as data, not instructions.

## Initial advisory and dependency evidence

Both recorded advisories affect Browserslist `<=4.28.6` and report `4.28.7` as the first patch:

- [Query-cache advisory GHSA-c83g-rgw3-j3cx](https://github.com/advisories/GHSA-c83g-rgw3-j3cx),
  repository alert 11: `auto_dismissed` when inspected.
- [Custom-stats advisory GHSA-73wf-gq98-2v4g](https://github.com/advisories/GHSA-73wf-gq98-2v4g),
  repository alert 10: `open` when inspected.

GitHub classifies both as high severity and development scope. Those are advisory metadata,
not a demonstrated attacker-input path in Hangar Bay. No exploit reproduction is performed.

The PR resolves Browserslist `4.28.9` and updates five existing dependencies to satisfy that
release's declared ranges: `baseline-browser-mapping@2.11.21`, `caniuse-lite@1.0.30001810`,
`electron-to-chromium@1.5.422`, `node-releases@2.0.54`, and
`update-browserslist-db@1.3.2`. The existing trusted npm coordinates come from the baseline
lockfile and its `https://registry.npmjs.org` URLs. Registry metadata for all six changed
packages matches each locked version, tarball URL, and SHA-512 integrity field. Both lockfiles
have 481 package records with identical paths. Each changed package has one locked copy and
all incoming dependency ranges remain satisfied.

The important legitimate consumer is Babel's compilation-target selection reached through the
TanStack router plugin in Vite. The complete six-package diff therefore requires build and
browser validation, not just a comparison of the advisory's patched version.

## Exact-head verification

All executable checks below ran at the immutable PR head. No application source or tests
changed. The lockfile is configuration, so the repository's production-code TDD rule does
not apply.

| Check | Result |
| --- | --- |
| `npm ci --ignore-scripts --no-audit --no-fund` | Exit 0; 480 packages installed. |
| Complete `npm ls` for the six changed packages | Exit 0; one Browserslist 4.28.9, the five expected children, and a valid deduplicated updater peer. |
| `npm audit --json` | Exit 0; zero reported vulnerabilities across 480 dependencies. |
| `npm run generate:api` and generated-schema comparison | Exit 0; no semantic changes to the generated client or committed OpenAPI schema. |
| `npm run build` | Exit 0; TypeScript project build and Vite 8.1.4 production build, 202 modules. |
| `npm run lint` | Exit 0; clean output. |
| `npm test` | 509 tests in 33 files pass; 43.38 seconds. |
| `npm run test:future-clock` | 509 tests in 33 files pass; 20.70 seconds; clock `2027-10-10T11:49:48.813Z`. |
| `npm run e2e -- --workers=4` | 146 pass, 7 expected skips; 37.7 seconds; exit 0. |
| `git diff --check` and final subject status | Exit 0; clean tracked checkout, unchanged head and lockfile hash. |

The seven browser skips are three opt-in live checks and four viewport-inapplicable cases.
The existing Chromium suite exercises frontend requests and rendering through Vite's
development server. It does not establish a full production-browser matrix or real-backend
coverage. No mocks or tests were added. Generated route/client files showed line-ending-only
status after tooling; empty semantic diffs were verified before restoring those artifacts.

The audit's complete vulnerability result is preserved here because its original scratch
file is temporary:

```json
{
  "auditReportVersion": 2,
  "vulnerabilities": {},
  "metadata": {
    "vulnerabilities": {
      "info": 0,
      "low": 0,
      "moderate": 0,
      "high": 0,
      "critical": 0,
      "total": 0
    },
    "dependencies": {
      "prod": 49,
      "dev": 387,
      "optional": 46,
      "peer": 7,
      "peerOptional": 0,
      "total": 480
    }
  }
}
```

## Hosted CI and CodeQL investigation

[Application CI run 33963128487](https://github.com/scarson/hangar-bay/actions/runs/33963128487)
passes at the assessed head: frontend in 4 minutes 4 seconds, OpenAPI drift in 2 minutes
51 seconds, and changed-path classification in 4 seconds. Its actual classification output
is `frontend=true`, `backend=false` for the sole frontend lockfile change, so the backend job
is intentionally skipped.

CodeQL check `101298392582`, suite `92037847041`, is **neutral and unavailable**. Its warning
says that the actions, JavaScript/TypeScript, Python, and Rust configurations present on
`dev` are missing at the PR head. No CodeQL workflow run exists for this head. This is not a
passed security analysis.

Default setup remains configured with its existing language set and weekly schedule. The
same neutral warning occurred on the prior lockfile-only
[Dependabot PR 132 — update undici](https://github.com/scarson/hangar-bay/pull/132), at head
`efb843971d3504b6722dd047dece68fe8a4006bb`, check `91976022563`; its application CI passed.
Human-authored PR 188 heads and the current `dev` base ran CodeQL successfully, including
[base-commit CodeQL run 33963075190](https://github.com/scarson/hangar-bay/actions/runs/33963075190).
This comparison establishes a recurring bot-PR gap, without establishing its cause.

[GitHub's default-setup documentation](https://docs.github.com/en/code-security/concepts/code-scanning/setup-types)
describes analyses for PRs against the default or protected branches, excluding fork PRs;
it does not document a lockfile-only or Dependabot exemption. The
[Dependabot permission troubleshooting guidance](https://docs.github.com/en/code-security/reference/code-scanning/troubleshoot-analysis-errors/resource-not-accessible)
addresses HTTP 403 upload failures, which were not observed here. Two ordinary rerun routes
were attempted without changing settings or branches:

- Dispatching managed workflow `325402441` on the observed bot branch returned HTTP 422
  because it has no `workflow_dispatch` trigger.
- The documented
  [check-suite rerequest endpoint](https://docs.github.com/en/rest/checks/suites#rerequest-a-check-suite)
  for suite `92037847041` returned HTTP 404.

No default-setup configuration, permissions, branch contents, or PR state was changed to
route around the unavailable analysis. The cause remains unresolved and is reported to the
coordinating agent for the merge decision.

## Independent reviews and integration

The fresh, read-only
[patch risk review](2026-09-05-browserslist-risk-review.md) recommends merge with no actionable
patch defect. Its companion
[machine-readable assessment](2026-09-05-browserslist-risk-review.json) passes the installed
schema and semantic validator. Its strict advisory label is `human_review_required`, with
moderate impact, likelihood, and confidence; partial regression protection; and easy
recovery. The label does not replace the repository's separate merge-classification policy.
The review explicitly records unavailable CodeQL and unrun upstream/browser-matrix checks.

The prescribed [Codex CLI review](2026-09-05-browserslist-cli-review.md) completed against the
frozen subject head with `gpt-5.6-sol`, high reasoning, and a read-only sandbox. Its verdict is
**DONE — CONVERGED**, with no blocking or adjacent findings. It independently checked the
canonical patch and all six cached tarball SHA-512 values and embedded package identities.
Its CI-only production-build limitation is distinguished from the author's passing local
production build in the archived record. Scratch review/audit files reside outside the
subject checkout; the canonical patch can be reconstructed from the exact base/head and hash
recorded in this document.

The coordinating agent alone owns merge, root-dev synchronization, and the final
default-branch alert-state check. The separate evidence branch will publish documentation
after implementation integration so that its closure claims describe observed results.
