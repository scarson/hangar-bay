// ABOUTME: Vitest config for the future-clock lane — the same suite with Date moved a year+ ahead.
// ABOUTME: Catches fixture dates that only work "for now"; see testing-pitfalls TEST-17.
import { defineConfig, mergeConfig } from 'vitest/config'
// Explicit .ts extension: tsconfig.node.json resolves with module: nodenext, which
// requires it (and sets allowImportingTsExtensions to permit it).
import baseConfig from './vite.config.ts'

// How far ahead to move the clock. Over a year, so the run crosses every annual
// boundary and no literal written "safely in the future" today can still be in the
// future here.
const OFFSET_DAYS = 400

// MUST stay relative to the real clock. A fixed instant (`'2027-08-01'`) makes this
// lane stop testing the future the moment real time passes it — the guard against
// time bombs would become one, which is the whole failure class it exists to
// eliminate (testing-pitfalls TEST-17). Do not "simplify" this to a literal for
// determinism: the property under test is "behaviour survives clock movement", not
// "output equals X". HB_FUTURE_CLOCK pins it for a reproducible re-run of a failure.
const simulatedNow =
  process.env.HB_FUTURE_CLOCK ?? new Date(Date.now() + OFFSET_DAYS * 86_400_000).toISOString()

// Logged once, in the main process, so a red run reports which future instant
// produced it and can be replayed with HB_FUTURE_CLOCK=<instant>.
console.log(`[future-clock] running the suite with Date faked to ${simulatedNow}`)

export default mergeConfig(
  baseConfig,
  defineConfig({
    test: {
      // Appended, not replacing: the lane is the ordinary suite plus a moved clock.
      setupFiles: ['./src/test/setup.ts', './src/test/future-clock.ts'],
      env: { HB_FUTURE_CLOCK: simulatedNow },
    },
  }),
)
