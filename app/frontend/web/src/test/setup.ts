import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

// vite.config.ts does not set `globals: true`, so React Testing Library's
// auto-cleanup (which registers only when `afterEach` is a global) never runs.
// Register it explicitly here — the canonical RTL-without-globals pattern — so
// each test starts with a clean DOM. Without this, renders accumulate across a
// file's tests and shared text/labels resolve to "Found multiple elements".
afterEach(() => {
  cleanup()
})
