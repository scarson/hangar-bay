ABOUTME: Records the cold independent review of the contract item fetch integrity implementation plan.
ABOUTME: Preserves review provenance, the reviewed draft hash, and the exact as-raised finding.

Provenance: GPT-6 Astra high, cold independent review.

Reviewed draft SHA256: `81CD6A09568F0437B7C2AAD22EFA2772C9CCE810CC1712D977F2FDA0C1064DB3`

**As-raised substantive findings: 1.**

- **Task 1, database-seam transport-failure instructions** — “check the final error’s cause.” **Dimension: context gap / ambiguity.** The shared retry helper raises `ESIRequestFailedError` after leaving the `except` block, without `from last_exception` ([esi_client_class.py:416](/C:/Users/Sam/Code/hangar-bay/.claude/worktrees/ingestion-pipeline-plan/app/backend/src/fastapi_app/core/esi_client_class.py:416)). Consequently, the final transport error has no chained `ConnectError` cause. The proposed item walk does not change that behavior, leaving an executor to invent either a cause-preservation change or an assertion that the cause is absent. **Minimal correction:** replace this instruction with explicit assertions on the logged exception’s `ESIRequestFailedError` class, `status_code == 0`, and complete network-error message. Keep cause-preservation assertions on the newly introduced JSON/header decoding errors, whose proposed implementation explicitly chains the original exception.
