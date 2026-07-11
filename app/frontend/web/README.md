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

> This README is a scaffold stub. A fuller README (setup, architecture, contribution notes)
> is written at milestone end per the project spec.
