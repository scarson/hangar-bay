import type { AxeMatchers } from 'vitest-axe/matchers'

declare module 'vitest' {
  // `<T = unknown>` must stay to match vitest's generic `Assertion<T>` for
  // declaration merging, so the unused type parameter is deliberate.
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type, @typescript-eslint/no-unused-vars
  interface Assertion<T = unknown> extends AxeMatchers {}
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  interface AsymmetricMatchersContaining extends AxeMatchers {}
}
