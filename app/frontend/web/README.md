# Hangar Bay — web frontend

Single-page app for browsing EVE Online contracts.

## Stack

- **Vite** (build/dev server) + **React 19**
- **TypeScript** (strict mode)
- **Tailwind CSS v4** (Vite-plugin based — no `tailwind.config.js`)
- **TanStack Router** (file-based routing) + **TanStack Query**
- **openapi-fetch** / **openapi-typescript** (typed API client generated from `openapi.json`)
- **ESLint** (flat config: `eslint.config.js`, with `jsx-a11y`) + **Prettier**
- **Vitest** + **Testing Library** (jsdom)

Dependency versions are exactly pinned (no `^`/`~`); `.npmrc` sets `save-exact=true`.

## Scripts

```bash
npm run dev          # start the Vite dev server
npm run build        # tsc -b && vite build
npm run preview      # preview the production build
npm run lint         # eslint .
npm run format       # prettier --write .
npm run test         # vitest run
npm run generate:api # regenerate src/lib/api/schema.d.ts from openapi.json
```

## Layout

- `src/components/` — hand-rolled UI primitives (`Badge`, `Button`, `Checkbox`, `Input`) styled with the Tailwind v4 design tokens in `src/index.css`.
- `src/features/contracts/` — the contract browsing feature: list and detail views (`components/`), TanStack Query hooks (`hooks/`), and the URL-search/filter, formatting, and region helpers.
- `src/lib/api/` — the typed `openapi-fetch` client and the `schema.d.ts` types generated from `openapi.json`.
- `src/routes/` — TanStack Router file-based routes (`__root`, `contracts.index`, `contracts.$contractId`); `routeTree.gen.ts` is generated.
- `src/test/` — Vitest/Testing Library setup and helpers.

Tests live next to the code they cover (`*.test.ts`/`*.test.tsx`), including `vitest-axe` accessibility checks on the list and detail views.
