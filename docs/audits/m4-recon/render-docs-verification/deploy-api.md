<!-- ABOUTME: Docs-verified contract for the Render public API deploy-create + poll flow, for the M4 CI deploy job. -->
<!-- ABOUTME: Evidence is official Render docs only (no API access this session); every answer carries a confidence label. -->

# Render Deploy API — documentation verification (M4 CI deploy job)

**Session constraint:** No Render API credential available; official documentation is the only evidence source.
**Primary sources:** `https://api-docs.render.com/reference/*` (ReadMe-hosted; the full OpenAPI 3.0.2 spec is embedded in the page HTML and was extracted directly) and `https://render.com/docs/*`.
**Method note:** The interactive reference pages are client-side rendered, so response schemas do not appear to a plain fetch. The authoritative field/enum/response data below was extracted from the embedded OpenAPI JSON in the raw HTML of `https://api-docs.render.com/reference/create-deploy` (485 KB; contains the entire spec inline), which is more reliable than the rendered prose.

---

## Q1 — POST /v1/services/{serviceId}/deploys: request body fields + response status codes

**Confidence: documented**

- **Method/path:** `POST https://api.render.com/v1/services/{serviceId}/deploys` — "Trigger a deploy for the service with the provided ID."
- **`requestBody.required: true`.** Request body properties (verbatim from the embedded spec):
  - **`commitId`** (string) — YES, accepted for pinning a commit. "The SHA of a specific Git commit to deploy for a service. Defaults to the latest commit on the service's connected branch." Also documents: "deploying a specific commit with this endpoint does not disable autodeploys" and "Not supported for cron jobs."
  - **`clearCache`** (string enum) — YES, accepted. `enum: ["clear","do_not_clear"]`, `default: "do_not_clear"`. "If `clear`, Render clears the service's build cache before deploying. This can be useful if you're experiencing issues with your build."
  - **`imageUrl`** (string) — "The URL of the image to deploy for an image-backed service." Host, repository, and image name must match the currently configured image.
  - **`deployMode`** (`$ref DeployMode`, enum `deploy_only` / `build_and_deploy`, default `build_and_deploy`) — "**Validation:** `deploy_mode` cannot be combined with `commitId` or `imageUrl` or `clearCache`."
- **Documented response status codes (createDeploy operation):** `201` Created, `202` Queued, then shared error responses `400`, `401`, `404`, `406`, plus the API-wide set `409`, `410`, `429`, `500`, `503`. **Both 201 and 202 are documented success codes** — the create can return either.

**URL:** https://api-docs.render.com/reference/create-deploy

---

## Q2 — Response body on create: does it always include a deploy "id"? What does a 202 carry?

**Confidence: documented**

From the createDeploy operation's `responses` block (verbatim):

```json
"responses": {
  "201": { "description": "Created",
           "content": { "application/json": { "schema": { "$ref": "#/components/schemas/deploy" } } } },
  "202": { "description": "Queued" },
  ...
}
```

- **201 Created** returns the full `deploy` object. The `deploy` schema declares `"required": ["id"]`, so on a 201 the response **always includes `id`** (string).
- **202 Queued carries NO documented response body.** The `202` entry has only a `description` and **no `content`** — the spec does not define any body (and therefore no `id`) for the queued case.

**Operational implication for the CI job (flag):** If a create call returns **202**, the job **cannot read a deploy `id` from the create response**. To obtain the deploy id in that case it must fall back to `GET .../deploys?limit=1` (list, newest first) and match on commit/time. A robust CI job must handle both the 201 (id present) and 202 (id absent) paths. The docs do not state the precise condition that produces 202 vs 201 — see Gaps.

**URL:** https://api-docs.render.com/reference/create-deploy

---

## Q3 — GET /v1/services/{serviceId}/deploys/{deployId}: complete `status` enum

**Confidence: documented**

- **Method/path:** `GET https://api.render.com/v1/services/{serviceId}/deploys/{deployId}`.
- The `deploy.status` field is `$ref: #/components/schemas/deployStatus`. The **complete enum** (verbatim from the `deployStatus` component):

```json
"deployStatus": { "type": "string", "enum": [
  "created",
  "queued",
  "build_in_progress",
  "update_in_progress",
  "live",
  "deactivated",
  "build_failed",
  "update_failed",
  "canceled",
  "pre_deploy_in_progress",
  "pre_deploy_failed"
] }
```

That is **11 values**. Notes for the poller:
- Spelling is **`canceled`** (one "l").
- There is **no `pre_deploy_completed`** value and **no `succeeded`/`success`** value — the terminal success state is **`live`**.
- **Terminal SUCCESS:** `live`. **Terminal FAILURE:** `build_failed`, `update_failed`, `pre_deploy_failed`, `canceled`, `deactivated`. **In-progress/non-terminal:** `created`, `queued`, `build_in_progress`, `pre_deploy_in_progress`, `update_in_progress`. (Terminal-vs-nonterminal grouping is my reading of the state names — see confidence note below; the enum membership itself is documented.)

Other documented `deploy` object fields (from the `deploy` component schema): `id` (string, required), `commit` `{id, message, createdAt}`, `image` `{ref, sha, registryCredential}`, `status`, `trigger` (enum: `api`, `blueprint_sync`, `deploy_hook`, `deployed_by_render`, `manual`, `other`, `new_commit`, `rollback`, `service_resumed`, `service_updated`), `startedAt`, `finishedAt`, `createdAt`, `updatedAt` (all date-time).

**Documented response status codes:** `200`, `401`, `403`, `404`, `406`, `410`, `429`, `500`, `503`.

**Caveat:** The enum *membership* is documented. The classification of each value as terminal-success / terminal-failure / in-progress is my inference from the names (the spec lists the values but does not annotate each as terminal). CI logic keying off "stop polling when status ∈ {live, build_failed, update_failed, pre_deploy_failed, canceled, deactivated}" is sound but rests on that inference.

**URL:** https://api-docs.render.com/reference/retrieve-deploy

---

## Q4 — GET /v1/services/{serviceId}/deploys (list): wrapper shape + query params

**Confidence: documented**

- **Method/path:** `GET https://api.render.com/v1/services/{serviceId}/deploys`.
- **Response wrapper:** YES — it is a **JSON array of `{ deploy, cursor }` objects**, confirmed by the component schemas (verbatim):

```json
"deployWithCursor": { "type": "object", "properties": {
  "deploy":  { "$ref": "#/components/schemas/deploy" },
  "cursor":  { "$ref": "#/components/schemas/cursor" } } },
"deployList": { "type": "array", "items": { "$ref": "#/components/schemas/deployWithCursor" } }
```

So each element is `{ "deploy": { ...deploy object... }, "cursor": "<opaque string>" }`, and the top-level 200 body is the array (`deployList`).
- **Query parameters:**
  - **`limit`** (integer) — `default: 20`, range **1–100**. "The maximum number of items to return."
  - **`cursor`** (string) — "The position in the result list to start from when fetching paginated results."
  - **`status`** (array) — "Filter for deploys with the specified statuses."
  - Timestamp filters: `createdBefore`, `createdAfter`, `updatedBefore`, `updatedAfter`, `finishedBefore`, `finishedAfter` (all ISO-8601 date-time).
- **Documented response status codes:** `200`, `401`, `403`, `404`, `406`, `410`, `429`, `500`, `503`.

**Note on default ordering:** results are returned newest-first in practice (so `limit=1` gives the most recent deploy), but the docs text I could extract does not state the sort order explicitly — treat "newest first" as inferred, not documented.

**URL:** https://api-docs.render.com/reference/list-deploys  (note: the `get-deploys` slug in the task 404s; the live slug is `list-deploys`)

---

## Q5 — RENDER_GIT_COMMIT as a runtime env var; full SHA?

**Confidence: documented**

- **Yes**, `RENDER_GIT_COMMIT` is documented as a Render-provided default environment variable available at runtime in deployed services.
- **Description (verbatim):** "The commit SHA for a service or deploy."
- **Full vs short SHA:** The description says "commit SHA" without qualification and gives no truncated format — read as the **full 40-char SHA**. This is **inferred** (the doc does not literally say "full 40-character"), though full-SHA is the strong reading and matches common usage.
- Other Render defaults listed on the same page (useful for the deploy job / health endpoint): `RENDER`, `RENDER_GIT_BRANCH`, `RENDER_GIT_REPO_SLUG`, `RENDER_SERVICE_ID`, `RENDER_SERVICE_NAME`, `RENDER_SERVICE_TYPE`, `RENDER_INSTANCE_ID`, `RENDER_EXTERNAL_URL`, `RENDER_EXTERNAL_HOSTNAME`, `RENDER_DISCOVERY_SERVICE`, `RENDER_CPU_COUNT`, `RENDER_WEB_CONCURRENCY`, `WEB_CONCURRENCY`, `IS_PULL_REQUEST`.

**URL:** https://render.com/docs/environment-variables

---

## Q6 — API rate limits relevant to polling every 10–15s for up to 30 min

**Confidence: documented**

Documented per-category limits (Render API rate limits page):

- **Other GET requests: 400 / minute.** ← This is the bucket that covers `GET .../deploys/{deployId}` polling and `GET .../deploys` list.
- Service creation/updates/**deploys** (`POST /v1/services` and related): **20 / hour.** ← Covers `POST .../deploys` (deploy creation).
- Deploy Hooks: 10 / minute / service. Custom domains: 50 / hour. Job creation: 100 / minute. Logs endpoints: 30 / minute. Other POST/PATCH/DELETE: 30 / minute.
- **429** is returned when rate limited.
- **Rate-limit response headers:** `Ratelimit-Limit` ("Maximum requests you're permitted to make per time window"), `Ratelimit-Remaining` ("Number of requests remaining in the current rate limit window"), `Ratelimit-Reset` ("Time at which the current rate limit window resets in UTC Epoch Seconds").
- Docs advise handling 429 and setting up a retry mechanism with exponential backoff + jitter.

**Assessment for the CI job (inferred from documented numbers):** Polling every 10–15 s for 30 min = ~120–180 `GET` retrieve-deploy calls, far under the **400/min GET** limit (that limit is per-minute, not per-run, so a single poller is never close). The binding constraint is the **20/hour deploy-creation POST** limit — fine for normal CI, but a job that retries `POST .../deploys` aggressively on failure could exhaust it. Poll on GET; do not loop on POST.

**URL:** https://api-docs.render.com/reference/rate-limiting

---

## Q7 — Behavior when creating a deploy while another is in progress

**Confidence: documented** (behavior is documented; the exact create-response status code it maps to is inferred)

Per Render's deploy docs, when a deploy triggers while another is already in progress, behavior depends on the workspace's configured **concurrent-deploy policy**:

- **Wait** (default for workspaces created on/after 2025-07-14): "Allow the in-progress deploy to finish, then proceed directly to the most recently triggered deploy" — intermediate deploys are skipped.
- **Override** (default for older workspaces): "Immediately cancel the in-progress deploy and start the new one."

Framing quote: "Sometimes, a deploy will trigger while _another_ deploy is still in progress. When this occurs, your service can do one of the following:" (followed by the two policies).

So a concurrent create is **not rejected** — it is either **queued** (Wait) or it **cancels + supersedes** the in-progress deploy (Override).

**Inferred linkage to Q1/Q2:** The `202 Queued` create response plausibly corresponds to the Wait-policy queued case (deploy accepted but not yet started, hence no body/id yet), while `201 Created` corresponds to a deploy that starts immediately. The docs do **not** explicitly state this mapping — treat it as a hypothesis to confirm once API access is available.

**URL:** https://render.com/docs/deploys

---

## Gaps (docs silent — do NOT guess)

1. **202-vs-201 trigger condition (create).** The spec documents both `201 Created` (returns `deploy` with `id`) and `202 Queued` (no body), but does **not** state the precise condition under which each is returned. The Wait-policy/queued linkage in Q7 is a reasonable hypothesis, not documented. **Verify with a live create when API access is restored.**
2. **202 response body.** The spec defines **no body** for 202. Whether Render actually returns a `Location` header or any payload on 202 is undocumented; the CI job must not assume a deploy `id` is present on 202.
3. **List default sort order.** "Newest-first" for `GET .../deploys` (so `limit=1` = latest) is the widely-relied-on behavior but was not found as an explicit documented statement in the extractable page text. Confirm empirically.
4. **Terminal-status classification.** Enum *membership* (11 values) is documented; the per-value terminal/non-terminal grouping used for the poll-exit condition is inferred from the value names, not annotated in the spec.
5. **RENDER_GIT_COMMIT length.** Documented as "The commit SHA for a service or deploy" with no explicit statement of full-40-char vs abbreviated. Full SHA is the strong reading but not literally stated.
6. **Per-second burst limits.** Rate limits are documented per-minute / per-hour; no per-second burst ceiling is documented. A 10–15 s poll interval is safely within per-minute limits, but any documented instantaneous burst cap was not found.
7. **Concurrent-policy configurability via API.** The Wait/Override policy exists and has workspace-age-based defaults, but where/whether it can be set via the public API (vs dashboard only) was not confirmed from the pages fetched.
