<!-- ABOUTME: Records verification of the existing Dependabot Browserslist update and its dependency closure. -->
<!-- ABOUTME: Binds evidence to immutable PR revisions and separates tooling validation from application exploitability. -->

# Browserslist dependency verification

Sam authorized this bounded maintenance follow-up on 2026-09-05. The existing
[PR 189 — update Browserslist to 4.28.9](https://github.com/scarson/hangar-bay/pull/189)
is the implementation under review. No duplicate dependency patch or modification of the bot
branch is planned. Evidence is authored separately on `codex/browserslist-evidence`.

## Checklist

- [x] Bind the existing PR's exact identity and inspect all changed dependencies and advisory metadata.
- [ ] Validate the clean installed dependency tree and remaining advisory report.
- [ ] Run build, code generation, lint, unit, future-clock, and existing browser checks at the PR head.
- [ ] Complete independent risk assessment and the prescribed Codex CLI review.
- [ ] Hand the immutable implementation and evidence to the coordinating agent for CI-gated merge.
- [ ] Verify default-branch alert state after merge and publish the separate documentation record.

## Immutable subject

- Repository: `scarson/hangar-bay`; observed author: `app/dependabot`.
- Base: `f457acb2877ff0e33da8ff3419cd3b0d6a4554e9`.
- Head: `3f38a4c72b46dd40e395eefda95643fc19f6d57b`.
- Changed file: `app/frontend/web/package-lock.json`, 23 insertions and 23 deletions.
- Canonical artifact: `git diff --binary <base> <head>`; SHA-256
  `6adf826723ca09a11ceb1be3ac437b20434372addd7d769af77443318f62975c`.

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
lockfile and its `https://registry.npmjs.org` URLs. Browserslist's candidate registry metadata
matches its locked version, dependency ranges, tarball URL, and SHA-512 integrity field.

The important legitimate consumer is Babel's compilation-target selection reached through the
TanStack router plugin in Vite. The complete six-package diff therefore requires build and
browser validation, not just a comparison of the advisory's patched version.

## Verification and integration

The implementing agent records completed checks here. The independent risk assessment and
Codex CLI review will be linked after their verdicts exist. The coordinating agent alone owns
merge, root-dev synchronization, and final default-branch alert-state verification.
