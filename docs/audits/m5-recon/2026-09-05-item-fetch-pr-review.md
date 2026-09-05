ABOUTME: Preserves the adversarial review of the item-fetch preparation PR and its accepted correction.
ABOUTME: Records review provenance and separates publication checks from future implementation verification.

# Item-fetch preparation PR review — 2026-09-05

## Adversarial review

The installed Codex CLI ran `exec review` with GPT-5.6 Sol, high reasoning, a read-only sandbox and approval policy `never`, against base `a2ac558f1fbb0689ff1a91ccfcbc7249816eeb24`. The preparation tip at dispatch was `62f23d4a0b1b1477c6e85cdf052448603fd4d7e3`. The coordinator added only the independent handoff report during the review; the plan bytes remained unchanged until the review returned. Completion was observed at `2026-09-05T20:03:49Z`, with exit code zero and the following actionable result.

The final reviewer output's SHA256 was `3597C6D2955FDCA104D8156C6094921ADAE9A3EDC3B5F99B71D927814EF5332B`. Its finding, preserved verbatim:

> [P2] Scope the retry-attempt assertion to page 3 — docs/plans/2026-09-05-ingestion-item-fetch-integrity-plan.md:288
>
> When the failure occurs on page 3 after pages 1 and 2 succeed, the transport receives five requests overall: one for each successful page and three attempts for page 3. Therefore, “Assert three HTTP attempts” is ambiguous and becomes false if implemented as the client's total call count; require five total requests, three page-3 attempts, and the ordered URLs so the test proves the failing page was reached, consistent with TEST-25 (`docs/pitfalls/testing-pitfalls.md:170`).

## Disposition

**Raised: 1; accepted: 1; rejected: 0.** The coordinator verified `_get_with_transient_retry` in `app/backend/src/fastapi_app/core/esi_client_class.py`: three attempts and two waits of 0.5 and 1.0 seconds. The [plan's failure-preservation test](../../plans/2026-09-05-ingestion-item-fetch-integrity-plan.md#phase-1--complete-uncached-item-reads) now requires five item requests for the failing fetch, with ordered pages `[1, 2, 3, 3, 3]`. Collection is scoped to that contract and that fetch so seed/recovery requests, metadata and the succeeding contract cannot contaminate the count. No production code or retry policy changed.

The original five-round plan certification and its editorial pass remain historical evidence. This correction is the later PR-review disposition. The [fresh preparation PR review](2026-09-05-item-fetch-pr-final-review.md) verified the corrected request-count contract and raised one additional monitoring seam: the required `X-Pages` response header is outside the ESI drift monitor's projection. The coordinator confirmed the missing coverage against the monitor and the ESI dependency checklist. That finding must be resolved before this preparation merges. The future implementation's TDD, mutation checks and independent reviews remain required; baseline tests do not verify this unimplemented behavior.

## Header-monitor amendment

**Fresh-review findings raised: 1; accepted: 1; rejected: 0.** The [bounded amendment analysis](2026-09-05-item-fetch-header-monitor-amendment.md) identified reuse of the existing monitor's shape, consumer-attribution and missing-dependency comparisons. The coordinator incorporated its contract into Task 1, expanded its scope and staging from three to seven files, and permitted only CLI regeneration of the monitor snapshot. The two production tasks and their merge classification are unchanged.

The amendment preserves upstream header optionality, limits projection to declared 200 response headers, distinguishes header dependencies from body fields/parameters, and requires explicit tests for reference resolution, casing, missing declarations, drift severity and duplicate suppression. The coordinator checked the actual comparison helpers, pytest configuration and CLI before incorporating it. The proposal's PDM command was corrected to the relocated module invocation, and the plan requires investigating a changed upstream declaration rather than asserting stale live metadata.

The [final artifact verification](2026-09-05-item-fetch-pr-verification.md) returned zero new findings after checking the complete amended plan and all six handoff perspectives. Both accepted PR findings are resolved at the documentation level, with no rejection or verification item pending. The coordinator checked the recorded plan and handoff hashes against the final files. This review concerns the final preparation artifacts; no implementation, snapshot generation or production test verification occurred here.
