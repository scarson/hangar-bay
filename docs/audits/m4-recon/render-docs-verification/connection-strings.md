<!-- ABOUTME: Doc-verified facts on Render's injected Postgres/Key Value connection-string formats plus plan facts for the Hangar Bay M4 deploy blueprint. -->
<!-- ABOUTME: Evidence is official Render docs only (no Render API access this session); every answer is tagged documented / inferred / not-found with quotes + URLs. -->

# Render connection-string formats & plan facts — documentation verification

**Context.** Verifying the exact connection strings Render injects into services (via `render.yaml` blueprint property references) and the Postgres / Key Value plan facts, for the M4 production blueprint (FastAPI backend + Valkey cache + Postgres). Render API was unreachable this session, so **official documentation is the sole evidence source**. Each answer carries a confidence tag: `documented` (explicit doc statement + quote), `inferred` (reasonable reading, not explicit), or `not-found` (docs silent → recorded as a gap; not guessed).

Primary sources fetched:
- Postgres: https://render.com/docs/postgresql-creating-connecting
- Key Value: https://render.com/docs/key-value
- Blueprint YAML reference: https://render.com/docs/blueprint-spec
- Free instances: https://render.com/docs/free

---

## Q1 — Postgres INTERNAL connection string scheme: `postgres://` or `postgresql://`?

**Answer:** `postgresql://` (the longer form, with the `ql`). The docs give the internal URL as `postgresql://USER:PASSWORD@INTERNAL_HOST:PORT/DATABASE`.

**Confidence:** documented.

**Quote (verbatim example, Internal URL):**
> `postgresql://USER:PASSWORD@INTERNAL_HOST:PORT/DATABASE`

Surrounding text: "You can view both individual details and the assembled internal URL, which has the following format:" — the rendered example that follows uses the `postgresql://` scheme.

**URL:** https://render.com/docs/postgresql-creating-connecting

**M4 note:** asyncpg accepts `postgresql://`. SQLAlchemy async needs the driver-qualified `postgresql+asyncpg://`, so the injected `DATABASE_URL` will need scheme rewriting in app config (this is an app-side concern, not a Render format question).

---

## Q2 — Postgres EXTERNAL URL scheme, and does blueprint `fromDatabase … property: connectionString` yield the INTERNAL URL?

**Answer:** External URL uses the same `postgresql://` scheme: `postgresql://USER:PASSWORD@EXTERNAL_HOST:PORT/DATABASE`. And yes — a blueprint `fromDatabase` reference with `property: connectionString` yields the **internal** (private-network) URL.

**Confidence:** documented.

**Quote (verbatim example, External URL):**
> `postgresql://USER:PASSWORD@EXTERNAL_HOST:PORT/DATABASE`

**Quote (blueprint `connectionString` property, from the Supported properties table):**
> "connectionString … Render Postgres and Key Value only. The URL for connecting to the datastore over the **private network**. For Render Postgres, has the format `postgresql://user:password@host:port/database`"

Because `connectionString` is explicitly "over the private network," it resolves to the internal URL, not the external one. (A separate `connectionPoolString` property, "Render Postgres only … through its managed connection pool (if enabled)," also uses `postgresql://…`.)

**URLs:** https://render.com/docs/postgresql-creating-connecting and https://render.com/docs/blueprint-spec

**M4 note:** the canonical way to wire the backend's `DATABASE_URL` in `render.yaml` is:
```yaml
- key: DATABASE_URL
  fromDatabase:
    name: <db-name>
    property: connectionString
```
This is verbatim the pattern in Render's example blueprint.

---

## Q3 — Key Value (Valkey) internal scheme (`redis://` vs `valkey://` vs `rediss://`), does `fromService … type: keyvalue … property: connectionString` yield it, and is TLS involved internally?

**Answer:**
- Internal scheme is **`redis://`** (NOT `valkey://`, NOT `rediss://`). Example: `redis://red-abc123:6379` (unauthenticated default) or `redis://USERNAME_HERE:PASSWORD_HERE@red-abc123:6379` (if internal auth enabled). External URL uses **`rediss://`** (TLS).
- Yes — `fromService` with `type: keyvalue` and `property: connectionString` yields the internal connection string.
- **No TLS on internal connections.** Internal is plaintext `redis://` and is unauthenticated by default; only external connections are TLS-secured (`rediss://`).

**Confidence:** documented.

**Quotes:**
> "Key Value instances use `redis://` and `rediss://` URL schemes."

> (internal example) "# An unauthenticated internal URL (default) `redis://red-abc123:6379`"  ·  "# An authenticated internal URL `redis://USERNAME_HERE:PASSWORD_HERE@red-abc123:6379`"

> (external example) `rediss://user:PASSWORD_HERE@red-abc123:6379`

> (code samples) "The REDIS_URL is set to the internal connection URL e.g. `redis://red-343245ndffg023:6379`"

> "Connections using the internal URL are **unauthenticated by default**."

> "External connections are TLS secured. The Redis CLI command provided will include the `--tls` flag." (→ internal connections are not TLS)

> (blueprint property table) "For Render Key Value, has the format `redis://red-xxxxxxxxxxxxxxxxxxxx:6379` (or `redis://user:password@red-xxxxxxxxxxxxxxxxxxxx:6379` if internal authentication is enabled)" — described as "over the private network," i.e. internal.

The blueprint example uses `type: keyvalue` for Key Value `fromService` references (shown with `property: host` and `property: port`); `property: connectionString` is the documented property that yields the full internal URL.

**URLs:** https://render.com/docs/key-value and https://render.com/docs/blueprint-spec

**M4 note:** redis-py accepts `redis://` directly; no TLS handshake on internal, and no password by default (the app's Valkey URL should not assume auth unless internal auth is explicitly enabled). `valkey://` is NOT a scheme Render emits.

---

## Q4 — Is Postgres 17 available? Current default/newest major version? Is `basic-256mb` a current plan slug + its price?

**Answer:**
- **Postgres 17: yes, available.** Docs state majors 13 through 18 are available for all new instances (17 is in range).
- **Newest offered major: 18.** Default version is not stated as an explicit number; the newest is 18 and the create flow treats a newer version as the starting point ("Optionally change the PostgreSQL Version if you want to use an **older** version").
- **`basic-256mb`: yes, a current plan slug**, and it is the **default** plan when `plan` is omitted in a blueprint.
- **Price of `basic-256mb`: NOT found** in the fetched docs (the /pricing page is client-rendered and did not yield a number; "see pricing" is only linked). Recorded as a gap.

**Confidence:** Postgres-17-available = documented; newest = documented (18); default *version number* = inferred; `basic-256mb` current + default = documented; `basic-256mb` price = not-found.

**Quotes:**
> "Major versions 13 through 18 are available for all new instances."

> "Versions 11 and 12 are available for workspaces that have at least one existing database on the corresponding version."

> "Optionally change the PostgreSQL Version if you want to use an older version."

> (blueprint `plan` field, "Current instance types:") "free · basic-256mb · basic-1gb · basic-4gb · pro-4gb · pro-8gb · … · accelerated-1024gb"

> "If you omit this field: Render uses **basic-256mb** for a new database."

Legacy (non-creatable) slugs listed separately: `starter`, `standard`, `pro`, `pro plus` — "You cannot create new databases on a legacy instance type."

**URLs:** https://render.com/docs/postgresql-creating-connecting and https://render.com/docs/blueprint-spec

---

## Q5 — Key Value FREE plan: memory cap (25 MB?), eviction behavior, is `maxmemory-policy` configurable on free?

**Answer:**
- **Free memory cap (25 MB?): NOT found.** Neither the Key Value page nor the Free-instances page states a numeric memory cap for a free Key Value instance. Recorded as a gap (the /pricing table, which likely holds it, is client-rendered and did not yield a number).
- **Eviction behavior on free specifically: NOT found** as a free-specific statement. General maxmemory-policy behavior IS documented (see below) but no free-tier carve-out or default is stated.
- **`maxmemory-policy` configurable on free: not explicitly stated for free.** The docs say the policy is selectable at creation and changeable later for Key Value instances generally, with no explicit free-tier exclusion — so it *appears* to apply to free too, but this is inferred, not documented.

**Confidence:** memory-cap = not-found; free-specific eviction = not-found; maxmemory-policy-on-free = inferred.

**Quotes (documented general behavior, not free-specific):**
> "Your Key Value instance's maxmemory policy determines which data it evicts to free space when it reaches its memory limit. You select a policy on instance creation and can change it later."

> "For caching use cases, we recommend using `allkeys-lru`." · "For job queues, we recommend using `noeviction`…"

Documented policy options include `allkeys-lru`, `noeviction`, `volatile-lru`, `volatile-lfu`, `allkeys-lfu`, `allkeys-random` (and others in the table).

**Quotes (free-specific limitations that ARE documented):**
> "Data persistence is not available for free Key Value instances." (Key Value page)

> "Only one Free Key Value instance can be active for any given workspace." (Free instances page)

> "Free Key Value instances do not continually persist their state to disk. This means that whenever an instance restarts, all of its data is lost." (Free instances page)

**URLs:** https://render.com/docs/key-value and https://render.com/docs/free

**M4 note (gap flagged):** the 25 MB figure could not be confirmed from docs this session — do NOT hardcode a cache-sizing assumption on it. Confirm via the Render dashboard/pricing UI or the Render API (`get_key_value` plan metadata) before relying on it.

---

## Q6 — Does Render Postgres enforce/require TLS on INTERNAL connections? (asyncpg implications)

**Answer:** Docs **explicitly state only that EXTERNAL connections are TLS-encrypted**; they are **silent on whether TLS is required for internal (private-network) connections**. Reading across the product (internal URL is the private-network path, and Key Value's internal path is explicitly non-TLS/unauthenticated), the internal Postgres path is most likely **not TLS-required**, but the docs do not say so explicitly.

**Confidence:** "external is TLS" = documented; "internal does not require TLS" = inferred; asyncpg-specific `ssl`/`sslmode` guidance for internal = not-found (gap).

**Quotes:**
> "Render Postgres databases are encrypted at rest using AES-256 data encryption. This encryption applies to both primary and replica instances, along with all backups. **External connections** to your database are encrypted in transit using Render-managed TLS certificates."

> (TLS troubleshooting, in the external-connection context) "Confirm that your PostgreSQL client supports TLS version 1.2 or higher…"

> "These rules apply only to connections that use your database's **external URL**. Your Render services in the same region as your database can always connect using your database's **internal URL**." (this is about IP allow-listing, but confirms internal is the private-network path distinct from the TLS-described external path)

The docs contain no statement that internal connections require or reject TLS, and no asyncpg-specific `sslmode`/`ssl=` instruction for the internal URL.

**URL:** https://render.com/docs/postgresql-creating-connecting

**M4 note (gap flagged):** asyncpg does not honor libpq `sslmode` in the URL query the way psycopg does — it takes an `ssl=` connect arg. Since docs don't pin internal TLS behavior, don't assume `sslmode=require` is needed (or harmless) on the internal URL. Verify empirically against the live internal endpoint before hardening; treat the exact asyncpg SSL posture as an open item.

---

## Gaps (docs silent — do NOT guess; verify before relying)

1. **`basic-256mb` (and all Postgres plan) prices** — not on the fetched docs pages; the /pricing page is client-rendered and returned no numbers to curl/WebFetch. Confirm via dashboard/pricing UI or Render API.
2. **Key Value free-plan memory cap (the 25 MB figure)** — not stated on the Key Value or Free-instances pages. Confirm via dashboard/pricing UI or Render API (`get_key_value`).
3. **Key Value free-plan eviction default / maxmemory-policy configurability on free** — only general (all-tier) policy behavior is documented; no free-specific default or explicit "configurable on free" statement.
4. **Postgres explicit default major version number** — inferred as 18 (newest of the 13–18 range; create flow changes version only to go "older"), but not stated as a numeric default.
5. **Internal Postgres TLS requirement + asyncpg SSL posture** — docs describe TLS only for external connections; internal-connection TLS requirement and any asyncpg `ssl=`/`sslmode` guidance are undocumented. Verify against the live internal endpoint.
6. **Key Value plan slugs/prices** — the current Key Value instance-type slugs and prices were not captured (pricing page client-rendered); confirm before choosing a paid Valkey tier.
