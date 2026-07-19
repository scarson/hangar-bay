# ABOUTME: Doc-only verification of Render static-site EDGE behavior (rewrite semantics + default response headers) for the M4 deploy blueprint.
# ABOUTME: Every answer is classified documented / inferred / not-found against official render.com/docs; not-found items are gaps to be confirmed empirically once the Render API/live site is reachable.

## Context & method

- **Constraint this session:** No Render API credential; official documentation is the only evidence source. No live `curl` against a real Render static site was possible, so all "defaults" claims rest on what the docs literally state.
- **Sources consulted (all fetched this session):**
  - `https://render.com/docs/redirects-rewrites` (full text obtained)
  - `https://render.com/docs/static-sites` (full text obtained)
  - `https://render.com/docs/static-site-headers` (full text obtained)
  - `https://render.com/docs/blueprint-spec` (render.yaml reference — `headers` / `routes` sections + examples obtained)
  - `https://render.com/docs/edge-caching` — **not reachable**: `curl` returned an empty body and WebFetch returned HTTP 404. Could not verify any default cache behavior from it.
- **Bias:** An honest "not-found" is recorded wherever the docs are silent. Several load-bearing edge behaviors (POST-through-rewrite, query-string forwarding, HSTS, default Cache-Control, ETags, override-vs-add) are **undocumented** and MUST be confirmed empirically before the production blueprint depends on them.

---

## Q1 — Absolute-URL (cross-service) rewrites: proxy semantics + POST method/body/query preservation

**Answer:** The docs do **not** describe cross-service rewrites (destination = a full URL like `https://other.onrender.com/*`) as a "proxy", and say **nothing** about preserving HTTP method, request body, or query string for non-GET (POST) requests. What is stated:

- Rewrite (as opposed to redirect) "Does not redirect the browser. Instead, your site serves the content from the rule's destination at the original path. The browser can't detect that content was served from a different path or URL."
- "Destination can be either a path or a full, publicly accessible URL."

That a full-URL rewrite means the edge fetches the origin and returns its response (i.e. proxy-like) is a **reasonable reading** of "your site serves the content from the rule's destination," but the word "proxy" and any method/body semantics are absent. Nothing addresses POST, request bodies, or non-GET methods. Static sites are a GET/HEAD-oriented CDN product; the docs never promise POST pass-through.

**Confidence:** not-found (for the proxy label and for method/body/query preservation). The proxy-nature is at best *inferred*; the POST/method/body guarantee is genuinely undocumented.

**Quote:** "Instead, your site serves the content from the rule's destination at the original path. The browser can't detect that content was served from a different path or URL." / "Destination can be either a path or a full, publicly accessible URL."

**URL:** https://render.com/docs/redirects-rewrites

> Production caution: do **not** assume a static-site rewrite to an absolute backend URL will faithfully forward a POST with body + method. This is undocumented. Route the SPA's `/api/*` to the backend at the DNS/edge/proxy layer (or make the backend same-origin) rather than relying on static-site rewrite proxying for non-GET API calls until verified live.

---

## Q2a — Wildcard splat replacement in the destination

**Answer:** Yes — documented. The string captured by `*` in the Source is substituted for `*` in the Destination. With Source `/*` and Destination `/blog/*`, a request to `/path1/path2` rewrites to `/blog/path1/path2`. So for Source `/api/v1/*` → Destination `https://host/*`, the matched splat (everything after `/api/v1/`) replaces the destination's `*`.

**Confidence:** documented.

**Quote:** "In Destination, `*` applies the entire string captured by the wildcard in Source." Example table: `/*` → `/blog/*`, "`/path1/path2` → `/blog/path1/path2`". (Placeholders like `:postid` are also supported for named path components.)

**URL:** https://render.com/docs/redirects-rewrites

---

## Q2b — Query-string forwarding on rewrites

**Answer:** Not documented. The redirects/rewrites page describes only *path* matching (Source "is matched against the path of the incoming request") and splat/placeholder substitution into the destination path. There is **no** statement about whether the incoming query string is forwarded to (or dropped from) the destination, for either same-site or absolute-URL rewrites.

**Confidence:** not-found (gap).

**Quote:** "Source must be a path (not a full URL). This is matched against the path of the incoming request." (No mention of query strings anywhere on the page.)

**URL:** https://render.com/docs/redirects-rewrites

---

## Q3 — Trailing-slash / case normalization / automatic redirects on paths or rule matching

**Answer:** No trailing-slash normalization, case normalization, or automatic path-normalization redirect is documented. What the docs *do* state about matching:

- "Render does not apply redirect or rewrite rules to a path if a resource exists at that path." (existing files win over rules)
- "Each Source requires at least one URL path component (such as `/blog`, or even `/`)." and "You can't apply redirect/rewrite rules to your domain root."
- "If this process results in a redirect to another site path, the process repeats with the new path." (chained rule evaluation)
- The only automatic redirect documented for static sites is protocol: "Render automatically redirects HTTP traffic to HTTPS" (static-sites page).

Nothing says Render adds/strips a trailing slash, canonicalizes case, or issues a redirect to normalize `/foo` vs `/foo/`.

**Confidence:** not-found (for trailing-slash/case normalization). The HTTP→HTTPS auto-redirect is documented and is the only edge normalization mentioned.

**Quote:** "Render does not apply redirect or rewrite rules to a path if a resource exists at that path." / (static-sites) "Additionally, Render automatically redirects HTTP traffic to HTTPS."

**URL:** https://render.com/docs/redirects-rewrites and https://render.com/docs/static-sites

---

## Q4a — Default HSTS (Strict-Transport-Security)

**Answer:** Not documented. No Render static-site doc states that `Strict-Transport-Security` is sent by default. HTTP→HTTPS redirection is documented, but an HSTS *header* is a separate thing and is not mentioned. (If HSTS is required, set it explicitly via a custom header rule.)

**Confidence:** not-found (gap).

**Quote:** (static-sites) "Additionally, Render automatically redirects HTTP traffic to HTTPS." — no HSTS header is mentioned anywhere.

**URL:** https://render.com/docs/static-sites , https://render.com/docs/static-site-headers

---

## Q4b — Default Cache-Control (regular files vs. custom-header-less HTML)

**Answer:** Not documented. Neither the static-sites page nor the headers page states any default `Cache-Control` value. `Cache-Control` appears only as an *example of a custom header you can set yourself* (`public, max-age=86400` on the headers page; `must-revalidate` for `/blog/*` in the blueprint example). No default is given for hashed assets, regular files, or HTML.

**Confidence:** not-found (gap). This is the single most important undocumented item for the "index.html no-cache + hashed assets immutable" strategy — see Q6.

**Quote:** (headers page, as an *example only*) "cache-control: public, max-age=86400". No sentence states a Render-applied default Cache-Control.

**URL:** https://render.com/docs/static-site-headers , https://render.com/docs/static-sites

---

## Q4c — Compression (Brotli / gzip) by default

**Answer:** Brotli is documented as on by default. gzip is not explicitly stated as a default; it's referenced only comparatively ("better than gzip"), which implies gzip fallback for non-Brotli clients but does not literally promise it.

**Confidence:** documented (Brotli default). gzip-as-fallback is inferred, not stated.

**Quote:** "Render serves your content with Brotli compression, which is better than gzip and makes your sites faster by reducing page sizes."

**URL:** https://render.com/docs/static-sites

---

## Q4d — ETags

**Answer:** Not documented. No Render static-site doc mentions `ETag` or conditional-request (`If-None-Match` / 304) behavior.

**Confidence:** not-found (gap).

**Quote:** (none — the term "ETag" does not appear on any consulted page.)

**URL:** https://render.com/docs/static-sites , https://render.com/docs/static-site-headers

---

## Q5a — Custom-header path-pattern syntax (is `/assets/*` valid?)

**Answer:** Yes — `/assets/*` is valid. The header `path` is a relative path (no domain) matched against request paths, with glob wildcards. `/blog/*` is the documented shape for "everything under a prefix," so `/assets/*` matches `/assets/` and all paths under it. Documented glob table:

| Path | Effect |
|---|---|
| `/*` | Matches all request paths |
| `/blog/*` | Matches `/blog/` and all paths under `/blog/` |
| `/**/*` | Paths with at least two slashes |
| `/*.css` | Matches `/tokens.css`, `/mode.css`, but **not** `/assets/theme.css` |
| `/**/*.css` | Matches `/assets/theme.css` but **not** `/tokens.css` |

Blueprint (`render.yaml`) uses the same syntax under `headers:` with `path` / `name` / `value` (e.g. `path: /blog/*`, `name: Cache-Control`, `value: must-revalidate`). Header names are case-insensitive.

**Confidence:** documented.

**Quote:** "The header path must be a relative path without the domain. It will be matched with all custom domains attached to your site. You can use wildcards to match arbitrary request paths." + the path/effect table above.

**URL:** https://render.com/docs/static-site-headers , https://render.com/docs/blueprint-spec

---

## Q5b — Do custom headers OVERRIDE defaults or ADD to them?

**Answer:** Not documented (for custom-vs-default interaction). The headers page explains only how a rule's name+value form the emitted header ("The header key is normalized and the value is appended to it to form the response") — this describes constructing `name: value`, **not** whether it replaces a Render default of the same name.

There is a related but distinct documented statement in the blueprint reference: **blueprint-defined** rules merge with **dashboard-defined** rules — "You can modify existing header rules and add new ones. Render preserves any existing header rules that are not included in the Blueprint file." That governs render.yaml-vs-dashboard reconciliation, **not** whether your custom header overrides a Render-injected default header. Do not conflate the two.

**Confidence:** not-found (for override-vs-add against Render defaults). The blueprint-vs-dashboard merge behavior is documented but answers a different question.

**Quote:** (headers) "The header key is normalized and the value is appended to it to form the response". (blueprint) "You can modify existing header rules and add new ones. Render preserves any existing header rules that are not included in the Blueprint file."

**URL:** https://render.com/docs/static-site-headers , https://render.com/docs/blueprint-spec

---

## Q6 — CDN cache invalidation on each deploy

**Answer:** Yes — documented. Every successful build is deployed atomically and the CDN caches are invalidated immediately, so users see the latest version. This means the "index.html served with no-cache + content-hashed assets marked immutable" strategy behaves sanely: even if an old `index.html` were cached, a deploy invalidates it; and because asset filenames are content-hashed, a new deploy references new filenames. **Caveat:** the *default* Cache-Control that Render applies to `index.html` is **not** documented (Q4b), so to guarantee `no-cache` on `index.html` and `immutable` on hashed assets you should set those explicitly via custom header rules rather than rely on unstated defaults.

**Confidence:** documented (deploy-time CDN invalidation). The interaction with your specific Cache-Control strategy is sound *given* you set the headers yourself.

**Quote:** "As soon as a build succeeds, we deploy it and immediately invalidate our CDN caches so your users always see the latest working version of your site." (Also: "each build is fully atomic.")

**URL:** https://render.com/docs/static-sites

---

## Gaps (docs silent — confirm empirically once Render API / a live static site is reachable)

1. **POST-through-rewrite:** Whether an absolute-URL rewrite proxies non-GET requests preserving method + request body is undocumented. Do not rely on it for `/api/*` → backend POSTs; verify with a live `curl -X POST` or route the API at the DNS/edge layer instead. (Q1)
2. **Query-string forwarding on rewrites:** Undocumented whether `?a=b` is forwarded to the destination (same-site or absolute-URL). (Q2b)
3. **Trailing-slash / case normalization:** No documented behavior for `/foo` vs `/foo/`, case-folding, or normalization redirects. (Q3)
4. **Default HSTS header:** Not documented; assume absent and set `Strict-Transport-Security` explicitly if required. (Q4a)
5. **Default Cache-Control values** for regular files and for custom-header-less HTML/`index.html`: undocumented. Set them explicitly. (Q4b, Q6)
6. **ETags / conditional requests:** No documentation of `ETag` or 304 handling. (Q4d)
7. **gzip fallback:** Only Brotli is stated as default; gzip is referenced comparatively, not promised as a fallback. (Q4c)
8. **Custom header override-vs-add against Render defaults:** Undocumented whether a custom `Cache-Control`/`X-Frame-Options` replaces or coexists with any Render-injected default of the same name. (The documented merge rule is blueprint-vs-dashboard, a different concern.) (Q5b)
9. **Edge caching doc unreachable:** `https://render.com/docs/edge-caching` returned empty (curl) / HTTP 404 (WebFetch) this session; could not verify any additional default cache behavior it might describe.
