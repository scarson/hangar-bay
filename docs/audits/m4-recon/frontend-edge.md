# M4 Recon — Frontend Build + Edge Contract

ABOUTME: Read-only recon of the Hangar Bay React SPA's build output, dev-proxy contract, runtime config, auth-redirect surface, and serving constraints for the M4 (production-readiness / deployment) designer.
ABOUTME: Facts only — exact proxy rewrite, route inventory, hardcoded API base, cookie/redirect settings, and the header/compression gaps a real edge must fill. No code was modified.

Scope: `app/frontend/web/` (plus the backend auth router + config it must interoperate with).
All paths below are relative to
`/Users/sam/Code/hangar-bay/.claude/worktrees/hangar-bay-frontend-rebuild-2e4fe7/`.
Relevant specs: `design/specifications/security-spec.md`, `design/specifications/performance-spec.md`.

---

## 1. The dev-proxy contract the production edge MUST replicate (PROXY-1)

File: `app/frontend/web/vite.config.ts:15-25`. This is the **single source of truth** for the
edge rewrite; the prod edge (Nginx/Caddy/CDN/Worker) must reproduce it exactly.

```js
server: {
  proxy: {
    '/api/v1': {
      target: 'http://localhost:8000',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api\/v1/, ''),
    },
  },
},
```

- **Exact rewrite:** strip the **`/api/v1` prefix** (anchored `^`, first occurrence only) and forward
  the remainder verbatim to the backend origin. `/api/v1/contracts/` → `/contracts/`;
  `/api/v1/auth/sso/login?next=…` → `/auth/sso/login?next=…` (query string preserved).
- **Only one proxied path prefix exists:** `/api/v1`. Everything else is served as SPA static
  assets. There is no second backend path, no websocket, no `/docs` proxy.
- **`changeOrigin: true`** rewrites the `Host` header to the backend target — the prod edge should
  set upstream `Host`/`X-Forwarded-*` equivalently.
- **Trailing slashes are load-bearing and must NOT be normalized by the edge.** `client.ts:19-21`
  and `live-smoke.spec.ts:29-33` both call this out: the SPA calls schema paths *with* trailing
  slashes (`/contracts/`), because a bare `/contracts` triggers a FastAPI **307** to the slashed
  form, and that 307's `Location` escapes the rewriting proxy → 404/error. **The edge must pass the
  path through byte-for-byte (no slash-stripping, no slash-adding, no merge_slashes rewriting).**
- **No `/api/v1` inside FastAPI:** backend routers mount bare (`main.py`), so the prefix is 100%
  the edge's responsibility. Confirmed by the comment at `vite.config.ts:16-18` pointing at
  `app/backend/src/fastapi_app/main.py:165`.
- **Same-origin by design — there is no CORS.** `main.py` adds only `RequestIDMiddleware`
  (`main.py:99-100`); grep finds no `CORSMiddleware`/`allow_origins` anywhere. The SPA and API MUST
  be served from **one origin**; the `/api/v1` path is the only seam. A split-origin deploy
  (SPA on a CDN host, API on a different host) would break auth cookies and require adding CORS —
  a design decision for M4.

---

## 2. Build output + SPA fallback requirements

- **Build command:** `npm run build` = `tsc -b && vite build` (`package.json:8`). Typecheck gates
  the build; a type error fails the build.
- **Output dir:** Vite default **`dist/`** (no `build.outDir` override; `vite.config.ts` has no
  `build` block). Static assets land in `dist/assets/` with content-hashed filenames
  (Vite/Rollup default), so they are safe to serve `immutable, max-age=31536000`.
- **Base path:** Vite default **`/`** (no `base:` in `vite.config.ts` — confirmed by grep). Assets
  are referenced from the site root; the SPA assumes it is served at the **origin root**, not a
  sub-path. Deploying under a sub-path would require setting `base` and rebuilding.
- **Entry HTML:** `app/frontend/web/index.html` — references `/src/main.tsx` (dev) which Vite
  rewrites to the hashed bundle at build. Head declares `<link rel="icon" href="/favicon.svg">`,
  `theme-color #0d1211`, and the title. `favicon.svg` is a root-served static asset.
- **Code-splitting:** `tanstackRouter({ autoCodeSplitting: true })` (`vite.config.ts:10`) → per-route
  chunks. The edge must serve all hashed chunks from `dist/assets/`.
- **SPA fallback (critical):** TanStack Router is **client-side** (`createRouter` in
  `src/main.tsx`, `RouterProvider`). There is no SSR and no server-side route table. **The edge
  MUST serve `index.html` for any non-asset, non-`/api/v1` path** (history-API fallback), or a deep
  link / refresh on any route below returns 404.

### Route inventory (`app/frontend/web/src/routes/`, file-based)

| URL path | File | Notes |
|---|---|---|
| `/` | `index.tsx` | `beforeLoad` throws `redirect({ to: '/contracts', search: true })` — forwards incoming `?sso=…` (`index.tsx:3-9`). |
| `/contracts` | `contracts.index.tsx` | List view; `validateSearch` parses filter/sort/pagination search params (`contracts.index.tsx:5-13`). |
| `/contracts/$contractId` | `contracts.$contractId.tsx` | Detail view; `contractId` is a path param coerced to Number (`contracts.$contractId.tsx:4-14`). |
| (root layout) | `__root.tsx` | Header (`HeaderIdentity`, `SsoNotice`) + `<Outlet/>`. Not a navigable path. |

Generated route tree: `src/routeTree.gen.ts` (TanStack plugin output, never hand-edited).

- **There is NO frontend auth-callback route.** The OAuth callback is a **backend** endpoint
  (`/api/v1/auth/sso/callback`, §4); it 302-redirects the browser back to a **frontend** path
  (`/` or the `next` path, with an optional `?sso=…` flag). So the SPA only ever needs fallback for
  `/`, `/contracts`, and `/contracts/:id` — all handled by the single `index.html` fallback rule.
- Any path the router doesn't recognize renders TanStack Router's not-found (still served from
  `index.html`), so the fallback rule is genuinely catch-all except for real static asset URLs.

---

## 3. Runtime configuration — there is essentially none (all baked at build)

- **The SPA reads NO `import.meta.env` / `VITE_*` variables.** Grep over `src/` and `e2e/` for
  `import.meta.env` and `VITE_` returns **empty**. There are **no `.env*` files** in
  `app/frontend/web/`. The frontend has zero runtime-injected configuration.
- **API base URL is hardcoded relative:** `src/lib/api/client.ts:30-33`:
  ```js
  export const api = createClient<paths>({
    baseUrl: (typeof location !== 'undefined' ? location.origin : '') + '/api/v1',
    fetch: (request) => globalThis.fetch(request),
  })
  ```
  Base is **`location.origin + '/api/v1'`** — always **same-origin**, always the `/api/v1` prefix.
  The `location.origin` prefix exists only so `new Request()` doesn't throw under Node/jsdom in tests
  (comment `client.ts:23-32`); in the browser it resolves to the current origin. **Consequence: the
  deployed origin serving the SPA MUST also answer `/api/v1/*` (proxied to the backend). There is no
  build-time or runtime knob to point the SPA at a different API host** — retargeting requires a code
  change, not an env var. This is the strongest constraint on the M4 topology: **single-origin edge
  that both serves static files and reverse-proxies `/api/v1` to FastAPI.**
- Other hardcoded external URL: character portraits load directly from
  `https://images.evetech.net/characters/{id}/portrait?size=64` (`HeaderIdentity.tsx:35`). This is a
  **third-party image CDN hit from the browser** — relevant if M4 adds a Content-Security-Policy
  (`img-src` must allow `images.evetech.net`), and it is not proxied.

---

## 4. Auth-relevant frontend behavior + the backend redirect contract

The SPA never handles the OAuth handshake itself; it (a) links out to the backend to start login and
(b) reacts to a `?sso=…` flag the backend appends on the return redirect.

### Login initiation (full-page navigation, not SPA route)
`src/features/auth/components/HeaderIdentity.tsx:15-30`: when anonymous, renders an `<a href>`
(full browser navigation, deliberately not a `<Link>`):
```
/api/v1/auth/sso/login?next=<encodeURIComponent(pathname + normalized search)>
```
The `sso` param is stripped from `next` before encoding (`HeaderIdentity.tsx:19-22`) so a login
doesn't round-trip the user back to a stale notice. The browser leaves the SPA, hits the edge,
which proxies to the backend `/auth/sso/login`.

### The backend redirect contract the edge/deploy must satisfy (`app/backend/src/fastapi_app/api/auth.py`)
- **`GET /auth/sso/login`** (`auth.py:89-118`): 302 to EVE's authorize URL. Sets a browser-binding
  state cookie `hb_sso_state` — `httponly=True, samesite="lax", secure=_cookie_secure(), path="/"`
  (`auth.py:111-114`), TTL from `_STATE_TTL_SECONDS`. `redirect_uri` sent to EVE is
  **`settings.ESI_SSO_CALLBACK_URL`** (`auth.py:108`).
- **`GET /auth/sso/callback`** (`auth.py:184-282`): EVE redirects the browser here. On success, sets
  the session cookie **`hb_session`** — `httponly=True, samesite="lax", secure=_cookie_secure(),
  path="/", max_age=SESSION_ABSOLUTE_TTL_SECONDS` (`auth.py:277-280`) — then 302s the browser to
  **`settings.FRONTEND_ORIGIN + <validated next>`** (`auth.py:276`, `build_redirect` at
  `auth.py:67-77`). Error/denial paths 302 to `FRONTEND_ORIGIN` with `?sso=denied|error`
  (`auth.py:224,228,249,263,271`).
- **`POST /auth/sso/logout`** (`auth.py:285`): 204; the SPA's `useLogout` (`useLogout.ts:17-18`)
  requires a real 2xx before flipping the header to anonymous.
- **`GET /me`** (`auth.py:296`): the SPA's only identity source (`useCurrentUser.ts`); 401 = anonymous.

### Two prod-config settings the callback contract hinges on (`core/config.py`)
- `ESI_SSO_CALLBACK_URL` default `"https://localhost:5173/api/v1/auth/sso/callback"` (`config.py:43`).
- `FRONTEND_ORIGIN` default `"https://localhost:5173"` (`config.py:44`).
- **Both defaults are dev values (`localhost:5173`, the Vite HTTPS dev server) and MUST be overridden
  per deployed environment.** The callback URL must also be **registered in the EVE SSO application**
  (external, out-of-repo) — a deployment prerequisite the M4 plan must call out. `FRONTEND_ORIGIN`
  is the origin the browser is sent back to after login: it must equal the public origin serving the
  SPA, or post-login redirects land on the wrong host.

### Cookie `Secure` flag is environment-gated
`_cookie_secure()` (`auth.py:80-81`) returns `settings.ENVIRONMENT != "development"`. So **any
non-development `ENVIRONMENT` (including the secure-by-default `"production"`, `config.py:21`) sets
`Secure` on `hb_session` and `hb_sso_state`.** Both cookies are `SameSite=Lax`, `HttpOnly`, `path=/`.
Implication: **production MUST terminate TLS at (or before) the edge and serve the SPA over HTTPS**,
or a `Secure` cookie is silently dropped by the browser and login appears to succeed but no session
sticks. `SameSite=Lax` is compatible with the top-level-navigation OAuth return (the callback redirect
is a top-level GET), and it depends on SPA + API being **same registrable origin** (reinforces §1/§3).

---

## 5. Serving constraints from the specs — and the gaps M4 must close

### What the specs require
- **TLS 1.2/1.3 + PFS, terminated at the web server** — `security-spec.md:28-46`. Explicitly names
  "the web server (Nginx/Caddy/etc.)" as where TLS/ciphers/HSTS live.
- **HSTS** (`Strict-Transport-Security`, `max-age` e.g. 31536000, `includeSubDomains`, `preload`) —
  `security-spec.md:33-46`. Specified as a **web-server header**, i.e. the M4 edge's job.
- **HTTP compression (Gzip/Brotli)** — `performance-spec.md:102-103`: "Ensure server
  (Uvicorn/Gunicorn) is configured for Gzip/Brotli compression."
- **Bundle budgets** — `performance-spec.md:36`: main bundle < 500 KB, lazy route chunks < 200 KB.
  The M4 deploy should verify the built `dist/assets/` against these (a build-time check candidate).
- **Secrets injected via platform env, never in the image/repo** — `security-spec.md:84-102`:
  local `.env` (gitignored), prod via hosting-platform secret injection or a KMS/Vault.
- **Session/state cookies** already conform to spec guidance (`HttpOnly`, `Secure`, `SameSite=Lax`,
  no token in `localStorage`) — `security-spec.md:119-137`; matches §4 above.

### Gaps (currently unimplemented — M4 design decisions)
- **No HSTS header is emitted anywhere.** The backend adds only `RequestIDMiddleware`
  (`main.py:99-100`); no `Strict-Transport-Security`. The spec assumes a reverse proxy sets it — **so
  M4 must introduce that edge layer** (there is none today; dev relies on Vite's own HTTPS via
  `@vitejs/plugin-basic-ssl`, `vite.config.ts:13`).
- **No Content-Security-Policy anywhere.** `security-spec.md` §3.2 covers React's JSX escaping but
  specifies **no CSP** (grep for `Content-Security-Policy`/`frame-ancestors`/`X-Frame-Options`/
  `default-src` in the spec is empty). If M4 adds CSP/security headers at the edge, note the SPA's
  cross-origin needs: `img-src` must allow `https://images.evetech.net` (portraits, §3) and the
  self-hosted fonts (`@fontsource/*`, bundled → same-origin, no external font host).
- **No compression configured.** No `GZipMiddleware` in `main.py` (grep empty) and no compression in
  the (nonexistent) edge. The M4 edge should compress `dist/` assets; hashed assets also want
  long-lived immutable cache headers, while `index.html` must be served **`no-cache`** (or short TTL)
  so new deploys are picked up — a standard SPA cache split the edge config must encode.
- **No deployment/hosting doc exists yet.** `find docs design -iname '*deploy*' -o -iname
  '*hosting*' -o -iname '*production*'` returns nothing. M4 is greenfield on serving topology.

---

## 6. E2E lanes vs. a deployed environment

File: `app/frontend/web/playwright.config.ts` + `e2e/`.

- **Two lanes** (`playwright.config.ts:3-13`):
  - **Fixture lane** (`desktop`, `mobile` projects): every API call is intercepted via `page.route`
    (`e2e/helpers/api.ts`), fully offline/deterministic — asserts nothing about a live backend.
  - **Live-smoke lane** (`live-smoke` project): structural assertions against the **real** stack
    through the Vite proxy. Opt-in via `E2E_LIVE=1` (`live-smoke.spec.ts:15`; the whole file
    `test.skip`s when the env var is unset).
- **What `E2E_LIVE=1` assumes** (`live-smoke.spec.ts:4-15`, `playwright.config.ts:20-48`):
  - `baseURL: https://localhost:5173` with `ignoreHTTPSErrors: true` — i.e. the **Vite dev server**
    (self-signed cert), NOT a production build. `webServer.command` is `npm run dev`
    (`playwright.config.ts:42-48`), `reuseExistingServer: true`.
  - The **backend up and settled on `:8000`** (comment `live-smoke.spec.ts:12-13`), reached through
    the Vite proxy → the same `/api/v1` rewrite as §1. It asserts `/api/v1/contracts/` returns
    **200** and the pathname is exactly `/api/v1/contracts/` (PROXY-1 end-to-end guard,
    `live-smoke.spec.ts:29-33`).
  - **Values are never asserted** — only structure/invariants — because the dev backend wipes and
    re-ingests on every restart (ENV-2/ENV-3), so counts/prices differ each run and a zero-ship
    dataset is legitimate (`live-smoke.spec.ts:6-11`, tests `test.skip` when `total === 0`).
  - Retries stay at **0** (`playwright.config.ts:18`); flakes are fixed with synchronization, never
    masked (TEST-2).
- **Gap for a real deployment:** there is **no lane that exercises the production build (`vite build`
  + a real static server + the prod edge rewrite)**. Live-smoke validates the *dev proxy*, not the
  *prod edge*. If M4 wants confidence that the edge config reproduces PROXY-1 (trailing slash, no
  merge_slashes, SPA fallback, `/api/v1` strip), that is a **new** post-deploy smoke/canary the M4
  plan must add — the existing live-smoke spec is a good behavioral template but is hardwired to the
  Vite dev server, not a built artifact. Auth flows are **not** covered live at all (the fixture
  `e2e/auth.spec.ts` intercepts `/me` and logout; nothing drives real EVE SSO end-to-end).

---

## Quick-reference: the edge contract in one place

| Concern | Value / rule | Source |
|---|---|---|
| Proxied path prefix | `/api/v1` only | `vite.config.ts:19` |
| Rewrite | strip `^/api/v1`, forward rest verbatim | `vite.config.ts:22` |
| Backend origin (dev) | `http://localhost:8000` | `vite.config.ts:20` |
| Trailing slash | pass through byte-for-byte (no normalize) — else 307 escapes proxy | `client.ts:19-21`, `live-smoke.spec.ts:29-33` |
| CORS | none — SPA + API MUST be same origin | `main.py` (no CORSMiddleware) |
| SPA fallback | serve `index.html` for all non-asset, non-`/api/v1` paths | `src/main.tsx` (client router) |
| Build output | `dist/`, base `/`, hashed `dist/assets/` | Vite defaults; no override in `vite.config.ts` |
| Runtime config | none — API base hardcoded `location.origin + /api/v1` | `client.ts:30-33` |
| SPA routes | `/`, `/contracts`, `/contracts/:id` | `src/routes/` |
| Auth callback | backend `/api/v1/auth/sso/callback` (no FE route) | `auth.py:184-282` |
| Cookies | `hb_session`, `hb_sso_state`: HttpOnly, SameSite=Lax, Secure when ENVIRONMENT≠development | `auth.py:80-81,111-114,277-280` |
| Must override per-env | `FRONTEND_ORIGIN`, `ESI_SSO_CALLBACK_URL` (both default to `localhost:5173`) | `config.py:43-44` |
| Portrait CDN | browser → `https://images.evetech.net` (CSP `img-src` if added) | `HeaderIdentity.tsx:35` |
| Required by spec, not yet implemented | HSTS, TLS termination, Gzip/Brotli, (no CSP specified) | `security-spec.md:28-46`, `performance-spec.md:102-103` |
