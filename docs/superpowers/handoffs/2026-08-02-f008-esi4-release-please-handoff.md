<!-- ABOUTME: Session-close handoff for 2026-08-02 — the F008 spec and its four review rounds, the ESI -->
<!-- ABOUTME: compatibility-date pin, release-please adoption, and the first user feedback the project has. -->

# Handoff — F008 spec, ESI-4 pin, release-please (2026-08-02, session close)

**Read this first, then [`design/features/F008-Type-Aware-Contract-Browsing.md`](../../../design/features/F008-Type-Aware-Contract-Browsing.md).**

## 1. Headline state

| | |
|---|---|
| `dev` | `379048d` |
| `main` (production) | **`fe43bda` — advanced this session for the first time since `7a95118`** |
| Released | PR #126, 81 commits, merged |
| Merged this session | #122 (ESI-4), #123 (F008 spec), #124 (release-please), #125 (handoff), #126 (release) |
| CI on `dev` | ✅ green |

**The release shipped.** `main` moved from `7a95118` to `fe43bda`, which triggered CI → Deploy on the production path and fired Release Please for the first time.

**Release Please is working.** Its first run failed to open a PR because the repository forbade Actions from creating pull requests; that setting was enabled and the workflow re-run, producing **PR #128 `chore: release main`** proposing `0.2.0`. Merging #128 is the next action — see §8 item 1, including one caveat about the published release notes.

## 2. What shipped

**[PR #122] ESI compatibility date pinned.** Hangar Bay sent no `X-Compatibility-Date`, and ESI answers a header-less request at the **oldest** published date — so every call was answered from a `2020-01-01` contract CCP chose for us. Now pinned to `2026-07-21`, the newest. Behaviorally a no-op: all nine consumed routes are byte-identical across that range. It unblocks `/meta/status`, which does not exist at the old floor and which ESI-1 wants for upstream health.

The non-obvious half: `fetch_specs()` in the spec monitor deliberately fetched its `pinned` view **with no header**, to mirror a header-less client. Left alone it would have watched `2020-01-01` while production requested `2026-07-21` — a monitor reporting a safety it cannot see. It now pins the same date, duplicated as `PINNED_COMPATIBILITY_DATE` because the tool is standard-library only and cannot import `Settings`. Three tests guard this, each mutation-verified; the one that matters is `test_monitor_pins_the_same_date_the_client_sends`, because the snapshot test alone would not catch both moving together.

**[PR #123] F008 — Type-Aware Contract Browsing.** The feature spec for making the ~98.8% of ingested contracts that are not ships a designed surface. Closes two long-standing spec gaps: the F002-vs-M1 market-group conflict (superseded — mechanism changes to dogma category/group, requirement preserved; F002 carries a pointer) and the total absence of a courier policy (couriers are now a first-class type with stated coverage limits). Includes the courier reward-per-jump spike and the MCP spec/code-mode spike.

**[PR #124] release-please adopted.** Config, manifest, workflow. **It does nothing until it reaches `main`** — a workflow only runs from the branch it lives on — so it activates *with* the next publication PR, and its first release PR will cover all 78 commits.

**First user feedback recorded** — [`design/user-feedback/2026-08-01-capital-ship-order-workflow.md`](../../../design/user-feedback/2026-08-01-capital-ship-order-workflow.md). See §4.

## 3. F008: what a fresh agent must know before touching it

The spec went through **four adversarial review rounds** (one codex, three independent Opus). Its shape is a consequence of what those rounds found, and undoing that shape will reintroduce the defects.

**Three subsections are canonical and must not be restated elsewhere.** §3.1 (item-level filter semantics), §5.1 (location resolution), §5.2 (taxonomy cache). Every other section points at them. This is deliberate: the location-resolution fact previously lived in five sections and went stale in four of them across three rounds. **If you fix something in one of these, grep the document for the old claim before committing.**

**§17 is a normative API contract** — response models by name and field, envelope shapes, endpoint payloads, parameter shapes. It exists because a planner-lens reviewer found the backend and frontend halves could not be built independently without it.

**§7.1 records four single-writer resources** that make the obvious decomposition fail. The sharpest is a production hazard, not a test failure: `alembic/versions/` is a linear chain and `alembic upgrade head` is `render.yaml`'s `preDeployCommand`, so four tasks each writing a migration produce `Multiple head revisions` and **break the deploy**. All schema changes must be one migration authored once, up front.

**Scope decisions embedded in the spec, with reasons:**

- **Abyssal display deferred** to its own plan. `item_id` is persisted in v1 specifically so the follow-on needs no corpus re-ingest.
- **Courier reward-per-jump deferred** to its own plan, despite the spike measuring the whole live Forge courier population at 161 ESI calls / 8.4s cold. It was the largest block of net-new machinery serving 0.34% of the corpus, and the only part depending on the ESI compatibility date. The seam is drawn so `end_location_system_id` still lands in v1 — the follow-on is purely route lookups plus presentation.
- **Taxonomy axis is dogma category/group**, not market groups. The deciding reason is the abyssal follow-on: abyssal items are off-market by construction and have no market group at all, so a market-group axis would need a second taxonomy or leave the largest non-ship cluster unfilterable.
- **Instrumentation is server-side.** There is zero frontend telemetry in the repo — no library, no references — so client-side event tracking would be net-new infrastructure. Filter dimensions ride the existing structlog → Grafana Cloud path instead.
- **No success threshold.** The app has one user and has not been advertised, so no adoption metric can produce signal. §15.4 records this rather than resolving it.

## 4. The user feedback, and why it is load-bearing

Every argument for the contract-browsing direction is **supply-side** — we ingest the data, therefore we should show it. No user has asked for it. One user asked for something else.

Asked whether anyone would plausibly use Hangar Bay, a capital-ship builder said he would use it for his business and then described a **build-to-order shop management system**: alliance-gated SSO, order placement, ISK deposit verified via ESI, status tracking, delivery confirmation, Discord notifications. Read carefully, that is a redirect, not validation of the current direction.

It also retroactively justifies keeping the four permanently-NULL columns (`status`, `date_completed`, `raw_quantity`, `is_singleton`) — his delivery-polling step needs exactly the authenticated character/corp contract routes those columns belong to.

**Six follow-up questions were sent 2026-08-02; no reply yet.** The decisive one asks whether he would use a ME/TE/runs-filtered contract browser to source **capital component blueprints** — one of the two largest non-ship clusters. Yes means F008 and his request converge. No means they are two products competing for the same time.

**Do not put his name in the repository.** He has not consented to appearing in a public project. The record identifies him by role.

## 5. Seams — where this session's work meets something else

*   **Two workflows now run on every push to `main`, and that is correct.** `gh run list --branch main` shows **CI** and **Release Please** starting at the same second on the same SHA. They are different workflows, not a duplicated CI run. Deploy then fires separately via `workflow_run` after CI completes. Anyone auditing for duplicate triggers should check `workflowName` before concluding anything — the run list alone looks like a double-fire.
*   **Release Please ran on `fe43bda`, did all its work correctly, and then failed on the last step — a repo setting, not the config.** The run errors with `GitHub Actions is not permitted to create or approve pull requests`. Verified via `gh api repos/scarson/hangar-bay/actions/permissions/workflow`: `can_approve_pull_request_reviews` is `false`. **Fix: Settings → Actions → General → Workflow permissions → enable "Allow GitHub Actions to create and approve pull requests."** It is repo-wide, so any workflow gains the ability; acceptable on a single-owner repo. Leave `default_workflow_permissions` at `read` — the workflow declares its own `pull-requests: write`, which is why it got as far as it did.

    **The config itself is proven working**, so do not "fix" it. The action created branch `release-please--branches--main` (commit `0152d61`) before failing, and diffing that branch against `main` shows exactly the intended result: `app/backend/pyproject.toml` `0.1.0` → `0.2.0` (the `x-release-please-version` annotation works), `app/frontend/web/package.json` `0.0.0` → `0.2.0` (the jsonpath works), a 459-line `CHANGELOG.md`, and a bumped manifest. Once the setting is enabled, re-run the workflow; the branch already exists and it will open the PR.

    Two benign log lines that look like problems and are not: `⚠ file version.txt did not exist` (first run; the manifest is the source of truth) and `⚠ pullRequestTitlePattern miss the part of '${scope}'` (informational, about the default title template).
*   **A cancelled run on `dev` is usually not a failure.** #123's run shows `cancelled` because #124's push superseded it via the `ci-${{ github.ref }}` concurrency group. The authoritative run is the latest one for the ref.
*   **Each release cycle produces two deploys** — one from the publication PR (real code) and one from the release PR (changelog and version files only). Harmless; it does prove the tagged SHA deploys.
*   **The ESI-4 pin constrains the courier follow-on.** `/route/{origin}/{destination}` is a hard cutover at compatibility date `2025-09-30`: `GET` with query params below it, **`POST`** with a JSON body, renamed preference values and an object envelope at or above. The old shape returns 404. We now send `2026-07-21`, so **any future `/route/` call must use the POST form.**
*   **`min_me` is still lying in production.** `min_me=10` returns the full result set unchanged; `min_runs=5` returns zero. Six inert params in two failure modes. See §6.
*   **Local `dev` is behind `origin/dev`.** The main checkout sits at `fd34148`. Realign with `git fetch origin dev && git reset --hard origin/dev` — never a merge or a GUI Sync.
*   **Worktree debt: 11 live, nearly all on merged branches.** `item-schema-cleanup`, `retire-dead-columns`, `location-system-resolution`, `future-clock-lane`, `handoff-final`, `m3-account-features`, `m5-acceptance-numbers`, `esi-compat-date`, `release-please`, and this one are all reclaimable. **Do not delete a worktree that has long-lived containers bound to it** (pitfall ENV-10).

## 6. Deferred items, each with its unblock condition

| Item | Unblock condition | Where the unblocker lives |
|---|---|---|
| Fix the inert `min_me`/`max_me`/`min_te`/`max_te` filters | Fold into F008's **single** item-level migration. Doing it standalone pays the ~80-minute `ENRICHMENT_VERSION` resweep twice, and that resweep is a single-writer resource | F008 §7.1, Criterion 2.5 |
| Alternatively: make those params hard-error now | Independent of everything; a small breaking API change that stops the lie without delivering capability. Needs a decision, not a prerequisite | — |
| Abyssal / mutated module display | Its own plan. `item_id` already persisted by F008 v1, so no re-ingest needed | F008 §4.2 |
| Courier reward-per-jump | Its own plan. Everything it inherits — measured costs, the high-sec default and its primary source, the per-row tier-disclosure pattern, three correctness traps, two implementation traps, and the required manifest entry — is recorded so it is not re-derived | F008 §15.2 + the courier spike |
| Adopt `/meta/status` for upstream health | **Now unblocked** — it exists at `2026-07-21` and did not exist at the old floor | pitfall ESI-1 |
| MCP surface | Downstream of M5 trust work. The spike verified the prior position survives the `2026-07-28` spec revision with no reversals, and recommends discrete hand-written tools over code mode | `2026-08-01-mcp-spec-and-code-mode-spike.md` |
| Character/corp contract ingestion | Needs per-user ESI tokens → token-lifecycle and privacy questions the public pipeline does not have. Strengthened by the user feedback in §4 | gap analysis §4.2 |
| A pitfalls entry for the alembic-multiple-heads hazard | Worth allocating an ID against `origin/dev` and writing up — it is general to any multi-task migration work, not specific to F008. Currently captured only in F008 §7.1 | see §8 |

## 7. Operational guardrails from this session

*   **Do not put third-party names in the repository.** A first name reached a pushed commit before it was caught. The commit was rewritten and force-pushed with lease, but the orphaned SHA stays reachable on GitHub until garbage-collected. Scrub before pushing, not after.
*   **A fact restated in N sections goes stale in N-1 of them.** Make one section canonical, make the rest pointers, and grep for the old claim after any fix that adds a requirement. This cost four review rounds.
*   **Decorrelated review lenses beat more rounds of the same lens.** Three rounds asked "is this true?" The round that asked "**can this be executed?**" found problems none of them did, including an acceptance criterion that was arithmetically impossible to satisfy.
*   **Script the consistency check.** A short Python pass for dangling/duplicate references and stale phrases caught an error four rounds of reading had missed. Read the hits — naive probes produce false positives on cross-document references and negated phrasing.
*   **`mktemp` on macOS needs the X's at the end of the template.** `foo-XXXXXX.txt` fails with "File exists"; use a scratchpad path with explicit names instead.
*   **codex times out on large prompts.** A 67 KB prompt stalled past 5.5 minutes; scoping to a single file and giving it a 15-minute background budget worked.
*   **Fresh worktrees need `pdm install` *and* `app/backend/src/.env`.** The conftest imports `fastapi_app.main`, which constructs `Settings()` at module scope, so tests cannot even collect without it. Copy `app/backend/.env.example` to `src/.env` and fill the three required keys. **Never read the repo-root `.env`** — 1Password-managed, can hang past 120s.
*   **Mutation-verify by file copy, never `git checkout --`.** The latter discards uncommitted work and yields fake evidence. Always end with a restore-and-rerun green check.
*   **Merge with `--body ""`, always.** GitHub writes the PR title into every merge commit's message and release-please parses merge commits, so each merged PR generated **two** changelog entries. Measured on the first release: **82 of 425 bullets (19%) came from merge commits.** Only 32 were visible text duplicates; the other 50 were merge commits whose PR title differed from any commit subject inside the PR, so they read as legitimate distinct entries while being redundant — the worse half, because nothing looks wrong.

    **No repository setting can fix this.** GitHub permits exactly three merge title/message combinations — `PR_TITLE`/`PR_BODY`, `PR_TITLE`/`BLANK`, `MERGE_MESSAGE`/`PR_TITLE` — and all three place the PR title where release-please will parse it. Attempting `MERGE_MESSAGE`/`BLANK` returns HTTP 422. The fix is therefore at merge time and lives in `docs/git-strategy.md`: `gh pr merge <n> --merge --delete-branch --body ""`. **A merge performed through the GitHub UI will reintroduce the problem** unless the message box is cleared by hand.

*   **`delete_branch_on_merge` is now enabled.** Merged head branches are removed automatically. `dev` is safe from this two ways: it is the default branch, and the active ruleset carries a `deletion` rule. Worktrees still need removing by hand — and never remove one with long-lived containers bound to it (ENV-10).

*   **The active ruleset is named `main-branch-protections` but targets `~DEFAULT_BRANCH`, which is `dev`.** So the protections named for `main` are applied to `dev`, and **`main` — the release branch production deploys from — has none**. Not changed this session; flagged because the name actively misleads anyone auditing it.

*   **CI's trigger set is deliberate; read the comment before "fixing" it.** `push: [dev, main]` plus an *unfiltered* `pull_request` looks like a duplicate-trigger bug and is not. Feature PRs (`claude/*` → `dev`) run once, because pushes to `claude/*` do not match the push filter. The unfiltered `pull_request` exists so stacked PRs based on another `claude/*` branch get CI at all — a `branches: [dev, main]` filter matches the PR's **base**, which would leave stacked PRs with no run. The one real duplication is that a `dev` → `main` publication PR re-tests a tree that push-to-`dev` already tested: one extra run per release cycle, which is cheap insurance against the "no CI ran" ambiguity the merge-authority policy treats as failure. **Leave it.**
*   **Push feature branches early.** The F008 spec branch went a full session unpushed and existed only in a worktree. Nothing enforces this; the habit is the safeguard.

## 8. Priority queue

1. **Merge PR #128 (`chore: release main`)** — the `0.2.0` release. Its `CHANGELOG.md` has been hand-cleaned of the 82 merge-commit entries (§5), so merge it rather than letting release-please regenerate. Merging tags `v0.2.0`, publishes a GitHub Release, and triggers a second (code-identical) deploy. `0.2.0` is confirmed — do not revisit it. **Caveat: the GitHub Release body is generated from release-please's own notes branch, which was not cleaned, so the published release notes will still carry the 82 spurious entries.** Edit the release body after publishing if that matters; the committed `CHANGELOG.md` is the durable artifact and it is clean.
2. **Confirm the production deploy of `fe43bda` succeeded** and the site is healthy. This release carried two `feat!` serialization changes, so the frontend is the thing to eyeball: contract list and detail rendering, not just an HTTP 200.
3. **Read the user's reply** when it arrives. Q4 decides whether F008's blueprint surface has a validated user.
4. **Write the F008 implementation plan** via `superpowers-plus:writing-plans-enhanced`, then `plan-review-cycle`. Start from §17 (API contract) and §7.1 (decomposition constraints) — those exist specifically to make the plan writable.
5. **Decide the `min_me` question** (§6) — fold in, or stop the lie now.
6. **Reclaim the worktrees** in §5.
7. Optional: write the alembic-multiple-heads pitfall.

## 9. Continuation prompt (paste-ready)

> Pick up the Hangar Bay work. Read `docs/superpowers/handoffs/2026-08-02-f008-esi4-release-please-handoff.md` first, then `design/features/F008-Type-Aware-Contract-Browsing.md` — specifically §3.1, §5.1, §5.2 (canonical subsections that must not be restated elsewhere), §7.1 (decomposition constraints), and §17 (the normative API contract).
>
> State: `dev` is at `7153ee7` with CI green, 78 commits ahead of `main`; production is `7a95118` and untouched. No open PRs except the handoff itself. First action: open the `dev` → `main` publication PR. (If you scan `gh run list --branch dev`, #123 shows `cancelled` — that is the concurrency group superseded by #124, not a failure; #124's run is the authoritative green one.) That PR is what activates release-please, whose first release PR will cover all 78 commits at version `0.2.0` unless the manifest is changed to `1.0.0` first.
>
> Do not re-derive: the F008 taxonomy axis (dogma category/group, decided on the abyssal follow-on), the courier reward-per-jump deferral and everything it inherits (§15.2), or the ESI compatibility date (`2026-07-21`, pinned in both the client and the spec monitor, guarded by a test). Do not restate the canonical subsections — point at them.
>
> Do not put the name of the player whose feedback is recorded in `design/user-feedback/` into the repository; he has not consented and the record identifies him by role deliberately.

## Appendix — adversarial review of this handoff

**Round 1 — naive fresh agent (4 findings applied).** Added the tip SHA, the unreleased count, and production's SHA to a headline table rather than leaving them in prose. Spelled out that release-please cannot act until it reaches `main`, which reads as a bug otherwise. Named what F008 *is* in one line before referring to its sections. Stated the `min_me` symptom concretely rather than as "the inert filters."

**Round 2 — recency bias (3 findings applied).** The morning's F008 review work was under-represented against the evening's release tooling. Restored: the four scope decisions with their reasons (§3), the taxonomy deciding-reason, and the fact that instrumentation went server-side because no frontend telemetry exists — a finding that cost a check to establish and would otherwise be re-litigated.

**Round 3 — seams (5 findings applied).** Documented the cancelled-vs-failed CI distinction, which would otherwise read as a red `dev`. Added the two-deploys-per-release consequence. Added the ESI-4 → `/route/` POST constraint as a seam rather than burying it in the deferred table. Noted local `dev` is behind. Added worktree debt with the ENV-10 caveat.

**Round 4 — operational guardrails (4 findings applied).** §7 existed only as scattered prose. Added the fresh-worktree `.env` mechanic with its cause (module-scope `Settings()` in the conftest import chain), the macOS `mktemp` trap, the codex prompt-size limit, and the mutation-revert rule.

**Round 5 — loss-averse (3 findings applied).** Recovered from transcript only: that the F008 branch was unpushed for the entire session and nearly lost, the orphaned-commit caveat on the name scrub, and the `/meta/status` deferral being *newly unblocked* by this session's pin rather than still blocked.

**Round 6 — "privacy and disclosure auditor" (session-specific, 3 findings applied).** Chosen because this session's distinguishing event was leaking a third party's name into public history and then remediating it imperfectly. The failure mode is a future agent re-introducing the name from the local memory, the chat log, or helpfulness. Applied: an explicit prohibition in §4, a repeat of it in the continuation prompt where a fresh agent will actually see it, and an honest statement in §7 that the orphaned SHA remains reachable rather than implying the scrub was total.

**Round 7 — "is the next action unambiguous?" (2 findings applied).** Chosen because this handoff's whole purpose is to enable one specific next step, and rounds 1–6 all audited content rather than actionability. Found that "confirm CI then publish" was stated in three places with different amounts of detail, and that the release-please version decision was buried in §5 while being a step-2 blocker. Consolidated into §8 with the CI caveat attached.

Final pass through rounds 1–7 produced zero further material findings.
