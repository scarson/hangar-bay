# Design

Visual system for Hangar Bay's web app (`app/frontend/web`). Tokens live in
`src/index.css` under Tailwind v4 `@theme`; this document is the human-readable
map. Register: **product** (see PRODUCT.md). Theme: **dark-only by decree** —
tokens are semantic so a courtesy light theme could redefine the layer later.

## Color

OKLCH throughout. Neutrals are tinted toward the brand hue (~180) at 0.006–0.016
chroma; depth comes from surface lightness, never shadows.

| Token | Value | Role |
|---|---|---|
| `--color-void` | `oklch(0.115 0.008 180)` | Page ground |
| `--color-surface` | `oklch(0.155 0.01 180)` | Panels, rail, table header |
| `--color-raised` | `oklch(0.2 0.012 180)` | Hover rows, elevated bits |
| `--color-overlay` | `oklch(0.24 0.014 180)` | Menus/overlays (reserved) |
| `--color-line` | `oklch(0.28 0.012 180)` | Decorative hairlines |
| `--color-line-strong` | `oklch(0.49 0.016 180)` | Interactive boundaries (≥3:1 on void) |
| `--color-ink` | `oklch(0.93 0.006 180)` | Headings, data values |
| `--color-ink-body` | `oklch(0.85 0.008 180)` | Body text |
| `--color-ink-dim` | `oklch(0.71 0.01 180)` | Secondary labels (~8:1) |
| `--color-ink-faint` | `oklch(0.62 0.012 180)` | Hints, placeholders (~5.5:1) |
| `--color-brand` | `oklch(0.8 0.125 172)` | Oxidized teal: links, selection, focus, active sort |
| `--color-brand-bright` / `-dim` / `-ink` / `-wash` | see tokens | Hover / pressed / on-fill text / selected wash |
| `--color-copper` | `oklch(0.78 0.115 55)` | Counter-accent: price emphasis + BPC marker ONLY |
| `--color-danger` / `-wash`, `--color-warn`, `--color-ok` | see tokens | Semantic states |

Rules: brand = interaction, copper = economics, semantic colors = state. No
color carries meaning alone (badges/text always accompany). All text pairs
verified ≥ 4.5:1 (most ≥ 7:1); interactive borders ≥ 3:1.

## Typography

- **IBM Plex Sans** (400/500/600) for UI; **IBM Plex Mono** (400/500) for data.
- Every numeric/data cell uses `.text-data` (mono, `tabular-nums`, 13px) —
  numbers are the protagonists; ISK always aligns.
- `.text-label`: 11px, 600, +0.08em tracking, uppercase — section/column labels.
- Fixed rem scale (product register): 12 / 13 / 14 (UI base) / 16 (prose) / 22 (h1).
- Light-on-dark compensation: body line-height 1.55, +0.011em tracking.

## Layout

- App shell: full-width header (wordmark `HANGARBAY`, mono, tracked), content
  container max-width 1400px.
- List view: `236px` filter rail + fluid table column (`lg:` grid); below `lg`
  the rail becomes a toggled panel (single DOM instance, `aria-expanded`).
- Density is respect: tight table rows (py-2), generous section separations
  (gap-5/6/8). Machined edges: radii 3px/6px only.
- Detail view: max-width 48rem; identification/economics two-up on `md+`,
  contents list below.

## Components

`src/components/`: `Button` (primary/ghost), `Input`, `CheckboxField`
(native checkbox + `accent-color`), `Badge` (neutral/brand/copper, mono
uppercase). Feature components under `src/features/contracts/components/`.
Every interactive element has default/hover/focus-visible/active/disabled;
loading is skeletons (`.skeleton` shimmer), never spinners.

## Motion

150/200ms, `--ease-out-quart`, color/opacity transitions only. Skeleton sweep
is the one ambient animation. `prefers-reduced-motion` collapses everything to
instant + static skeleton. No page-load choreography (product register).

## Voice

Quiet sci-fi carried by restraint: mono wordmark, spectral teal on near-black,
machined edges. Never Photon-UI cosplay, never SaaS-cream, never storefront.
