ABOUTME: Doc-only verification of every field name in the Hangar Bay M4 render.yaml draft against the CURRENT Render Blueprint spec.
ABOUTME: Evidence is official Render docs (Render API unreachable this session); each answer carries confidence + exact quote + source URL.

# Render Blueprint field verification — M4 deploy

Verified against the live Render docs on 2026-07-18. Primary source: <https://render.com/docs/blueprint-spec> (server-rendered; quotes pulled from raw page text). Sub-pages used where the spec page is silent: <https://render.com/docs/disks>, <https://render.com/docs/key-value>.

Confidence legend: **documented** = explicit doc statement (quoted); **inferred** = reasonable reading, not explicit; **not-found** = docs silent (recorded as a gap, not guessed).

---

## Q1 — `autoDeployTrigger: off` vs `autoDeploy: false`

**Answer:** `autoDeployTrigger` is the CURRENT key; `autoDeploy` is DEPRECATED. Valid values: `commit`, `checksPass`, `off`.
**Confidence:** documented.
**Quote:** "This field replaces the deprecated `autoDeploy` field. If you include both, this field takes precedence." … "`commit`: Trigger a deploy on each commit … `checksPass`: Trigger a deploy only if the linked branch's CI checks pass. `off`: Disable auto-deploys." The value `off` is shown verbatim in the reference example: `autoDeployTrigger: 'off' # Disable automatic deploys`.
**Note:** "This field has no effect for services that deploy a prebuilt Docker image" — i.e. it applies to `runtime: docker` (build-from-Dockerfile) but NOT `runtime: image`. `commit` == deprecated `autoDeploy: true`; `off` == deprecated `autoDeploy: false`.
**Source:** <https://render.com/docs/blueprint-spec>

## Q2 — top-level `previews: { generation: off }`

**Answer:** Yes — `previews.generation` is a valid root-level (top-level) field. Valid values: `off`, `manual`, `automatic`.
**Confidence:** documented.
**Quote:** "`previews.generation` — The generation mode to use for preview environments. Supported values include: `off` / `manual` / `automatic`. … If you omit this field, preview environments are disabled for any linked Blueprints. Setting the deprecated field `previewsEnabled: true` is equivalent to setting this field to `automatic`."
**Note:** This is the root-level Blueprint previews control. It is distinct from per-service `previews:` (service-level, e.g. `previews: { generation: automatic }` with `numInstances`/`plan`), whose deprecated alias is `pullRequestPreviewsEnabled: true`. Omitting root `previews.generation` already disables previews, so `off` is explicit belt-and-suspenders.
**Source:** <https://render.com/docs/blueprint-spec>

## Q3 — Docker web service field names

**Answer:** All current, no renames for the listed fields.
**Confidence:** documented.
- `runtime` — CURRENT. Valid values: `node`, `python`, `elixir`, `go`, `ruby`, `rust`, `docker`, `image`, `static`. Quote: "`docker` for services that build an image from a Dockerfile." Note: "This field replaces the `env` field (`env` is still supported but is discouraged)." So `runtime: docker` is correct; `env:` is the discouraged predecessor.
- `type` — required alongside runtime. For a Docker web service use `type: web`. Quote: "`web` for a web service or static site."
- `rootDir` — CURRENT. Quote: "The service's root directory within its repo."
- `dockerfilePath` — CURRENT. Quote: "The path to the service's `Dockerfile`, relative to the repo root."
- `healthCheckPath` — CURRENT. Quote: "Web services only. The path of the service's health check endpoint. This value always starts with a `/` character."
- `preDeployCommand` — CURRENT. Quote: "this command runs after the service's `buildCommand` but before its `startCommand`. … Recommended for running database migrations and other pre-deploy tasks."
- `plan: starter` — CURRENT. Quote: "`free` … `starter` … `standard` … `pro` … `pro plus`" (plus `pro max`/`pro ultra` for web/private/worker). Default is `starter` for a new service.
- `region: frankfurt` — CURRENT. Quote: valid values "`oregon` (default) … `frankfurt` … `singapore`" (also `ohio`, `virginia`).
- `branch` — CURRENT. Quote: "For Git-based services, the branch of the linked repo to use."
**Source:** <https://render.com/docs/blueprint-spec>

## Q4 — `disk: { name, mountPath, sizeGB }` + single-instance + deploy strategy

**Answer:** Yes, `disk` with `name`/`mountPath`/`sizeGB` is current. The single-instance pin and the stop-then-start (recreate, non-zero-downtime) deploy behavior ARE documented — but on the /docs/disks page, NOT on the blueprint-spec page.
**Confidence:** documented (fields on spec page; scaling/deploy-strategy on disks page).
**Quotes (spec page):** disk example — `disk:` `name: app-data # Required field` / `mountPath: /opt/data # Required field` / `sizeGB: 5 # Default: 10`. "You can modify the `name` and `mountPath` of an existing disk. You can increase the `sizeGB` of an existing disk, but you can't reduce it." "You can't scale a service with an attached persistent disk."
**Quotes (disks page):** "You can't scale a service to multiple instances if it has a disk attached." AND — the exact stop-then-start/recreate behavior: "Adding a disk to a service prevents zero-downtime deploys. This is because: When you redeploy your service, Render stops the existing instance before bringing up the new instance. This instance swap takes a few seconds, during which your service is unavailable. This is a necessary safeguard to prevent data corruption…"
**Note for the blueprint:** disks attach to "a paid Render web service, private service, or background worker" — NOT free tier, NOT cron. Disk is unavailable during build and pre-deploy commands ("these commands run on separate compute"). Render does not use the literal words "recreate strategy," but "stops the existing instance before bringing up the new instance" is exactly that.
**Sources:** <https://render.com/docs/blueprint-spec>, <https://render.com/docs/disks>

## Q5 — envVars syntax

**Answer:** All three forms are current and correctly shaped.
**Confidence:** documented.
- **(a) fromDatabase** — Quote (example): `fromDatabase:` `name: mydatabase` / `property: connectionString`. Valid `property` values for Postgres: `connectionString`, `connectionPoolString`, `user`, `password`, `database`. Quote: "`connectionString` — Render Postgres and Key Value only. The URL for connecting to the datastore over the private network." "All fields shown in each example are required." Use `fromDatabase` specifically for Render Postgres.
- **(b) fromService for a Key Value** — `fromService: { type: keyvalue, name, property: connectionString }` is VALID. `property: connectionString` is explicitly allowed for Key Value. Quote: "`connectionString` — Render Postgres and Key Value only." For Key Value the connectionString "has the format `redis://red-xxxxxxxxxxxxxxxxxxxx:6379` (or `redis://user:password@…` if internal authentication is enabled)." The spec's own example uses `fromService:` with `type: keyvalue` / `name: lightning` / `property: host` and `property: port`, confirming `type: keyvalue` is the correct discriminator inside `fromService`. (`host`/`port`/`hostport` are documented as "Web services and private services only," yet the spec example applies them to a `keyvalue` service — for Hangar Bay use `connectionString`, which is the property explicitly blessed for Key Value.)
- **(c) sync: false placeholder** — Quote: "you can define these environment variables with `sync: false`" and example `sync: false # Prompt for a value in the Render Dashboard`. Behavior: "you're prompted to provide a value for each environment variable with `sync: false`" during INITIAL Blueprint creation only. Critical caveat: "When you update an existing Blueprint, Render ignores any environment variables with `sync: false`." and "Render does not include `sync: false` environment variables in preview environments." Related: `generateValue: true` produces "a randomized, base64-encoded, 256-bit value."
**Source:** <https://render.com/docs/blueprint-spec>

## Q6 — Key Value service fields

**Answer:** `type: keyvalue` is CURRENT (`redis` is a deprecated alias). `maxmemoryPolicy: allkeys-lru` and `ipAllowList` are valid fields. Empty-ipAllowList == private-network-only is a reasonable reading but is NOT stated verbatim.
**Confidence:** documented (type / maxmemoryPolicy / ipAllowList existence); inferred (empty-list == private-only).
**Quotes:** "A Key Value instance has the type `keyvalue` (or its deprecated alias `redis`)." — `redis` is deprecated. "`maxmemoryPolicy` — … One of the following: `allkeys-lru` (default) / `volatile-lru` / `allkeys-random` / `volatile-random` / `volatile-ttl` / `noeviction`." So `allkeys-lru` is valid (and is the default). "`ipAllowList` — Required. A list of the IP address ranges allowed to connect to your Key Value instance over the public internet." (Note: for a **Key Value** service `ipAllowList` is marked **Required**; for web/static services it is "Optional (defaults to allow all)".)
**On empty list → private-only (inferred):** the spec does NOT say "empty list = private-network-only." The /docs/key-value page supports the inference indirectly: "By default, newly created Key Value instances are not reachable at their external URL." and IP rules "apply only to connections that use your Key Value instance's external URL. Your Render services in the same region … can always connect using your instance's internal URL." So zero external ranges ⇒ external URL unreachable, internal (private-network) always works ⇒ effectively private-only. IMPORTANT nuance for the blueprint: the docs' EXPLICIT block-all-external mechanism is a dummy range, not an empty list — "To continue blocking all external connections, you can add the dummy IP range `0.0.0.0/32`." Also note `persistenceMode` (`journal-snapshot` default / `snapshot` / `off`) is the other Key-Value-specific field.
**Sources:** <https://render.com/docs/blueprint-spec>, <https://render.com/docs/key-value>

## Q7 — Static site definition

**Answer:** A static site is `type: web` + `runtime: static` (NOT a distinct top-level type). `buildCommand`, `staticPublishPath`, `routes`, and `headers` are all current with the shapes given.
**Confidence:** documented.
**Quotes:** "`web` for a web service or static site — For a static site, you also set `runtime: static`." "`static` for static sites." "`staticPublishPath` — Required. The path to the directory that contains the static files to publish, relative to the repo root. Common examples include `./build` and `./dist`."
- `buildCommand` — current (spec example: `buildCommand: yarn build`).
- `routes` — Quote/example: `routes:` `- type: redirect` / `source: /old` / `destination: /new` and `- type: rewrite` / `source: /a/*` / `destination: /a`. So `{type: rewrite|redirect, source, destination}` is exactly right. "You can modify existing routing rules and add new ones. Render preserves any existing routing rules that are not included in the Blueprint file."
- `headers` — Quote/example: `headers:` `- path: /*` / `name: X-Frame-Options` / `value: sameorigin`. So `{path, name, value}` is exactly right. "Render preserves any existing header rules that are not included in the Blueprint file."
**Note:** the field is `staticPublishPath` (NOT `publishPath`/`staticPublishDir`).
**Source:** <https://render.com/docs/blueprint-spec>

## Q8 — databases block

**Answer:** `basic-256mb` is a CURRENT plan slug (and the default). `postgresMajorVersion` is the CURRENT key; `"17"` (string) is accepted; highest available is `18`.
**Confidence:** documented.
**Quotes:** plan — "Current instance types: `free` / `basic-256mb` / `basic-1gb` / `basic-4gb` / `pro-4gb` … `pro-512gb` / `accelerated-16gb` … `accelerated-1024gb`." "Render uses `basic-256mb` for a new database." (Legacy, cannot create new: `starter`, `standard`, `pro`, `pro plus`.) Version — "`postgresMajorVersion` — The major version number of PostgreSQL to use, as a string (e.g., `"17"`). If omitted, Render uses the most recent version supported by the platform (currently 18). You can't modify this value after creation."
**Note:** `"17"` is the doc's own worked example, so it is a supported value; `18` is the current maximum/default. Value must be a quoted string. Other database fields seen: `databaseName`, `previewPlan`, `diskSizeGB`, `previewDiskSizeGB`, `region`.
**Source:** <https://render.com/docs/blueprint-spec>

## Q9 — Deprecations / renames touching keys we use

**Answer (documented):** The spec explicitly flags these. For each, the CURRENT key our draft should use is on the right:
- `autoDeploy` → **deprecated**, replaced by **`autoDeployTrigger`**. Quote: "This field replaces the deprecated `autoDeploy` field."
- `env` (service runtime selector) → **discouraged**, replaced by **`runtime`**. Quote: "This field replaces the `env` field (`env` is still supported but is discouraged)."
- `redis` (service type) → **deprecated alias** for **`keyvalue`**. Quote: "`redis` is a deprecated alias for `keyvalue`."
- `previewsEnabled: true` → **deprecated**, equals **`previews.generation: automatic`** (root level). Quote: "Setting the deprecated field `previewsEnabled: true` is equivalent to setting this field to `automatic`."
- `pullRequestPreviewsEnabled: true` → **deprecated**, equals service-level **`previews: { generation: automatic }`**. Quote: "Setting the deprecated field `pullRequestPreviewsEnabled: true` is equivalent to setting this field to `automatic`."
- `afterFirstDeployCommand` → **deprecated alias** for **`initialDeployHook`** (not used in our draft, but adjacent to `preDeployCommand`; don't confuse the two). Quote: "`afterFirstDeployCommand` is a deprecated alias for this field."

None of the keys in the render.yaml draft use a deprecated form **provided** the draft uses `autoDeployTrigger`, `runtime`, `type: keyvalue`, and `previews.generation` (all confirmed current above).
**Source:** <https://render.com/docs/blueprint-spec>

---

## Gaps

1. **Empty `ipAllowList` semantics not stated verbatim.** No Render doc says "an empty `ipAllowList` means private-network-only." It is a well-grounded inference (default Key Value instances are "not reachable at their external URL"; internal/same-region connections always work). But the docs' EXPLICIT block-all-external recipe is a dummy range `0.0.0.0/32`, not `[]`. Since `ipAllowList` is marked "Required" for a Key Value service, confirm at apply-time whether `ipAllowList: []` is accepted by the API or whether the `0.0.0.0/32` dummy is needed — this could not be tested (Render API unreachable this session).
2. **Disk deploy-strategy terminology.** The docs describe stop-then-start behavior ("Render stops the existing instance before bringing up the new instance") but never use the literal words "recreate strategy" / "stop-then-start." If the blueprint or plan text uses those exact terms, they are our paraphrase of documented behavior, not Render's wording.
3. **`fromService` property table vs. example mismatch (Key Value).** The property reference table scopes `host`/`port`/`hostport` to "Web services and private services only," yet the spec's own example applies `property: host`/`port` to a `type: keyvalue` service. The docs are internally inconsistent here. `connectionString` is unambiguously blessed for Key Value, so prefer it; whether `host`/`port` actually resolve for a `keyvalue` `fromService` could not be verified against the live API.
4. **`sync: false` update-time behavior is a live trap, not a naming gap.** Documented but worth surfacing: `sync: false` vars are prompted ONLY on initial Blueprint creation and are IGNORED on later Blueprint updates (and excluded from preview envs). Any secret added via `sync: false` after first apply must be set manually in the dashboard — a deploy-process constraint the field name alone doesn't reveal.
