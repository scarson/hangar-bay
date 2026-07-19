# M3 Recon — Frontend Structure

Read-only reconnaissance of the React 19 + Vite + TanStack Router/Query + Tailwind v4 frontend, produced so the Milestone 3 designer can build F005 (Saved Searches), F006 (Watchlists), and F007 (in-app Alerts) directly from this report without re-reading the code.

All paths are absolute under `/Users/sam/Code/hangar-bay/.claude/worktrees/drama-pass-implementation-ae2eeb/app/frontend/web/`. Line numbers are as of this audit.

**Stack versions** (from `package.json`): React 19.2.7, `@tanstack/react-router` 1.170.17, `@tanstack/react-query` 5.101.2, `openapi-fetch` 0.17.0, Tailwind CSS 4.3.2, Vite 8.1.4, Vitest 4.1.10, `@playwright/test` 1.61.1. Codegen: `openapi-typescript` 7.13.0. No state-management lib beyond TanStack Query; **no UI component library** (no Radix, Headless UI, etc.).

---

## 0. Headline facts for M3 (read first)

- **No modal, dialog, popover, dropdown, select, toast, or confirm primitive exists anywhere.** The entire shared-UI kit is `Button`, `Input`, `CheckboxField`, `Badge` (see §4). The **only `useMutation` in the codebase is `useLogout`** (`src/features/auth/hooks/useLogout.ts`). Every write-oriented UI surface M3 needs — "Save Search" dialog, "name this search" input-in-a-modal, delete-confirm, watchlist add/remove toasts, an alerts/notifications panel — must be **built from scratch**. There is a z-scale ready for it (`--z-modal`, `--z-toast`, etc., see §4.6) but nothing consumes those tokens yet.
- **Identity is a single TanStack Query, key `['auth','me']`, that resolves `null` on ANY failure** (401/HTTP/network). There is no `AuthContext`, no route guard, no `beforeLoad` auth check anywhere. Anonymous is a data state, not an error, and today **no page requires auth** — the whole app is public. M3 introduces the first auth-gated surfaces; there is no existing guard pattern to copy (see §5 and §7).
- **The saved-search payload is already fully specified by `ContractSearch`** (`src/features/contracts/filters.ts:20-32`) and its URL round-trip (`parseContractSearch` / `toApiQuery`). This is the exact shape to persist as F005 `search_parameters`. See §1.3.
- **API base URL owns `/api/v1`; all paths keep verbatim trailing slashes** (PROXY-1). New `/me/*` routes must follow the same trailing-slash discipline the contracts endpoints use. See §3.
- **The header (`__root.tsx`) has no nav-link region and no notification-bell slot today.** The header row is: wordmark link → tagline → `HeaderIdentity` (pushed right with `ml-auto`). M3 nav (to saved-searches / watchlist pages) and the F007 alert bell need new structure inserted here. See §7.2.

---

## 1. Routes (`src/routes/`)

File-based routing via `@tanstack/router-plugin/vite` (`autoCodeSplitting: true`). Generated tree at `src/routeTree.gen.ts` (never hand-edited; regenerated on dev/build). Route files:

| File | Route id / path | Notes |
|---|---|---|
| `src/routes/__root.tsx` | root | Header + `<Outlet/>` shell |
| `src/routes/index.tsx` | `/` | `beforeLoad` throws `redirect({ to: '/contracts', search: true })` |
| `src/routes/contracts.index.tsx` | `/contracts/` | List; `validateSearch` = `parseContractSearch` |
| `src/routes/contracts.$contractId.tsx` | `/contracts/$contractId` | Detail; `Route.useParams()` → `Number(contractId)` |

**Routing convention for a new page (M3):** create `src/routes/<name>.tsx` (flat) or `src/routes/<segment>.<child>.tsx` (dot = nesting). The plugin generates the tree; register nothing manually. Named uppercase `RouteComponent` functions are used deliberately so `eslint-plugin-react-hooks@7` recognizes `Route.useSearch()`/`Route.useParams()` as hooks-in-a-component (an anonymous `component: () =>` arrow trips `react-hooks/rules-of-hooks`) — see the comments in `contracts.index.tsx:15-17` and `contracts.$contractId.tsx:8-10`. **New authed pages (e.g. `/me/searches`, `/watchlist`) must repeat this named-component pattern.**

### 1.1 `__root.tsx` header structure (exact)

`src/routes/__root.tsx` (28 lines). The component:

```
<div flex min-h-screen flex-col>
  <header border-b border-line bg-surface>
    <div mx-auto flex w-full max-w-[1400px] items-baseline gap-3 px-4 py-3 sm:px-6>
      <Link to="/contracts"> HANGAR<span text-brand>BAY</span> </Link>   // wordmark, font-mono
      <span hidden ... sm:inline> EVE Online ship contract market </span>  // tagline
      <HeaderIdentity />                                                    // pushes right via ml-auto
    </div>
    <SsoNotice />    // full-width row under the header bar
  </header>
  <main mx-auto w-full max-w-[1400px] flex-1 px-4 py-5 sm:px-6>
    <Outlet />
  </main>
</div>
```

- **Where nav links would go:** there is currently **no nav element**. The header's flex row is `[wordmark] [tagline] [HeaderIdentity(ml-auto)]`. To add nav to saved-searches/watchlist pages, insert `<nav>` links after the tagline (they'd sit left of the `ml-auto` identity cluster) — or restructure. There is no existing nav styling to inherit.
- **Where the F007 notification bell would go:** inside `HeaderIdentity` (§5.3), most naturally left of the portrait/name/logout cluster, since the bell should only show when authenticated. `HeaderIdentity` already owns the `ml-auto` right-alignment.
- **`max-w-[1400px]`** is the repeated content-width token used by header, main, and `SsoNotice` — keep it for any new full-width M3 header rows.

### 1.2 The `/` redirect

`src/routes/index.tsx`: `beforeLoad: () => { throw redirect({ to: '/contracts', search: true }) }`. `search: true` forwards incoming search (e.g. `?sso=error` from the callback exit) — without it the redirect drops the query.

### 1.3 `ContractSearch` shape — the saved-search payload (CRITICAL for F005)

`src/features/contracts/filters.ts`. This is the canonical filter state and the exact object F005 must persist as `search_parameters`.

**Constants** (`filters.ts:1-18`):
```ts
SORT_FIELDS   = ['date_issued','date_expired','price','collateral','ship_name','volume'] as const  // SortField
SORT_DIRECTIONS = ['asc','desc'] as const                                                          // SortDirection
MIN_SEARCH_LENGTH = 3   // backend ContractFilters.search has min_length=3; shorter → 422
DEFAULT_PAGE = 1
DEFAULT_SIZE = 50
MAX_SIZE = 100
```

**`interface ContractSearch`** (`filters.ts:20-32`) — fields, types, and which are optional vs. always-present:
```ts
interface ContractSearch {
  search?: string          // optional; undefined when empty
  min_price?: number       // optional; non-negative
  max_price?: number       // optional; non-negative
  region_ids?: number[]    // optional; positive ints, sorted ascending
  is_bpc?: boolean         // optional; only `true` is meaningful (undefined = off)
  ships_only: boolean      // ALWAYS PRESENT; default true (F002 Criterion 1.1)
  page: number             // ALWAYS PRESENT; default 1
  size: number             // ALWAYS PRESENT; default 50, max 100
  sort_by: SortField       // ALWAYS PRESENT; default 'date_issued'
  sort_direction: SortDirection  // ALWAYS PRESENT; default 'desc'
}
```

**`parseContractSearch(raw)`** (`filters.ts:69-87`) is the route's `validateSearch`. It accepts arbitrary address-bar input and always returns a well-formed `ContractSearch` — invalid values fall back to defaults, never throws. Junk-tolerance rules:
- `search`: kept only if a non-empty string.
- `min_price`/`max_price`: `toNonNegativeNumber` — finite and `>= 0`, else `undefined` (negative values 422 the backend).
- `region_ids`: `toIdArray` — coerces scalar→array, keeps positive integers only, `undefined` if empty.
- `is_bpc`: kept only if literally boolean.
- `ships_only`: `raw.ships_only !== false` → **defaults ON**; only an explicit `false` in the URL widens to all contracts.
- `page`/`size`: `toBoundedInt` (page 1..MAX_SAFE_INTEGER default 1; size 1..100 default 50).
- `sort_by`/`sort_direction`: validated against the const arrays; defaults `'date_issued'` / `'desc'`.

**`toApiQuery(s)`** (`filters.ts:94-108`) — URL state → API query object. Two transforms M3 must know:
- `search` is **gated below `MIN_SEARCH_LENGTH`**: a 1–2-char value stays in the URL but is sent as `undefined` (backend would 422). Trimmed before length check.
- `ships_only: true` maps to the wire param **`is_ship_contract: true`**; `ships_only: false` → `undefined` (param omitted). All other fields pass through 1:1 (`min_price`, `max_price`, `region_ids`, `is_bpc`, `page`, `size`, `sort_by`, `sort_direction`).

**F005 design implication:** a saved search is naturally the serialized `ContractSearch` (or the subset a user set — you may choose to drop `page`). To "apply" a saved search, navigate to `/contracts` with that object as `search`. To offer "Save current search," read `Route.useSearch()` on the contracts route (already available as the `search` prop threaded into `ContractsPage`). `parseContractSearch` also gives you free validation/normalization of any persisted blob on the way back in.

### 1.4 Wire query params available (backend list endpoint)

From `src/lib/api/schema.d.ts` `list_public_contracts_contracts__get`, the backend accepts more filters than the UI exposes today: `search, min_price, max_price, min_collateral, max_collateral, min_runs, max_runs, min_me/max_me/min_te/max_te (NOT IMPLEMENTED — accepted but ignored), region_ids, system_ids, station_ids, type_ids, is_bpc, is_ship_contract, page, size, sort_by, sort_direction`. The UI's `ContractSearch` is a deliberate subset. The **watchlist matcher (F006)** and any server-side saved-search evaluation would reuse this same filter vocabulary.

---

## 2. Features (`src/features/`)

Two feature folders, both following `features/<feature>/{components,hooks}` (plus flat helper modules for contracts).

```
src/features/
  auth/
    components/  HeaderIdentity.tsx, SsoNotice.tsx  (+ .test.tsx each)
    hooks/       useCurrentUser.ts, useLogout.ts    (+ .test.tsx each)
  contracts/
    components/  ContractsPage.tsx, ContractDetailPage.tsx, ContractTable.tsx,
                 FilterRail.tsx, Pagination.tsx  (+ a11y.test.tsx, pages.test.tsx)
    hooks/       useContracts.ts, useContract.ts   (+ hooks.test.tsx)
    filters.ts, format.ts, regions.ts  (+ .test.ts each)   // flat feature-level modules
```

**M3 folders to create:** `src/features/saved-searches/{components,hooks}`, `src/features/watchlists/{components,hooks}`, `src/features/alerts/{components,hooks}` (names illustrative). Follow the same shape.

### 2.1 Hook naming + TanStack Query key hierarchies (EXACT keys)

Hooks are named `use<Thing>`. Query keys are arrays, hierarchical. **Every key in the codebase:**

| Hook | File | Query key | Notes |
|---|---|---|---|
| `useContracts(search)` | `hooks/useContracts.ts:8` | `['contracts', 'list', query]` | `query` = `toApiQuery(search)` object; `placeholderData: keepPreviousData` |
| `useContract(contractId)` | `hooks/useContract.ts:6` | `['contracts', 'detail', contractId]` | `enabled` guarded on `Number.isInteger && > 0`; custom `retry` skips 404 |
| `useCurrentUser()` | `auth/hooks/useCurrentUser.ts:12` | `['auth', 'me']` | `staleTime: 60_000`; resolves `null` on any failure |

**Convention M3 should mirror:** `[<domain>, <sub-resource>, <params>]`. Suggested (designer decides): `['savedSearches','list']`, `['watchlists','list']`, `['alerts','list']`, `['alerts','unreadCount']`. Invalidation targets the domain prefix (see §2.2).

### 2.2 Mutation + invalidation pattern (the ONLY existing example)

`src/features/auth/hooks/useLogout.ts` is the sole mutation. It is the template for all M3 CRUD mutations. Key points:

```ts
export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { response } = await api.POST('/auth/sso/logout')
      if (!response.ok) throw new ApiError(response.status)   // openapi-fetch does NOT throw on non-2xx
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['auth', 'me'] }),
  })
}
```

**Load-bearing gotcha (applies to every M3 mutation):** `openapi-fetch` resolves non-2xx as `{ error, response }` rather than throwing. A mutation that doesn't check `response.ok` will treat a 4xx/5xx as success. Always `if (!response.ok) throw new ApiError(response.status)` (or check `data === undefined` as the queries do). Only a confirmed 2xx should trigger `onSuccess`/invalidation. When the generated schema declares only a success response (e.g. 204), the typed `error` field is `never` — check `response.ok` directly, not `error`.

**Invalidation:** `onSuccess` calls `queryClient.invalidateQueries({ queryKey: [...] })` on the affected prefix. M3 CRUD (create saved search, delete watchlist item, mark alert read) should invalidate the relevant list key in `onSuccess`.

### 2.3 `format.ts` helpers (reusable)

`src/features/contracts/format.ts` exports `formatIsk`, `formatDate`, `primaryLabel(contract)`, `timeRemaining(dateExpired)` (returns `'Expired'` or a human span). M3 lists that render contracts (a watchlist of matched contracts, an alert referencing a contract) should reuse these rather than reimplement ISK/date formatting.

---

## 3. API client (`src/lib/api/`)

`src/lib/api/client.ts` (33 lines). `openapi-fetch` client typed by the generated `paths`.

```ts
export const api = createClient<paths>({
  baseUrl: (typeof location !== 'undefined' ? location.origin : '') + '/api/v1',
  fetch: (request) => globalThis.fetch(request),
})
```

- **`baseUrl` owns `/api/v1`.** Dev proxy strips it (`vite.config.ts` rewrites `^/api/v1` → ``, target `http://localhost:8000`). All schema paths are used **verbatim including trailing slashes**: `/contracts/` (slash) vs `/contracts/{contract_id}` (no slash). A missing slash triggers a 307 that escapes the rewriting proxy (**PROXY-1**). New `/me/*` routes must match the backend's exact trailing-slash choice.
- **Two testability constraints (do not "simplify"):** (1) prefixing `location.origin` keeps `new Request(url)` valid under Node/jsdom (a bare relative baseUrl throws "Invalid URL" in tests); (2) delegating `globalThis.fetch(request)` at call time keeps `vi.stubGlobal('fetch', …)` effective (openapi-fetch captures fetch at `createClient()` time otherwise).
- **Error handling:** there is **no** global error interceptor. Each hook handles it: queries throw `new ApiError(response.status)` when `data === undefined`; the mutation throws on `!response.ok`. `ApiError` (`client.ts:9-17`) is `class ApiError extends Error { status: number }`.

**Type-alias convention** (`client.ts:4-7`): re-export named aliases from the generated `components['schemas']`:
```ts
export type Contract = components['schemas']['ContractSchema']
export type ContractItem = components['schemas']['ContractItemSchema']
export type PaginatedContracts = components['schemas']['PaginatedResponse_ContractSchema_']
export type CurrentUser = components['schemas']['CurrentUserSchema']
```
**M3 must add aliases here** for new backend schemas (e.g. `SavedSearch`, `WatchlistItem`, `Alert`, and any `PaginatedResponse_*_`) after regenerating `schema.d.ts`. Regen chain: `pdm run export-openapi` (backend) → `npm run generate:api` (frontend); commit both `openapi.json` and `schema.d.ts`.

**Existing paths in `schema.d.ts`:** `/`, `/auth/sso/callback` (GET), `/auth/sso/login` (GET), `/auth/sso/logout` (POST, 204), `/cache-test`, `/contracts/` (GET), `/contracts/{contract_id}` (GET), `/health`, `/me` (GET → `CurrentUserSchema`), `/metrics`. `CurrentUserSchema = { character_id: number; character_name: string }`. New M3 `/me/*` CRUD paths will land here after regen.

---

## 4. Shared UI inventory (`src/components/`)

**Complete inventory — four primitives, nothing else:**

### 4.1 `Button.tsx`
- `Variant = 'primary' | 'ghost'` (only two).
- `primary`: `bg-brand text-brand-ink hover:bg-brand-bright active:bg-brand-dim`. `ghost`: `border border-line-strong text-ink-body hover:bg-raised`.
- Base classes (`buttonClasses`): `inline-flex h-8 shrink-0 cursor-pointer items-center gap-1.5 rounded-md px-3 text-sm transition-colors ... disabled:opacity-40`.
- Exports both `Button` (component) and `buttonClasses(variant, className)` (for styling an `<a>` as a button — used by `HeaderIdentity` login link).
- **No `danger`/destructive variant.** M3 delete actions have no styled button — either add a variant (touches this file) or compose with `text-danger` tokens.

### 4.2 `Input.tsx`
- Single text-ish input. `h-8 w-full rounded-sm border border-line-strong bg-void px-2 text-sm text-ink ... placeholder:text-ink-faint hover:border-ink-faint focus:border-brand`.
- Contains a Tailwind-v4 clash guard: strips its own base `text-sm` if the caller passes any `text-(data|xs|sm|base|lg|xl)` class (`TEXT_SIZE_CLASS` regex, `Input.tsx:10`). Relevant if M3 reuses `Input` inside a modal with custom sizing.
- Handles `type="search"`, `type="number"`, etc. via spread `...props`. **No label wiring** — callers wrap with their own `<label>` (see `FilterRail`).

### 4.3 `Checkbox.tsx` — `CheckboxField`
- `{ label: ReactNode; checked: boolean; onChange: (checked: boolean) => void }`.
- Renders `<label><input type=checkbox accent-(--color-brand) .../>{label}</label>`. Accessible by label text (used by e2e `getByLabel('Blueprint copies only')`).

### 4.4 `Badge.tsx`
- `Tone = 'neutral' | 'brand' | 'copper'`. Small uppercase mono pill (`text-micro tracking-label`). Used for Auction/Exchange/BPC/Ship/Expired markers.

### 4.5 What does NOT exist (M3 must build)
- **No modal / dialog / confirm** — no `role="dialog"`, no focus trap, no backdrop component. F005 "name & save," any delete-confirm, F006 add-to-watchlist dialogs need one built.
- **No `<select>` / dropdown / combobox / popover** — the region filter is a searchable checkbox list (`FilterRail`), not a select. Any M3 dropdown is net-new.
- **No toast / notice / snackbar** — the closest thing is `SsoNotice` (a static, dismissible, URL-param-driven `role="status"` banner under the header; §5.4), NOT a transient toast system. F006/F007 success/undo toasts need building.
- **No pagination beyond `Pagination.tsx`** (contracts-specific but generic-ish; §4.7).
- **No empty-state / spinner components** — patterns exist inline (§4.8) but aren't extracted.
- **No notification bell / badge-count / panel.**

### 4.6 Tailwind token conventions (`src/index.css`)

Dark-first, OKLCH, semantic tokens defined in `@theme`. **Use these tokens; do not reach for arbitrary values or raw colors.**

- **Surfaces (elevation = lightness):** `void` (page bg), `surface`, `raised`, `overlay`. Used as `bg-void`, `bg-surface`, etc.
- **Lines:** `line` (dividers), `line-strong` (≥3:1, interactive borders — inputs/buttons). `border-line`, `border-line-strong`.
- **Ink (text):** `ink` (headings/primary), `ink-body` (body default), `ink-dim` (secondary), `ink-faint` (tertiary/placeholder). As `text-ink`, `text-ink-dim`, etc.
- **Brand (EVE cyan):** `brand`, `brand-bright`, `brand-dim`, `brand-ink` (text on brand bg), `brand-wash` (subtle bg). `text-brand`, `bg-brand`.
- **Copper:** `--color-copper` — price emphasis only (`text-(--color-copper)`).
- **Semantic states:** `danger`, `danger-wash`, `warn`, `ok`. E.g. error alerts use `border-danger/40 bg-danger-wash`. **`ok` (green) exists but is currently unused** — available for M3 success states.
- **Type scale (`@utility`, not arbitrary):** `text-h1` (22px), `text-meta`/`text-data` (13px mono tabular for data cells), `text-label` (11px uppercase tracked label — used for section headers), `text-micro`, `text-xs/sm/base` (Tailwind defaults). Custom utilities: `text-data`, `text-label`, `skeleton` (shimmer). **Skeleton loaders use the `skeleton` utility** (`index.css:151`).
- **Radii:** `rounded-sm` (3px), `rounded-md` (6px).
- **Fonts:** `--font-sans` = IBM Plex Sans, `--font-mono` = IBM Plex Mono (mono for data/wordmark).

**Z-scale (`:root`, `index.css:70-77`) — ready for M3, unused today except `--z-sticky`:**
```
--z-dropdown: 10;  --z-sticky: 20;  --z-modal-backdrop: 30;
--z-modal: 40;     --z-toast: 50;   --z-tooltip: 60;
```
Consume as `z-(--z-modal)` etc. Only `--z-sticky` is currently used (ContractTable header). **M3 modal/toast/dropdown should use these tokens, never arbitrary z-index.**

Accessibility baked into base layer (`index.css:79-123`): global `:focus-visible` outline (2px brand), `prefers-reduced-motion` disables animation/transition. `color-scheme: dark` (light mode intentionally absent).

### 4.7 `Pagination.tsx`
`{ page, size, total, onPage }`. Renders `<nav aria-label="Pagination">` with `← Previous` / `Next →` Buttons (disabled at bounds) and a `Page X of Y · N contracts` label. `pageCount = Math.max(1, Math.ceil(total/size))`. Reusable for any M3 paginated list.

### 4.8 Empty-state, error, and skeleton patterns (inline, not extracted)
From `ContractsPage.tsx` and `ContractDetailPage.tsx` — copy these shapes:
- **Empty state:** `<div rounded-md border border-line bg-surface px-5 py-8>` with an `<h2>`, explanatory `<p text-ink-dim>`, and an action `<Button>`.
- **Error state:** `<div role="alert" ... border-danger/40 bg-danger-wash px-4 py-4>` with message `<p>` + Retry `<Button>`.
- **Loading skeleton:** `<div role="status" aria-label="Loading …">` with `skeleton`-utility bars and an `sr-only` "Loading…" text. `ContractTableSkeleton` (`ContractTable.tsx:158`) is the list skeleton.
- **Polite live region for result counts:** `<p className="sr-only" role="status" aria-live="polite">` (`ContractsPage.tsx:102`). M3 async state changes should announce similarly (WCAG 4.1.3).

---

## 5. Auth: `useCurrentUser`, `useLogout`, how authed state gates UI

### 5.1 `useCurrentUser` (exact)
`src/features/auth/hooks/useCurrentUser.ts`:
```ts
export function useCurrentUser() {
  return useQuery<CurrentUser | null>({
    queryKey: ['auth', 'me'],
    staleTime: 60_000,
    queryFn: async () => {
      try {
        const { data } = await api.GET('/me')
        return data ?? null
      } catch {
        return null
      }
    },
  })
}
```
**ANY failure → resolves `null` (anonymous), never throws.** 401 and other HTTP statuses come back as `{ data: undefined }` → `null`. Network-level failures **throw** in openapi-fetch, caught by the `try/catch` → `null`. Because it resolves (not rejects), it **bypasses the global `retry: 1`** — no retry storm, no error UI for anonymous. Anonymous is a first-class data state.

### 5.2 `useLogout` (exact)
See §2.2. POSTs `/auth/sso/logout`, throws on `!response.ok`, invalidates `['auth','me']` on success. No client-side redirect — the header re-renders anonymous once the invalidated `/me` returns 401.

### 5.3 How authed state gates UI today
`src/features/auth/components/HeaderIdentity.tsx` is the **only consumer** of auth state and the **only place UI branches on identity**:
```
const { data: user, isPending } = useCurrentUser()
if (isPending) return <div className="ml-auto h-8" aria-hidden />   // reserve space, no flash
if (!user)   return <a href="/api/v1/auth/sso/login?next=…">Log in with EVE</a>   // anonymous
return <div>portrait + character_name + <Button>Log out</Button></div>            // authenticated
```
- **Login is a FULL navigation** (`<a href>`, not an SPA `<Link>`) to the backend redirect. `next = encodeURIComponent(location.pathname + search)` with any transient `?sso=` stripped first (`HeaderIdentity.tsx:18-22`) so a successful login doesn't round-trip back to a stale SSO notice.
- **Portrait:** `https://images.evetech.net/characters/${user.character_id}/portrait?size=64` (external CDN, `alt=""` decorative).
- `isPending` renders an invisible `h-8` spacer (no login/logout flash during the initial `/me` fetch).

**M3 gating implication:** there is **no route guard, no `AuthContext`, no redirect-to-login on protected routes.** To gate an M3 page, the component calls `useCurrentUser()` and branches itself (mirroring `HeaderIdentity`). See §7.4 for the anonymous-hits-authed-page gap.

### 5.4 `SsoNotice` (the `?sso` notice)
`src/features/auth/components/SsoNotice.tsx`. Reads the **raw** search (`useLocation().searchStr`, because typed `validateSearch` drops `sso`). Shows a dismissible `role="status" aria-live="polite"` banner for `?sso=denied` (cancelled) or `?sso=error`. Dismiss uses `router.navigate({ to: location.pathname, search: strip sso, hash: true, replace: true })`. It is **not** a general toast — it's URL-param-driven and lives mounted at root under the header. Not reusable as-is for F006/F007 transient feedback, but a useful reference for a polite dismissible-banner shape.

---

## 6. Testing infrastructure

### 6.1 Component/unit tests (Vitest + Testing Library)
- **Config:** `vite.config.ts` `test` block — `environment: 'jsdom'`, `setupFiles: './src/test/setup.ts'`, **excludes `e2e/**`** (Playwright owns those). No `globals: true`.
- **`src/test/setup.ts`:** registers `afterEach(cleanup)` explicitly (RTL-without-globals pattern) + imports `@testing-library/jest-dom/vitest`.
- **`src/test/renderApp.tsx`:** `renderApp(initialUrl)` — builds a fresh `QueryClient` with `retry: false`, a `createMemoryHistory({ initialEntries: [initialUrl] })` router over the real `routeTree`, wraps in `QueryClientProvider` + `RouterProvider`, returns `{ router, ...renderResult }`. **This is the integration harness M3 page tests should use** (renders the real route tree, so a new authed route renders end-to-end).
- **`src/test/http.ts`:** `jsonResponse(body, status=200)` builds a `Response`; **`anonymousMe(handler)`** wraps a URL→Response handler so `/api/v1/me` answers **401 by default** (`http.ts:11`). Without it, URL-agnostic stubs render a bogus authenticated header (name undefined, portrait `.../characters/undefined/...`). **Every M3 component test that renders the header/root must decide the `/me` answer** — wrap with `anonymousMe(...)` for the anonymous case, or return an authed user for the authed case.

**How component tests stub `/api/v1/me`** (three patterns in the tree):
1. **URL-routing stub** (`routes.test.tsx`, `pages.test.tsx`): `vi.stubGlobal('fetch', ...)` with a handler that inspects `input.url`; wrap in `anonymousMe(...)` to force 401, or add an explicit `/me` branch returning `jsonResponse({ character_id, character_name })`.
2. **Stateful branch** (`HeaderIdentity.test.tsx` logout test): a `let authed = true` flag flipped inside the logout branch, so the post-logout `/me` refetch observes 401.
3. **`renderHook` for hook-only tests** (`useCurrentUser.test.tsx`, `useLogout.test.tsx`): `vi.stubGlobal('fetch', ...)` + a hand-built `QueryClientProvider` wrapper. Mutation tests assert **URL + METHOD at the fetch seam** (`calls.push({url, method})`) AND query invalidation (`vi.spyOn(qc, 'invalidateQueries')`), per TEST-5. `afterEach(() => vi.unstubAllGlobals())` everywhere.

**Mutation test template (M3 CRUD)** — from `useLogout.test.tsx`: capture `{url, method}` at the fetch seam; assert the URL contains the endpoint and method is correct; spy `invalidateQueries` to assert the right key is invalidated on 2xx **and NOT invalidated on non-2xx / network failure** (three tests: success, 500, thrown). Reproduce this triplet for each M3 mutation.

**Error-state tests must exhaust the QueryClient retry (TEST-7):** production `QueryClient` runs `retry: 1`, so an initial load makes **two** attempts. A stub that fails only call 0 auto-recovers on call 1 and the error branch never renders — fail as many consecutive calls as the retry issues, then let the manual Retry succeed. See `pages.test.tsx:100` and `states.spec.ts:109-140`.

- **a11y tests:** `vitest-axe` (`src/test/vitest.d.ts` declares the matchers; `a11y.test.tsx` uses them).

### 6.2 E2E tests (Playwright)
- **Config:** `playwright.config.ts` — `testDir: './e2e'`, `retries: 0` (**TEST-2**: flakes fixed with deterministic synchronization, never masked), `reporter: 'list'`, `baseURL: https://localhost:5173`, `ignoreHTTPSErrors: true`. Three projects: **`desktop`** (1280×800) + **`mobile`** (Pixel 7) run the fixture lane; **`live-smoke`** (opt-in `E2E_LIVE=1`) hits the real backend. Fixture-lane specs `testIgnore: /live-smoke/`.
- **Vitest excludes `e2e/**`; Playwright specs use `*.spec.ts`; unit/component use `*.test.ts(x)`** (TEST-6).

**E2E fixtures & helpers:**
- `e2e/fixtures/auth.ts`: **`interface WireCurrentUser { character_id: number; character_name: string }`** and **`makeCurrentUser(overrides = {})`** → `{ character_id: 91_000_001, character_name: 'Sesta Hound', ...overrides }`. M3 needs analogous wire fixtures for saved searches / watchlist items / alerts (e.g. `makeSavedSearch`, `makeWatchlistItem`, `makeAlert`) in new `e2e/fixtures/*.ts` files.
- `e2e/fixtures/contracts.ts`: `SEVEN_SHIPS`, `pageOf(...)`, `makeContract`, `makeShipItem` (wire-shape contract fixtures).
- `e2e/helpers/api.ts`:
  - **`interceptCurrentUser(page, responder)`** — `page.route(/\/api\/v1\/me$/, ...)`; pass `{ status: 401 }` for anonymous default or a `WireCurrentUser` for authed (`api.ts:116`).
  - **`interceptLogout(page, onFulfill?)`** — captures `{url, params, method}`, runs `onFulfill()` (used to flip sibling `/me` state before the 204), fulfills 204 (`api.ts:139`).
  - **`interceptContractList` / `interceptContractDetail`** — return captured-calls arrays (assert request contract, TEST-5). List/detail URL regexes assert the **trailing-slash discipline** (`LIST_URL = /\/api\/v1\/contracts\/(\?|$)/`).
  - **`failUnexpectedApiCalls(page)`** — `page.route('**/api/v1/**', route.abort)`; register **FIRST** so specific intercepts still win (handlers run last-registered-first) and any unstubbed call aborts loudly (proves "request never sent").
  - **`stubPortraits(page)`** — serves a 1×1 PNG for `images.evetech.net` so authenticated specs stay fully offline (the portrait is outside `/api/v1`).
- `e2e/helpers/ui.ts`: **`openFiltersIfCollapsed(page)`** (below-`lg` the filter rail is behind a "Filters" disclosure — call before touching filters so specs run on both desktop & mobile), **`rowLinks(page)`** = `getByRole('region', {name:'Contract results'}).getByRole('link')`.

**Selector discipline (repo rule, enforced by convention):** specs use **role/label selectors only** — `getByRole`, `getByLabel`, `getByText`. The **one sanctioned exception** is the decorative portrait `img[src*="images.evetech.net"]` (no accessible role because `alt=""`). No CSS/test-id selectors. M3 specs must keep this — which means M3 UI must be **accessible by role/label** (buttons named, inputs labeled, dialogs `role="dialog"` with an accessible name, live regions `role="status"`).

---

## 7. Where M3 UI integrates

### 7.1 Contracts page filter bar — "Save Search" button placement (F005)
- `ContractsPage.tsx` receives `search: ContractSearch` and `from: '/contracts/'` and renders a two-column grid: `<aside id="filter-rail">` (the `FilterRail`) + `<section aria-label="Contract results">`.
- `FilterRail.tsx` (`src/features/contracts/components/FilterRail.tsx`) contains, top-to-bottom: Search input, "Show" fieldset (Ships only / BPC only), Price min/max, Regions (searchable checkbox list), then a **conditional `Clear filters` `<Button>`** at the bottom (`FilterRail.tsx:146`, shown only when `hasActiveFilters`).
- **Natural "Save Search" placement:** next to `Clear filters` at the bottom of `FilterRail` (it already computes `hasActiveFilters`), OR in the results-section header row beside the `<h1>` + "N matching" count (`ContractsPage.tsx:107-116`). The current filter state to persist is exactly the `search` prop already in scope. `FilterRail`'s props are `{ search, onUpdate, onReset }` — a `Save Search` action would need either a new `onSave` prop threaded from `ContractsPage` (which has the router `navigate` and can host the save mutation) or a self-contained save control placed in `ContractsPage`'s results header. **Gating:** Save Search must only show when authenticated → the control needs `useCurrentUser()` (or a passed-in `user`) to conditionally render.

### 7.2 Header — nav to saved/watchlist pages + F007 notification bell
- `__root.tsx` header row today: `[wordmark] [tagline] [HeaderIdentity(ml-auto)]`. **No nav element exists.**
- **Nav links** (to `/me/searches`, `/watchlist`, etc.): insert a `<nav>` with `<Link>`s after the tagline (before the `ml-auto` identity cluster), or restructure the flex row. Only show authed-only links when `useCurrentUser()` returns a user.
- **F007 notification bell:** best placed inside `HeaderIdentity` (which owns the right-aligned cluster and already branches on auth), left of the portrait. It needs: an unread-count query (suggest key `['alerts','unreadCount']`), a bell button opening a panel/dropdown (no dropdown primitive exists — build one using `--z-dropdown`/`--z-modal`), and a count badge (compose from `Badge` or a small custom pill). Only render when authenticated.

### 7.3 Routing conventions for new authed pages
Create `src/routes/<name>.tsx` (flat) or dotted for nesting (e.g. `src/routes/me.searches.tsx` → `/me/searches`). Use the **named uppercase `RouteComponent`** pattern (§1). If the page reads search params, add `validateSearch`. The plugin regenerates `routeTree.gen.ts`. Point new header `<Link to="…">`s at these — TanStack Router type-checks the `to` against the generated route union.

### 7.4 What happens today when an anonymous user hits an authed page (THE GAP)
**Nothing exists.** There is **no route guard, no `beforeLoad` auth check, no redirect-to-login, no 401 boundary.** The entire current app is public; `useCurrentUser` returning `null` only ever changes the header, never blocks a route. M3 is the **first** feature to need protected routes and must **establish the pattern** — options the designer must choose between:
- **Component-level branch** (mirrors `HeaderIdentity`): the page calls `useCurrentUser()`; while `isPending` show a skeleton; if `!user` render a "sign in to use saved searches" prompt (with the same `/api/v1/auth/sso/login?next=…` full-navigation login link, `next` = the current path) instead of the feature.
- **Route-level `beforeLoad` guard:** harder — `useCurrentUser` is a hook, so a `beforeLoad` guard would need to read the query cache directly (`queryClient.ensureQueryData` / `getQueryData(['auth','me'])`) via a router `context`, which is **not currently wired** (`createRouter` in `main.tsx`/`renderApp.tsx` passes no `context`). Establishing this touches router setup.
- The **backend `/me/*` routes will 401 anonymous requests regardless**; the frontend gap is purely about presenting that gracefully (not a security hole, since the API enforces auth server-side). Recommend the component-level branch for MVP (no router-context plumbing), matching the app's existing "anonymous is a data state" philosophy.

**Login redirect mechanics to reuse (F005/F006/F007 sign-in prompts):** the exact pattern from `HeaderIdentity.tsx:18-28` — build `next = encodeURIComponent(pathname + search)` (strip transient `?sso=`), then a **full navigation** `<a href={`/api/v1/auth/sso/login?next=${next}`}>` (not an SPA `<Link>` — the browser must leave the app to hit the backend redirect).

---

## 8. Pitfalls that constrain M3 frontend work (cross-refs)

- **PROXY-1:** trailing slashes are load-bearing; `baseUrl` owns `/api/v1`; no `/api/v1` in path strings. New `/me/*` paths must match the backend's exact slash choice.
- **TEST-2:** Playwright `retries: 0` — synchronize deterministically (gates, `expect.poll`), never mask flakes.
- **TEST-5:** assert request URL/method/params at the seam, not just rendered output, for every mutation.
- **TEST-6:** `*.spec.ts` under `e2e/` (Playwright) vs `*.test.ts(x)` (Vitest); vitest excludes `e2e/**`.
- **TEST-7:** error-state tests must exhaust `retry: 1` (fail two consecutive calls).
- **openapi-fetch non-2xx does not throw** — check `response.ok` / `data === undefined` in every hook.
- After any backend schema change: `pdm run export-openapi` → `npm run generate:api`; add named type aliases in `client.ts`; commit `openapi.json` + `schema.d.ts`.
