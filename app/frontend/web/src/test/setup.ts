import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

// jsdom implements no layout scrolling, and TanStack Router's scroll handling
// calls window.scrollTo on navigation (router-core scroll-restoration), so every
// navigation a test performs makes jsdom log "Not implemented: Window's
// scrollTo() method" to stderr. Test output must be pristine (CLAUDE.md
// §Testing), so give the environment the no-op jsdom lacks. Nothing here
// asserts on scrolling — this fills a platform gap, it does not mock behavior.
window.scrollTo = () => {}

// axe-core's color-contrast rule probes canvas pixels; without the optional
// `canvas` native package jsdom logs "Not implemented: HTMLCanvasElement's
// getContext() method" for every probe and then returns null, which axe
// treats as "cannot determine" (incomplete, not a violation). Returning null
// directly is behavior-identical minus the stderr noise — contrast is checked
// in a real browser or not at all, never by jsdom.
HTMLCanvasElement.prototype.getContext = () => null

// vite.config.ts does not set `globals: true`, so React Testing Library's
// auto-cleanup (which registers only when `afterEach` is a global) never runs.
// Register it explicitly here — the canonical RTL-without-globals pattern — so
// each test starts with a clean DOM. Without this, renders accumulate across a
// file's tests and shared text/labels resolve to "Found multiple elements".
afterEach(() => {
  cleanup()
})
